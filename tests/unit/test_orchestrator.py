"""
US0007 — TDD tests for APScheduler task harness, scan orchestrator,
OUI resolution, scan profiles, and online/offline state machine.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── OUI resolution ────────────────────────────────────────────────────────────


class TestOuiResolution:
    def test_resolve_vendor_known_mac(self, tmp_path: pytest.TempPathFactory) -> None:
        """Known OUI returns manufacturer string."""
        from netsentry.scanner.oui import OuiDatabase

        # Write a minimal manuf file
        manuf_file = tmp_path / "manuf"  # type: ignore[operator]
        manuf_file.write_text(
            "# Wireshark manuf file\n"
            "AA:BB:CC\tVendorCorp\tVendor Corporation\n"
            "11:22:33\tAcmeLtd\tAcme Ltd\n"
        )
        db = OuiDatabase(str(manuf_file))
        assert db.lookup("aa:bb:cc:dd:ee:ff") == "Vendor Corporation"
        assert db.lookup("11:22:33:44:55:66") == "Acme Ltd"

    def test_resolve_vendor_unknown_mac(self, tmp_path: pytest.TempPathFactory) -> None:
        """Unknown OUI returns None."""
        from netsentry.scanner.oui import OuiDatabase

        manuf_file = tmp_path / "manuf"  # type: ignore[operator]
        manuf_file.write_text("AA:BB:CC\tVendorCorp\tVendor Corporation\n")
        db = OuiDatabase(str(manuf_file))
        assert db.lookup("ff:ee:dd:cc:bb:aa") is None

    def test_resolve_vendor_normalises_mac(self, tmp_path: pytest.TempPathFactory) -> None:
        """Lookup normalises the MAC before matching."""
        from netsentry.scanner.oui import OuiDatabase

        manuf_file = tmp_path / "manuf"  # type: ignore[operator]
        manuf_file.write_text("AA:BB:CC\tVendorCorp\tVendor Corporation\n")
        db = OuiDatabase(str(manuf_file))
        # Dashes, uppercase — should still resolve
        assert db.lookup("AA-BB-CC-DD-EE-FF") == "Vendor Corporation"

    def test_oui_file_missing_returns_none(self, tmp_path: pytest.TempPathFactory) -> None:
        """Missing manuf file means all lookups return None (no crash)."""
        from netsentry.scanner.oui import OuiDatabase

        db = OuiDatabase(str(tmp_path / "nonexistent_manuf"))  # type: ignore[operator]
        assert db.lookup("aa:bb:cc:dd:ee:ff") is None

    def test_oui_ignores_comment_lines(self, tmp_path: pytest.TempPathFactory) -> None:
        """Comment lines starting with # are ignored."""
        from netsentry.scanner.oui import OuiDatabase

        manuf_file = tmp_path / "manuf"  # type: ignore[operator]
        manuf_file.write_text("# This is a comment\n\nAA:BB:CC\tVendorCorp\tVendor Corporation\n")
        db = OuiDatabase(str(manuf_file))
        assert db.lookup("aa:bb:cc:00:00:00") == "Vendor Corporation"


# ── Scan profiles ─────────────────────────────────────────────────────────────


class TestScanProfiles:
    def test_quick_profile_tools(self) -> None:
        """Quick profile only includes ARP and ICMP."""
        from netsentry.scanner.profiles import ScanProfile, get_profile_tools

        tools = get_profile_tools(ScanProfile.QUICK)
        assert "arp" in tools
        assert "icmp" in tools
        assert "tcp" not in tools
        assert "os" not in tools

    def test_standard_profile_tools(self) -> None:
        """Standard profile includes ARP, ICMP, and TCP port scan."""
        from netsentry.scanner.profiles import ScanProfile, get_profile_tools

        tools = get_profile_tools(ScanProfile.STANDARD)
        assert "arp" in tools
        assert "icmp" in tools
        assert "tcp" in tools
        assert "os" not in tools

    def test_deep_profile_tools(self) -> None:
        """Deep profile includes all tools including OS fingerprint."""
        from netsentry.scanner.profiles import ScanProfile, get_profile_tools

        tools = get_profile_tools(ScanProfile.DEEP)
        assert "arp" in tools
        assert "icmp" in tools
        assert "tcp" in tools
        assert "os" in tools

    def test_profile_from_string(self) -> None:
        """ScanProfile can be created from string."""
        from netsentry.scanner.profiles import ScanProfile

        assert ScanProfile.from_str("quick") == ScanProfile.QUICK
        assert ScanProfile.from_str("standard") == ScanProfile.STANDARD
        assert ScanProfile.from_str("deep") == ScanProfile.DEEP

    def test_profile_from_invalid_string_raises(self) -> None:
        """Invalid profile string raises ValueError."""
        from netsentry.scanner.profiles import ScanProfile

        with pytest.raises(ValueError, match="Invalid scan profile"):
            ScanProfile.from_str("turbo")


