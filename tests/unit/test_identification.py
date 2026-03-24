"""
US0022-US0028 — TDD tests for device identification, categorisation,
AI-assisted fingerprinting, and lifecycle management.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# ── Rule-based identifier ─────────────────────────────────────────────────────


class TestRuleBasedIdentifier:
    def test_identifies_apple_device_from_oui(self) -> None:
        """Apple OUI → category=Personal Device, device_type=Apple Device."""
        from netsentry.identification.rules import identify_by_rules

        result = identify_by_rules(vendor="Apple, Inc.", hostname=None, open_ports=[])
        assert result.category == "Personal Device"

    def test_identifies_router_from_ports(self) -> None:
        """Open port 80+443 on known router OUI → category=Network Infrastructure."""
        from netsentry.identification.rules import identify_by_rules

        result = identify_by_rules(
            vendor="TP-Link Technologies", hostname=None, open_ports=[80, 443]
        )
        assert result.category == "Network Infrastructure"

    def test_identifies_printer_from_port_9100(self) -> None:
        """Port 9100 (RAW printing) → category=Printer."""
        from netsentry.identification.rules import identify_by_rules

        result = identify_by_rules(vendor=None, hostname=None, open_ports=[9100, 80])
        assert result.category == "Printer"

    def test_identifies_smart_tv_from_hostname(self) -> None:
        """Hostname containing 'tv' → category=Smart TV."""
        from netsentry.identification.rules import identify_by_rules

        result = identify_by_rules(vendor=None, hostname="samsung-tv-living-room", open_ports=[])
        assert result.category == "Smart TV"

    def test_identifies_nas_from_port_445(self) -> None:
        """SMB port 445 → category=NAS / Storage."""
        from netsentry.identification.rules import identify_by_rules

        result = identify_by_rules(vendor=None, hostname=None, open_ports=[445, 22])
        assert result.category == "NAS / Storage"

    def test_unknown_device_returns_none_category(self) -> None:
        """Unrecognised device returns category=None."""
        from netsentry.identification.rules import identify_by_rules

        result = identify_by_rules(vendor=None, hostname=None, open_ports=[])
        assert result.category is None

    def test_confidence_score_higher_with_more_signals(self) -> None:
        """More matching signals → higher confidence."""
        from netsentry.identification.rules import identify_by_rules

        low = identify_by_rules(vendor=None, hostname="myphone", open_ports=[])
        high = identify_by_rules(vendor="Apple, Inc.", hostname="iphone", open_ports=[])
        assert high.confidence >= low.confidence

    def test_result_has_required_fields(self) -> None:
        """IdentificationResult has category, device_type, confidence."""
        from netsentry.identification.rules import IdentificationResult, identify_by_rules

        result = identify_by_rules(vendor="Apple, Inc.", hostname=None, open_ports=[])
        assert isinstance(result, IdentificationResult)
        assert hasattr(result, "category")
        assert hasattr(result, "device_type")
        assert hasattr(result, "confidence")


# ── AI identifier ─────────────────────────────────────────────────────────────


class TestAiIdentifier:
    @pytest.mark.asyncio
    async def test_ai_identifier_calls_anthropic_api(self) -> None:
        """AI identifier sends device fingerprint to Claude API."""
        from netsentry.identification.ai import AiIdentifier

        identifier = AiIdentifier(api_key="test-key")
        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(
                text='{"category": "Smart Speaker", "device_type": "Amazon Echo", "confidence": 0.92}'
            )
        ]

        with patch("netsentry.identification.ai.anthropic.Anthropic") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create.return_value = mock_response

            result = await identifier.identify(
                mac="aa:bb:cc:dd:ee:ff",
                vendor="Amazon Technologies",
                hostname="echo-bedroom",
                open_ports=[55443],
            )

        assert result.category == "Smart Speaker"
        assert result.confidence >= 0.9

    @pytest.mark.asyncio
    async def test_ai_identifier_graceful_on_invalid_json(self) -> None:
        """Malformed API response returns low-confidence fallback."""
        from netsentry.identification.ai import AiIdentifier

        identifier = AiIdentifier(api_key="test-key")
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="I cannot determine the device type.")]

        with patch("netsentry.identification.ai.anthropic.Anthropic") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create.return_value = mock_response

            result = await identifier.identify(
                mac="aa:bb:cc:dd:ee:ff",
                vendor=None,
                hostname=None,
                open_ports=[],
            )

        assert result.category is None
        assert result.confidence < 0.5

    @pytest.mark.asyncio
    async def test_ai_identifier_disabled_when_no_key(self) -> None:
        """AiIdentifier returns None from factory when API key missing."""
        from netsentry.identification.ai import AiIdentifier

        result = AiIdentifier.from_settings(api_key=None)
        assert result is None


# ── Device categorisation ─────────────────────────────────────────────────────


class TestDeviceCategorisation:
    @pytest.fixture
    async def db_conn(self, tmp_path: pytest.TempPathFactory):  # type: ignore[no-untyped-def]
        from netsentry.db.connection import get_connection, run_migrations

        db_path = str(tmp_path / "test.db")  # type: ignore[operator]
        run_migrations(db_path)
        conn = await get_connection(db_path)
        yield conn
        await conn.close()

    @pytest.mark.asyncio
    async def test_categorise_applies_rule_result(self, db_conn) -> None:  # type: ignore[no-untyped-def]
        """Categorisation engine applies rule-based result to device."""
        from netsentry.db.repositories.devices import DeviceRepository
        from netsentry.identification.categoriser import DeviceCategoriser

        repo = DeviceRepository(db_conn)
        await repo.upsert(mac="aa:bb:cc:dd:ee:ff", ip="192.168.1.10", vendor="Apple, Inc.")

        categoriser = DeviceCategoriser(conn=db_conn)
        await categoriser.categorise("aa:bb:cc:dd:ee:ff")

        device = await repo.get("aa:bb:cc:dd:ee:ff")
        assert device is not None
        assert device.category == "Personal Device"

    @pytest.mark.asyncio
    async def test_categorise_skips_user_set_category(self, db_conn) -> None:  # type: ignore[no-untyped-def]
        """Device with manually set category is not overwritten."""
        from netsentry.db.repositories.devices import DeviceRepository
        from netsentry.identification.categoriser import DeviceCategoriser

        repo = DeviceRepository(db_conn)
        await repo.upsert(mac="aa:bb:cc:dd:ee:ff", ip="192.168.1.10", vendor="Apple, Inc.")
        await repo.patch(mac="aa:bb:cc:dd:ee:ff", category="My Custom Category")

        categoriser = DeviceCategoriser(conn=db_conn, overwrite_manual=False)
        await categoriser.categorise("aa:bb:cc:dd:ee:ff")

        device = await repo.get("aa:bb:cc:dd:ee:ff")
        assert device is not None
        assert device.category == "My Custom Category"


# ── Lifecycle management ──────────────────────────────────────────────────────


class TestLifecycleManagement:
    @pytest.fixture
    async def db_conn(self, tmp_path: pytest.TempPathFactory):  # type: ignore[no-untyped-def]
        from netsentry.db.connection import get_connection, run_migrations

        db_path = str(tmp_path / "test.db")  # type: ignore[operator]
        run_migrations(db_path)
        conn = await get_connection(db_path)
        yield conn
        await conn.close()

    @pytest.mark.asyncio
    async def test_archive_marks_device_historic(self, db_conn) -> None:  # type: ignore[no-untyped-def]
        """archive_device() sets lifecycle=historic."""
        from netsentry.db.repositories.devices import DeviceRepository
        from netsentry.identification.lifecycle import LifecycleManager

        repo = DeviceRepository(db_conn)
        await repo.upsert(mac="aa:bb:cc:dd:ee:ff", ip="192.168.1.1")

        manager = LifecycleManager(conn=db_conn)
        await manager.archive_device("aa:bb:cc:dd:ee:ff")

        # Should not appear in active list
        active = await repo.list(lifecycle="active")
        assert not any(d.mac_address == "aa:bb:cc:dd:ee:ff" for d in active)

        # Should appear in historic list
        historic = await repo.list(lifecycle="historic")
        assert any(d.mac_address == "aa:bb:cc:dd:ee:ff" for d in historic)

    @pytest.mark.asyncio
    async def test_purge_device_creates_audit_log(self, db_conn) -> None:  # type: ignore[no-untyped-def]
        """purge_device() writes to deletion_audit_log."""
        from netsentry.db.repositories.devices import DeviceRepository
        from netsentry.identification.lifecycle import LifecycleManager

        repo = DeviceRepository(db_conn)
        await repo.upsert(mac="aa:bb:cc:dd:ee:ff", ip="192.168.1.1")
        await repo.patch(mac="aa:bb:cc:dd:ee:ff", friendly_name="My Laptop")

        manager = LifecycleManager(conn=db_conn)
        await manager.purge_device("aa:bb:cc:dd:ee:ff")

        assert await repo.get("aa:bb:cc:dd:ee:ff") is None

        async with db_conn.execute(
            "SELECT friendly_name_at_deletion FROM deletion_audit_log WHERE mac_address = ?",
            ("aa:bb:cc:dd:ee:ff",),
        ) as cur:
            row = await cur.fetchone()
        assert row is not None
        assert row[0] == "My Laptop"

    @pytest.mark.asyncio
    async def test_auto_archive_devices_missing_threshold(self, db_conn) -> None:  # type: ignore[no-untyped-def]
        """Devices unseen for more than N days are archived automatically."""
        from datetime import UTC, datetime, timedelta

        from netsentry.db.repositories.devices import DeviceRepository
        from netsentry.db.utils import to_iso8601, utc_now
        from netsentry.identification.lifecycle import LifecycleManager

        repo = DeviceRepository(db_conn)

        # Insert a device with last_seen 91 days ago
        old_ts = to_iso8601(datetime.now(UTC) - timedelta(days=91))
        now = to_iso8601(utc_now())
        await db_conn.execute(
            "INSERT INTO devices (mac_address, current_ip, lifecycle, is_online, is_monitored, "
            "first_seen, last_seen, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("aa:bb:cc:dd:ee:ff", "192.168.1.1", "active", 0, 0, old_ts, old_ts, now, now),
        )
        await db_conn.commit()

        manager = LifecycleManager(conn=db_conn, archive_after_days=90)
        archived = await manager.auto_archive_stale()

        assert archived == 1
        historic = await repo.list(lifecycle="historic")
        assert any(d.mac_address == "aa:bb:cc:dd:ee:ff" for d in historic)
