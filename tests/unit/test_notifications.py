"""
US0012-US0014 — TDD tests for Event Engine, ntfy channel, Telegram channel.
All HTTP calls mocked — no real ntfy or Telegram required.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── Event Engine ──────────────────────────────────────────────────────────────


class TestEventEngine:
    def test_event_engine_instantiates(self) -> None:
        """EventEngine can be created with a settings-like config."""
        from netsentry.events.engine import EventEngine

        engine = EventEngine(quiet_hours_start=23, quiet_hours_end=7)
        assert engine is not None

    def test_should_notify_urgent_bypasses_quiet_hours(self) -> None:
        """Urgent severity always notifies regardless of quiet hours."""
        from netsentry.events.engine import EventEngine

        engine = EventEngine(quiet_hours_start=0, quiet_hours_end=23)
        assert engine.should_notify("device.new", "urgent") is True

    def test_should_notify_info_during_quiet_hours(self) -> None:
        """Info events are suppressed during quiet hours."""
        from netsentry.events.engine import EventEngine

        engine = EventEngine(quiet_hours_start=0, quiet_hours_end=23)
        assert engine.should_notify("device.new", "info") is False

    def test_should_notify_outside_quiet_hours(self) -> None:
        """All events notify when outside quiet hours."""
        from netsentry.events.engine import EventEngine

        engine = EventEngine(quiet_hours_start=2, quiet_hours_end=6)
        # Noon should be outside 02:00-06:00 quiet window
        assert engine.should_notify("device.offline", "high", hour=12) is True

    def test_event_type_severity_mapping(self) -> None:
        """Event type → severity mapping is correct."""
        from netsentry.events.engine import EVENT_SEVERITIES

        assert EVENT_SEVERITIES["device.new"] == "urgent"
        assert EVENT_SEVERITIES["device.offline"] == "high"
        assert EVENT_SEVERITIES["device.online"] == "info"
        assert EVENT_SEVERITIES["deco.device_roamed"] == "info"

    def test_rate_limit_suppresses_repeat_events(self) -> None:
        """Same event type for same MAC is suppressed within cooldown window."""
        from netsentry.events.engine import EventEngine

        engine = EventEngine(rate_limit_seconds=60)
        # First event: allowed
        assert engine.check_rate_limit("aa:bb:cc:dd:ee:ff", "device.offline") is True
        # Immediate second: suppressed
        assert engine.check_rate_limit("aa:bb:cc:dd:ee:ff", "device.offline") is False

    def test_rate_limit_different_mac_not_suppressed(self) -> None:
        """Rate limit is per MAC — different MACs are independent."""
        from netsentry.events.engine import EventEngine

        engine = EventEngine(rate_limit_seconds=60)
        engine.check_rate_limit("aa:bb:cc:dd:ee:ff", "device.offline")
        assert engine.check_rate_limit("11:22:33:44:55:66", "device.offline") is True

    def test_rate_limit_different_event_type_not_suppressed(self) -> None:
        """Rate limit is per event type — different types are independent."""
        from netsentry.events.engine import EventEngine

        engine = EventEngine(rate_limit_seconds=60)
        engine.check_rate_limit("aa:bb:cc:dd:ee:ff", "device.offline")
        assert engine.check_rate_limit("aa:bb:cc:dd:ee:ff", "device.online") is True


# ── ntfy channel ──────────────────────────────────────────────────────────────


class TestNtfyChannel:
    @pytest.mark.asyncio
    async def test_send_success(self) -> None:
        """ntfy channel POSTs to the configured URL and returns True."""
        from netsentry.notifications.ntfy import NtfyChannel

        channel = NtfyChannel(url="http://ntfy.local/netsentry")

        with patch("netsentry.notifications.ntfy.httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_http.post.return_value = MagicMock(status_code=200)

            result = await channel.send(
                title="New Device",
                body="192.168.1.10 joined the network",
                priority="default",
                tags=["white_check_mark"],
            )

        assert result is True
        mock_http.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_failure_returns_false(self) -> None:
        """HTTP error returns False without raising."""
        from netsentry.notifications.ntfy import NtfyChannel

        channel = NtfyChannel(url="http://ntfy.local/netsentry")

        with patch("netsentry.notifications.ntfy.httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_http.post.side_effect = Exception("Connection refused")

            result = await channel.send(title="Test", body="Test message", priority="default")

        assert result is False

    @pytest.mark.asyncio
    async def test_send_includes_correct_headers(self) -> None:
        """ntfy POST includes Title, Priority, and Tags headers."""
        from netsentry.notifications.ntfy import NtfyChannel

        channel = NtfyChannel(url="http://ntfy.local/netsentry")

        with patch("netsentry.notifications.ntfy.httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_http.post.return_value = MagicMock(status_code=200)

            await channel.send(
                title="Device Offline",
                body="laptop went offline",
                priority="high",
                tags=["warning"],
            )

        call_kwargs = mock_http.post.call_args
        headers = call_kwargs.kwargs.get("headers", {})
        assert headers.get("Title") == "Device Offline"
        assert headers.get("Priority") == "high"
        assert "warning" in headers.get("Tags", "")

    def test_ntfy_from_settings(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """NtfyChannel.from_settings() reads NTFY_URL from environment."""
        monkeypatch.setenv("NTFY_URL", "http://ntfy.example.com/alerts")
        from netsentry.notifications.ntfy import NtfyChannel

        channel = NtfyChannel.from_settings()
        assert channel._url == "http://ntfy.example.com/alerts"

    def test_ntfy_disabled_when_no_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """NtfyChannel.from_settings() returns None when NTFY_URL not set."""
        monkeypatch.delenv("NTFY_URL", raising=False)
        from netsentry.notifications.ntfy import NtfyChannel

        assert NtfyChannel.from_settings() is None


# ── Telegram channel ──────────────────────────────────────────────────────────


class TestTelegramChannel:
    @pytest.mark.asyncio
    async def test_send_success(self) -> None:
        """Telegram channel calls sendMessage API and returns True."""
        from netsentry.notifications.telegram import TelegramChannel

        channel = TelegramChannel(bot_token="123:ABC", chat_id="456789")

        with patch("netsentry.notifications.telegram.httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_http.post.return_value = MagicMock(
                status_code=200, json=MagicMock(return_value={"ok": True})
            )

            result = await channel.send(
                title="New Device",
                body="192.168.1.10 joined",
                priority="default",
            )

        assert result is True

    @pytest.mark.asyncio
    async def test_send_uses_markdown(self) -> None:
        """Telegram message uses Markdown parse mode."""
        from netsentry.notifications.telegram import TelegramChannel

        channel = TelegramChannel(bot_token="123:ABC", chat_id="456789")

        with patch("netsentry.notifications.telegram.httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_http.post.return_value = MagicMock(
                status_code=200, json=MagicMock(return_value={"ok": True})
            )

            await channel.send(title="Alert", body="Message", priority="urgent")

        payload = mock_http.post.call_args.kwargs.get("json", {})
        assert payload.get("parse_mode") == "Markdown"

    @pytest.mark.asyncio
    async def test_send_failure_returns_false(self) -> None:
        """API error returns False without raising."""
        from netsentry.notifications.telegram import TelegramChannel

        channel = TelegramChannel(bot_token="123:ABC", chat_id="456789")

        with patch("netsentry.notifications.telegram.httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_http.post.side_effect = Exception("Network error")

            result = await channel.send(title="Test", body="Test", priority="default")

        assert result is False

    def test_telegram_from_settings(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """TelegramChannel.from_settings() reads bot token and chat ID."""
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "999:XYZ")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "112233")
        from netsentry.notifications.telegram import TelegramChannel

        channel = TelegramChannel.from_settings()
        assert channel is not None
        assert channel._chat_id == "112233"

    def test_telegram_disabled_when_no_token(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """TelegramChannel.from_settings() returns None when token not set."""
        monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
        from netsentry.notifications.telegram import TelegramChannel

        assert TelegramChannel.from_settings() is None