# ── Scan orchestrator ─────────────────────────────────────────────────────────


class TestScanOrchestrator:
    @pytest.fixture
    def db_path(self, tmp_path: pytest.TempPathFactory) -> str:
        return str(tmp_path / "test.db")  # type: ignore[operator]

    @pytest.fixture
    async def orchestrator(self, db_path: str, tmp_path: pytest.TempPathFactory):  # type: ignore[no-untyped-def]
        from netsentry.db.connection import get_connection, run_migrations
        from netsentry.scanner.orchestrator import ScanOrchestrator
        from netsentry.scanner.oui import OuiDatabase

        manuf_file = tmp_path / "manuf"  # type: ignore[operator]
        manuf_file.write_text("AA:BB:CC\tVendorCorp\tVendor Corporation\n")

        run_migrations(db_path)
        conn = await get_connection(db_path)
        oui_db = OuiDatabase(str(manuf_file))
        orch = ScanOrchestrator(conn=conn, oui_db=oui_db, subnets=["192.168.1.0/24"])
        yield orch
        await conn.close()

    @pytest.mark.asyncio
    async def test_new_device_added_to_inventory(self, orchestrator) -> None:  # type: ignore[no-untyped-def]
        """New device from ARP sweep is created in devices table."""
        from netsentry.scanner.models import DiscoveredHost
        from netsentry.scanner.profiles import ScanProfile

        discovered = [DiscoveredHost(ip="192.168.1.10", mac="aa:bb:cc:dd:ee:ff")]

        with (
            patch("netsentry.scanner.orchestrator.arp_sweep", new_callable=AsyncMock) as mock_arp,
            patch("netsentry.scanner.orchestrator.icmp_sweep", new_callable=AsyncMock) as mock_icmp,
        ):
            mock_arp.return_value = discovered
            mock_icmp.return_value = []
            await orchestrator.run_scan(ScanProfile.QUICK)

        from netsentry.db.repositories.devices import DeviceRepository

        repo = DeviceRepository(orchestrator._conn)
        device = await repo.get("aa:bb:cc:dd:ee:ff")
        assert device is not None
        assert device.current_ip == "192.168.1.10"
        assert device.is_online is True

    @pytest.mark.asyncio
    async def test_new_device_creates_event(self, orchestrator) -> None:  # type: ignore[no-untyped-def]
        """New device triggers a device.new event."""
        from netsentry.scanner.models import DiscoveredHost
        from netsentry.scanner.profiles import ScanProfile

        discovered = [DiscoveredHost(ip="192.168.1.10", mac="aa:bb:cc:dd:ee:ff")]

        with (
            patch("netsentry.scanner.orchestrator.arp_sweep", new_callable=AsyncMock) as mock_arp,
            patch("netsentry.scanner.orchestrator.icmp_sweep", new_callable=AsyncMock) as mock_icmp,
        ):
            mock_arp.return_value = discovered
            mock_icmp.return_value = []
            await orchestrator.run_scan(ScanProfile.QUICK)

        from netsentry.db.repositories.events import EventRepository

        repo = EventRepository(orchestrator._conn)
        events = await repo.list_for_device("aa:bb:cc:dd:ee:ff")
        assert any(e.event_type == "device.new" for e in events)

    @pytest.mark.asyncio
    async def test_device_marked_offline_after_threshold(self, orchestrator) -> None:  # type: ignore[no-untyped-def]
        """Device missing for N consecutive scans is marked offline."""
        from netsentry.scanner.models import DiscoveredHost
        from netsentry.scanner.profiles import ScanProfile

        # First scan — device online
        with (
            patch("netsentry.scanner.orchestrator.arp_sweep", new_callable=AsyncMock) as mock_arp,
            patch("netsentry.scanner.orchestrator.icmp_sweep", new_callable=AsyncMock) as mock_icmp,
        ):
            mock_arp.return_value = [DiscoveredHost(ip="192.168.1.10", mac="aa:bb:cc:dd:ee:ff")]
            mock_icmp.return_value = []
            await orchestrator.run_scan(ScanProfile.QUICK)

        # Five more scans — device absent from ARP and ping (5 = offline threshold)
        with (
            patch("netsentry.scanner.orchestrator.arp_sweep", new_callable=AsyncMock) as mock_arp,
            patch("netsentry.scanner.orchestrator.icmp_sweep", new_callable=AsyncMock) as mock_icmp,
            patch(
                "netsentry.scanner.orchestrator.ping_hosts_batch", new_callable=AsyncMock
            ) as mock_ping,
        ):
            mock_arp.return_value = []
            mock_icmp.return_value = []
            mock_ping.return_value = {"192.168.1.10": (False, None)}
            for _ in range(8):
                await orchestrator.run_scan(ScanProfile.QUICK)

        from netsentry.db.repositories.devices import DeviceRepository

        repo = DeviceRepository(orchestrator._conn)
        device = await repo.get("aa:bb:cc:dd:ee:ff")
        assert device is not None
        assert device.is_online is False

    @pytest.mark.asyncio
    async def test_device_online_event_on_reappearance(self, orchestrator) -> None:  # type: ignore[no-untyped-def]
        """Device that reappears after being offline gets device.online event."""
        from netsentry.scanner.models import DiscoveredHost
        from netsentry.scanner.profiles import ScanProfile

        # Scan 1: online
        with (
            patch("netsentry.scanner.orchestrator.arp_sweep", new_callable=AsyncMock) as mock_arp,
            patch("netsentry.scanner.orchestrator.icmp_sweep", new_callable=AsyncMock) as mock_icmp,
        ):
            mock_arp.return_value = [DiscoveredHost(ip="192.168.1.10", mac="aa:bb:cc:dd:ee:ff")]
            mock_icmp.return_value = []
            await orchestrator.run_scan(ScanProfile.QUICK)

        # Scans 2-6: offline threshold hit (ARP miss + ping fails)
        with (
            patch("netsentry.scanner.orchestrator.arp_sweep", new_callable=AsyncMock) as mock_arp,
            patch("netsentry.scanner.orchestrator.icmp_sweep", new_callable=AsyncMock) as mock_icmp,
            patch(
                "netsentry.scanner.orchestrator.ping_hosts_batch", new_callable=AsyncMock
            ) as mock_ping,
        ):
            mock_arp.return_value = []
            mock_icmp.return_value = []
            mock_ping.return_value = {"192.168.1.10": (False, None)}
            for _ in range(8):
                await orchestrator.run_scan(ScanProfile.QUICK)

        # Scan 4: device back
        with (
            patch("netsentry.scanner.orchestrator.arp_sweep", new_callable=AsyncMock) as mock_arp,
            patch("netsentry.scanner.orchestrator.icmp_sweep", new_callable=AsyncMock) as mock_icmp,
        ):
            mock_arp.return_value = [DiscoveredHost(ip="192.168.1.10", mac="aa:bb:cc:dd:ee:ff")]
            mock_icmp.return_value = []
            await orchestrator.run_scan(ScanProfile.QUICK)

        from netsentry.db.repositories.events import EventRepository

        repo = EventRepository(orchestrator._conn)
        events = await repo.list_for_device("aa:bb:cc:dd:ee:ff")
        event_types = [e.event_type for e in events]
        assert "device.online" in event_types

    @pytest.mark.asyncio
    async def test_device_stays_online_if_ping_succeeds(self, orchestrator) -> None:  # type: ignore[no-untyped-def]
        """Device missing from ARP but responding to ping stays online — not marked offline."""
        from netsentry.scanner.models import DiscoveredHost
        from netsentry.scanner.profiles import ScanProfile

        # Scan 1: device seen via ARP
        with (
            patch("netsentry.scanner.orchestrator.arp_sweep", new_callable=AsyncMock) as mock_arp,
            patch("netsentry.scanner.orchestrator.icmp_sweep", new_callable=AsyncMock) as mock_icmp,
        ):
            mock_arp.return_value = [DiscoveredHost(ip="192.168.1.10", mac="aa:bb:cc:dd:ee:ff")]
            mock_icmp.return_value = []
            await orchestrator.run_scan(ScanProfile.QUICK)

        # Scans 2-6: device absent from ARP but RESPONDS to ping (e.g. sleeping phone)
        with (
            patch("netsentry.scanner.orchestrator.arp_sweep", new_callable=AsyncMock) as mock_arp,
            patch("netsentry.scanner.orchestrator.icmp_sweep", new_callable=AsyncMock) as mock_icmp,
            patch(
                "netsentry.scanner.orchestrator.ping_hosts_batch", new_callable=AsyncMock
            ) as mock_ping,
        ):
            mock_arp.return_value = []
            mock_icmp.return_value = []
            mock_ping.return_value = {"192.168.1.10": (True, 1.2)}  # alive!
            for _ in range(6):
                await orchestrator.run_scan(ScanProfile.QUICK)

        from netsentry.db.repositories.devices import DeviceRepository
        from netsentry.db.repositories.events import EventRepository

        device_repo = DeviceRepository(orchestrator._conn)
        device = await device_repo.get("aa:bb:cc:dd:ee:ff")
        assert device is not None
        assert device.is_online is True  # should NOT have been marked offline

        event_repo = EventRepository(orchestrator._conn)
        events = await event_repo.list_for_device("aa:bb:cc:dd:ee:ff")
        assert not any(e.event_type == "device.offline" for e in events)

    @pytest.mark.asyncio
    async def test_oui_vendor_resolved_for_new_device(self, orchestrator) -> None:  # type: ignore[no-untyped-def]
        """OUI vendor is looked up and stored on new device."""
        from netsentry.scanner.models import DiscoveredHost
        from netsentry.scanner.profiles import ScanProfile

        with (
            patch("netsentry.scanner.orchestrator.arp_sweep", new_callable=AsyncMock) as mock_arp,
            patch("netsentry.scanner.orchestrator.icmp_sweep", new_callable=AsyncMock) as mock_icmp,
        ):
            mock_arp.return_value = [DiscoveredHost(ip="192.168.1.10", mac="aa:bb:cc:dd:ee:ff")]
            mock_icmp.return_value = []
            await orchestrator.run_scan(ScanProfile.QUICK)

        from netsentry.db.repositories.devices import DeviceRepository

        repo = DeviceRepository(orchestrator._conn)
        device = await repo.get("aa:bb:cc:dd:ee:ff")
        assert device is not None
        assert device.vendor == "Vendor Corporation"

    @pytest.mark.asyncio
    async def test_quick_profile_does_not_call_tcp_scan(self, orchestrator) -> None:  # type: ignore[no-untyped-def]
        """Quick profile only calls ARP and ICMP — no TCP probe."""
        from netsentry.scanner.profiles import ScanProfile

        with (
            patch("netsentry.scanner.orchestrator.arp_sweep", new_callable=AsyncMock) as mock_arp,
            patch("netsentry.scanner.orchestrator.icmp_sweep", new_callable=AsyncMock) as mock_icmp,
            patch(
                "netsentry.scanner.orchestrator.tcp_syn_probe", new_callable=AsyncMock
            ) as mock_tcp,
        ):
            mock_arp.return_value = []
            mock_icmp.return_value = []
            await orchestrator.run_scan(ScanProfile.QUICK)

        mock_tcp.assert_not_called()

    @pytest.mark.asyncio
    async def test_scan_run_recorded(self, orchestrator) -> None:  # type: ignore[no-untyped-def]
        """A scan_run record is created for each scan."""
        from netsentry.scanner.profiles import ScanProfile

        with (
            patch("netsentry.scanner.orchestrator.arp_sweep", new_callable=AsyncMock) as mock_arp,
            patch("netsentry.scanner.orchestrator.icmp_sweep", new_callable=AsyncMock) as mock_icmp,
        ):
            mock_arp.return_value = []
            mock_icmp.return_value = []
            await orchestrator.run_scan(ScanProfile.QUICK)

        from netsentry.db.repositories.scan_runs import ScanRunRepository

        repo = ScanRunRepository(orchestrator._conn)
        latest = await repo.get_latest()
        assert latest is not None
        assert latest.completed_at is not None


