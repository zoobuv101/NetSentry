"""
US0029-US0033 — TDD tests for availability monitoring.
Covers: ping probe, response time tracking, uptime calculation,
alert thresholds, and the monitor scheduler integration.
All subprocess/socket calls mocked.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

# ── Ping probe ────────────────────────────────────────────────────────────────


class TestPingProbe:
    @pytest.mark.asyncio
    async def test_ping_success_returns_response_time(self) -> None:
        """Successful ping returns (True, response_time_ms)."""
        from netsentry.monitor.ping import ping_host

        with patch("netsentry.monitor.ping._run_subprocess", new_callable=AsyncMock) as mock_run:
            # fping output: "192.168.1.1 : [0], 64 bytes, 1.23 ms (1.23 avg, 0% loss)"
            mock_run.return_value = (
                "192.168.1.1 : [0], 64 bytes, 1.23 ms (1.23 avg, 0% loss)\n",
                "",
            )
            alive, rtt_ms = await ping_host("192.168.1.1")

        assert alive is True
        assert rtt_ms is not None
        assert 1.0 <= rtt_ms <= 2.0

    @pytest.mark.asyncio
    async def test_ping_failure_returns_false(self) -> None:
        """Unreachable host returns (False, None)."""
        from netsentry.monitor.ping import ping_host

        with patch("netsentry.monitor.ping._run_subprocess", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = ("192.168.1.1 : xmt/rcv/%loss = 1/0/100%\n", "")
            alive, rtt_ms = await ping_host("192.168.1.1")

        assert alive is False
        assert rtt_ms is None

    @pytest.mark.asyncio
    async def test_ping_tool_missing_returns_false(self) -> None:
        """fping not found returns (False, None) gracefully."""
        from netsentry.monitor.ping import ping_host

        with patch("netsentry.monitor.ping._run_subprocess", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = FileNotFoundError("fping not found")
            alive, rtt_ms = await ping_host("192.168.1.1")

        assert alive is False
        assert rtt_ms is None

    @pytest.mark.asyncio
    async def test_ping_batch_returns_results_for_all(self) -> None:
        """ping_hosts_batch() returns result for each IP."""
        from netsentry.monitor.ping import ping_hosts_batch

        output = (
            "192.168.1.1 : [0], 64 bytes, 0.85 ms (0.85 avg, 0% loss)\n"
            "192.168.1.2 : xmt/rcv/%loss = 1/0/100%\n"
            "192.168.1.3 : [0], 64 bytes, 2.10 ms (2.10 avg, 0% loss)\n"
        )
        with patch("netsentry.monitor.ping._run_subprocess", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = (output, "")
            results = await ping_hosts_batch(["192.168.1.1", "192.168.1.2", "192.168.1.3"])

        assert len(results) == 3
        assert results["192.168.1.1"][0] is True
        assert results["192.168.1.2"][0] is False
        assert results["192.168.1.3"][0] is True

    @pytest.mark.asyncio
    async def test_ping_empty_list_returns_empty(self) -> None:
        """Empty host list returns empty dict."""
        from netsentry.monitor.ping import ping_hosts_batch

        with patch("netsentry.monitor.ping._run_subprocess", new_callable=AsyncMock) as mock_run:
            results = await ping_hosts_batch([])

        mock_run.assert_not_called()
        assert results == {}


# ── Availability tracker ──────────────────────────────────────────────────────


class TestAvailabilityTracker:
    @pytest.fixture
    async def db_conn(self, tmp_path: pytest.TempPathFactory):  # type: ignore[no-untyped-def]
        from netsentry.db.connection import get_connection, run_migrations

        db_path = str(tmp_path / "test.db")  # type: ignore[operator]
        run_migrations(db_path)
        conn = await get_connection(db_path)
        yield conn
        await conn.close()

    @pytest.mark.asyncio
    async def test_record_probe_creates_availability_row(self, db_conn) -> None:  # type: ignore[no-untyped-def]
        """record_probe() writes an availability_checks row."""
        from netsentry.db.repositories.devices import DeviceRepository
        from netsentry.monitor.tracker import AvailabilityTracker

        repo = DeviceRepository(db_conn)
        await repo.upsert(mac="aa:bb:cc:dd:ee:ff", ip="192.168.1.10")

        tracker = AvailabilityTracker(conn=db_conn)
        await tracker.record_probe(
            mac="aa:bb:cc:dd:ee:ff",
            ip="192.168.1.10",
            alive=True,
            rtt_ms=1.5,
        )

        async with db_conn.execute(
            "SELECT * FROM availability_checks WHERE mac_address = ?", ("aa:bb:cc:dd:ee:ff",)
        ) as cur:
            row = await cur.fetchone()
        assert row is not None
        assert row["alive"] == 1
        assert abs(row["rtt_ms"] - 1.5) < 0.01

    @pytest.mark.asyncio
    async def test_record_offline_emits_event(self, db_conn) -> None:  # type: ignore[no-untyped-def]
        """Device going offline emits availability.down event."""
        from netsentry.db.repositories.devices import DeviceRepository
        from netsentry.db.repositories.events import EventRepository
        from netsentry.monitor.tracker import AvailabilityTracker

        device_repo = DeviceRepository(db_conn)
        await device_repo.upsert(mac="aa:bb:cc:dd:ee:ff", ip="192.168.1.10", is_online=True)

        tracker = AvailabilityTracker(conn=db_conn)
        # Record two consecutive failures (threshold=2)
        await tracker.record_probe("aa:bb:cc:dd:ee:ff", "192.168.1.10", alive=False)
        await tracker.record_probe("aa:bb:cc:dd:ee:ff", "192.168.1.10", alive=False)

        events = await EventRepository(db_conn).list_for_device("aa:bb:cc:dd:ee:ff")
        assert any(e.event_type == "availability.down" for e in events)

    @pytest.mark.asyncio
    async def test_record_recovery_emits_event(self, db_conn) -> None:  # type: ignore[no-untyped-def]
        """Device coming back online emits availability.up event."""
        from netsentry.db.repositories.devices import DeviceRepository
        from netsentry.db.repositories.events import EventRepository
        from netsentry.monitor.tracker import AvailabilityTracker

        device_repo = DeviceRepository(db_conn)
        await device_repo.upsert(mac="aa:bb:cc:dd:ee:ff", ip="192.168.1.10", is_online=True)

        tracker = AvailabilityTracker(conn=db_conn)
        # Go offline
        await tracker.record_probe("aa:bb:cc:dd:ee:ff", "192.168.1.10", alive=False)
        await tracker.record_probe("aa:bb:cc:dd:ee:ff", "192.168.1.10", alive=False)
        # Come back
        await tracker.record_probe("aa:bb:cc:dd:ee:ff", "192.168.1.10", alive=True)

        events = await EventRepository(db_conn).list_for_device("aa:bb:cc:dd:ee:ff")
        assert any(e.event_type == "availability.up" for e in events)

    @pytest.mark.asyncio
    async def test_uptime_percentage_calculation(self, db_conn) -> None:  # type: ignore[no-untyped-def]
        """get_uptime_pct() calculates uptime from availability_checks."""
        from netsentry.monitor.tracker import AvailabilityTracker

        tracker = AvailabilityTracker(conn=db_conn)
        mac = "aa:bb:cc:dd:ee:ff"

        # 8 alive, 2 dead = 80% uptime
        for _i in range(8):
            await tracker.record_probe(mac, "192.168.1.10", alive=True, rtt_ms=1.0)
        for _i in range(2):
            await tracker.record_probe(mac, "192.168.1.10", alive=False)

        pct = await tracker.get_uptime_pct(mac, hours=24)
        assert abs(pct - 80.0) < 1.0

    @pytest.mark.asyncio
    async def test_no_checks_returns_none_uptime(self, db_conn) -> None:  # type: ignore[no-untyped-def]
        """No availability data returns None uptime."""
        from netsentry.monitor.tracker import AvailabilityTracker

        tracker = AvailabilityTracker(conn=db_conn)
        pct = await tracker.get_uptime_pct("ff:ff:ff:ff:ff:ff", hours=24)
        assert pct is None


# ── Availability monitor ──────────────────────────────────────────────────────


class TestAvailabilityMonitor:
    @pytest.fixture
    async def db_conn(self, tmp_path: pytest.TempPathFactory):  # type: ignore[no-untyped-def]
        from netsentry.db.connection import get_connection, run_migrations

        db_path = str(tmp_path / "test.db")  # type: ignore[operator]
        run_migrations(db_path)
        conn = await get_connection(db_path)
        yield conn
        await conn.close()

    @pytest.mark.asyncio
    async def test_monitor_probes_all_monitored_devices(self, db_conn) -> None:  # type: ignore[no-untyped-def]
        """Monitor probes all devices with is_monitored=True."""
        from netsentry.db.repositories.devices import DeviceRepository
        from netsentry.monitor.monitor import AvailabilityMonitor

        repo = DeviceRepository(db_conn)
        await repo.upsert(mac="aa:bb:cc:dd:ee:01", ip="192.168.1.10", is_online=True)
        await repo.upsert(mac="aa:bb:cc:dd:ee:02", ip="192.168.1.11", is_online=True)
        # Mark both as monitored
        await db_conn.execute("UPDATE devices SET is_monitored = 1")
        await db_conn.commit()

        with patch(
            "netsentry.monitor.monitor.ping_hosts_batch", new_callable=AsyncMock
        ) as mock_ping:
            mock_ping.return_value = {
                "192.168.1.10": (True, 1.2),
                "192.168.1.11": (True, 0.8),
            }
            monitor = AvailabilityMonitor(conn=db_conn)
            probed = await monitor.run_probe_cycle()

        assert probed == 2
        mock_ping.assert_called_once()

    @pytest.mark.asyncio
    async def test_monitor_skips_unmonitored_devices(self, db_conn) -> None:  # type: ignore[no-untyped-def]
        """Monitor does not probe devices with is_monitored=False."""
        from netsentry.db.repositories.devices import DeviceRepository
        from netsentry.monitor.monitor import AvailabilityMonitor

        repo = DeviceRepository(db_conn)
        await repo.upsert(mac="aa:bb:cc:dd:ee:01", ip="192.168.1.10")
        # is_monitored defaults to False

        with patch(
            "netsentry.monitor.monitor.ping_hosts_batch", new_callable=AsyncMock
        ) as mock_ping:
            mock_ping.return_value = {}
            monitor = AvailabilityMonitor(conn=db_conn)
            probed = await monitor.run_probe_cycle()

        assert probed == 0

    @pytest.mark.asyncio
    async def test_monitor_skips_devices_without_ip(self, db_conn) -> None:  # type: ignore[no-untyped-def]
        """Devices with no IP are skipped in probe cycle."""
        from netsentry.db.repositories.devices import DeviceRepository
        from netsentry.monitor.monitor import AvailabilityMonitor

        repo = DeviceRepository(db_conn)
        await repo.upsert(mac="aa:bb:cc:dd:ee:01", ip=None)
        await db_conn.execute("UPDATE devices SET is_monitored = 1")
        await db_conn.commit()

        with patch(
            "netsentry.monitor.monitor.ping_hosts_batch", new_callable=AsyncMock
        ) as mock_ping:
            mock_ping.return_value = {}
            monitor = AvailabilityMonitor(conn=db_conn)
            probed = await monitor.run_probe_cycle()

        assert probed == 0
