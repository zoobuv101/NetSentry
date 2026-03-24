"""
US0019-US0021 — TDD tests for AdGuard Home integration.
Covers: HTTP client, DNS stats, blocked queries, device enrichment.
All HTTP calls mocked.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

# ── AdGuard client ────────────────────────────────────────────────────────────


class TestAdGuardClient:
    def test_client_instantiates(self) -> None:
        from netsentry.integrations.adguard.client import AdGuardClient

        client = AdGuardClient(url="http://192.168.1.1:3000", username="admin", password="pw")
        assert client is not None

    def test_from_settings(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ADGUARD_URL", "http://adguard.local:3000")
        monkeypatch.setenv("ADGUARD_USERNAME", "admin")
        monkeypatch.setenv("ADGUARD_PASSWORD", "secret")
        from netsentry.integrations.adguard.client import AdGuardClient

        client = AdGuardClient.from_settings()
        assert client._url == "http://adguard.local:3000"

    def test_from_settings_missing_url_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ADGUARD_URL", raising=False)
        from netsentry.integrations.adguard.client import AdGuardClient

        with pytest.raises(ValueError, match="ADGUARD_URL"):
            AdGuardClient.from_settings()

    @pytest.mark.asyncio
    async def test_get_stats_returns_dict(self) -> None:
        from netsentry.integrations.adguard.client import AdGuardClient

        client = AdGuardClient(url="http://ag.local", username="admin", password="pw")
        fake_stats = {"num_dns_queries": 1234, "num_blocked_filtering": 56}
        with patch.object(client, "_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = fake_stats
            stats = await client.get_stats()
        assert stats["num_dns_queries"] == 1234

    @pytest.mark.asyncio
    async def test_get_clients_returns_list(self) -> None:
        from netsentry.integrations.adguard.client import AdGuardClient

        client = AdGuardClient(url="http://ag.local", username="admin", password="pw")
        fake = {"clients": [{"ip": "192.168.1.10", "name": "laptop"}], "auto_clients": []}
        with patch.object(client, "_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = fake
            clients = await client.get_clients()
        assert len(clients) == 1
        assert clients[0]["ip"] == "192.168.1.10"

    @pytest.mark.asyncio
    async def test_connection_error_raises(self) -> None:
        from netsentry.integrations.adguard.client import AdGuardClient
        from netsentry.integrations.adguard.exceptions import AdGuardConnectionError

        client = AdGuardClient(url="http://ag.local", username="admin", password="pw")
        with patch.object(client, "_get", side_effect=AdGuardConnectionError("refused")):
            with pytest.raises(AdGuardConnectionError):
                await client.get_stats()


# ── AdGuard stats models ──────────────────────────────────────────────────────


class TestAdGuardModels:
    def test_parse_stats(self) -> None:
        from netsentry.integrations.adguard.models import AdGuardStats

        raw = {
            "num_dns_queries": 5000,
            "num_blocked_filtering": 200,
            "num_replaced_safebrowsing": 5,
            "num_replaced_parental": 0,
            "avg_processing_time": 0.0015,
        }
        stats = AdGuardStats.from_raw(raw)
        assert stats.total_queries == 5000
        assert stats.blocked_queries == 200
        assert stats.block_rate == pytest.approx(0.04)

    def test_block_rate_zero_when_no_queries(self) -> None:
        from netsentry.integrations.adguard.models import AdGuardStats

        stats = AdGuardStats.from_raw({"num_dns_queries": 0, "num_blocked_filtering": 0})
        assert stats.block_rate == 0.0


# ── AdGuard poller ────────────────────────────────────────────────────────────


class TestAdGuardPoller:
    @pytest.fixture
    async def db_conn(self, tmp_path: pytest.TempPathFactory):  # type: ignore[no-untyped-def]
        from netsentry.db.connection import get_connection, run_migrations

        db_path = str(tmp_path / "test.db")  # type: ignore[operator]
        run_migrations(db_path)
        conn = await get_connection(db_path)
        yield conn
        await conn.close()

    @pytest.mark.asyncio
    async def test_poller_enriches_device_hostname_from_adguard(self, db_conn) -> None:  # type: ignore[no-untyped-def]
        """AdGuard client names are used to enrich device hostnames."""
        from netsentry.db.repositories.devices import DeviceRepository
        from netsentry.integrations.adguard.poller import AdGuardPoller

        repo = DeviceRepository(db_conn)
        await repo.upsert(mac="aa:bb:cc:dd:ee:ff", ip="192.168.1.10")

        mock_client = AsyncMock()
        mock_client.get_clients = AsyncMock(
            return_value=[{"ip": "192.168.1.10", "name": "Ian-MacBook", "ids": ["192.168.1.10"]}]
        )
        mock_client.get_stats = AsyncMock(
            return_value={"num_dns_queries": 100, "num_blocked_filtering": 10}
        )

        poller = AdGuardPoller(client=mock_client, conn=db_conn)
        await poller.poll()

        device = await repo.get("aa:bb:cc:dd:ee:ff")
        assert device is not None
        assert device.hostname == "Ian-MacBook"

    @pytest.mark.asyncio
    async def test_poller_stores_dns_stats(self, db_conn) -> None:  # type: ignore[no-untyped-def]
        """AdGuard stats are stored in system_config."""
        from netsentry.integrations.adguard.poller import AdGuardPoller

        mock_client = AsyncMock()
        mock_client.get_clients = AsyncMock(return_value=[])
        mock_client.get_stats = AsyncMock(
            return_value={
                "num_dns_queries": 9999,
                "num_blocked_filtering": 333,
            }
        )

        poller = AdGuardPoller(client=mock_client, conn=db_conn)
        await poller.poll()

        async with db_conn.execute(
            "SELECT value FROM system_config WHERE key = ?", ("adguard.last_stats",)
        ) as cur:
            row = await cur.fetchone()
        assert row is not None
        import json

        stats = json.loads(row[0])
        assert stats["total_queries"] == 9999

    @pytest.mark.asyncio
    async def test_poller_graceful_on_error(self, db_conn) -> None:  # type: ignore[no-untyped-def]
        """AdGuard connection error is swallowed gracefully."""
        from netsentry.integrations.adguard.exceptions import AdGuardConnectionError
        from netsentry.integrations.adguard.poller import AdGuardPoller

        mock_client = AsyncMock()
        mock_client.get_stats = AsyncMock(side_effect=AdGuardConnectionError("AdGuard unreachable"))
        mock_client.get_clients = AsyncMock(return_value=[])

        poller = AdGuardPoller(client=mock_client, conn=db_conn)
        await poller.poll()  # Should not raise