# ── APScheduler integration ───────────────────────────────────────────────────


class TestScheduler:
    def test_scheduler_creates_arp_job(self) -> None:
        """Scheduler registers ARP scan job on startup."""
        from netsentry.core.scheduler import NetSentryScheduler

        scheduler = NetSentryScheduler()
        mock_orchestrator = MagicMock()
        scheduler.register_scan_jobs(mock_orchestrator, arp_interval=300)

        job_ids = [job.id for job in scheduler.get_jobs()]
        assert "scan_arp" in job_ids

    def test_scheduler_creates_port_scan_job(self) -> None:
        """Scheduler registers TCP port scan job on startup."""
        from netsentry.core.scheduler import NetSentryScheduler

        scheduler = NetSentryScheduler()
        mock_orchestrator = MagicMock()
        scheduler.register_scan_jobs(mock_orchestrator, arp_interval=300, port_interval=900)

        job_ids = [job.id for job in scheduler.get_jobs()]
        assert "scan_ports" in job_ids

    @pytest.mark.asyncio
    async def test_scheduler_starts_and_stops(self) -> None:
        """Scheduler starts and shuts down without error."""
        from netsentry.core.scheduler import NetSentryScheduler

        scheduler = NetSentryScheduler()
        scheduler.start()
        assert scheduler.running is True
        # shutdown(wait=False) is non-blocking; just verify no exception raised
        scheduler.shutdown(wait=False)
