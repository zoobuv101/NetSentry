"""
US0004 — TDD tests for the Device Repository Layer.
Tests written BEFORE implementation per TDD approach.

Covers: DeviceRepository, IpAssignmentRepository, EventRepository,
ScanRunRepository, and all utility functions (normalise_mac, utc_now, etc.)
"""

from __future__ import annotations

import asyncio

import pytest


@pytest.fixture
def db_path(tmp_path: pytest.TempPathFactory) -> str:
    return str(tmp_path / "test.db")  # type: ignore[operator]


@pytest.fixture
async def repos(db_path: str):  # type: ignore[no-untyped-def]
    """Provide all repository instances against a fresh migrated DB."""
    from netsentry.db.connection import get_connection, run_migrations
    from netsentry.db.repositories.devices import DeviceRepository
    from netsentry.db.repositories.events import EventRepository
    from netsentry.db.repositories.ip_assignments import IpAssignmentRepository
    from netsentry.db.repositories.scan_runs import ScanRunRepository

    run_migrations(db_path)
    conn = await get_connection(db_path)
    yield {
        "devices": DeviceRepository(conn),
        "ip": IpAssignmentRepository(conn),
        "events": EventRepository(conn),
        "scans": ScanRunRepository(conn),
        "conn": conn,
    }
    await conn.close()


# ── MAC normalisation utility ─────────────────────────────────────────────────


class TestMacNormalisation:
    def test_lowercase_colon_passthrough(self) -> None:
        from netsentry.db.utils import normalise_mac

        assert normalise_mac("aa:bb:cc:dd:ee:ff") == "aa:bb:cc:dd:ee:ff"

    def test_uppercase_to_lowercase(self) -> None:
        from netsentry.db.utils import normalise_mac

        assert normalise_mac("AA:BB:CC:DD:EE:FF") == "aa:bb:cc:dd:ee:ff"

    def test_dashes_to_colons(self) -> None:
        from netsentry.db.utils import normalise_mac

        assert normalise_mac("AA-BB-CC-DD-EE-FF") == "aa:bb:cc:dd:ee:ff"

    def test_no_separator(self) -> None:
        from netsentry.db.utils import normalise_mac

        assert normalise_mac("AABBCCDDEEFF") == "aa:bb:cc:dd:ee:ff"

    def test_invalid_mac_raises(self) -> None:
        from netsentry.db.utils import normalise_mac

        with pytest.raises(ValueError, match="Invalid MAC"):
            normalise_mac("not-a-mac")

    def test_too_short_raises(self) -> None:
        from netsentry.db.utils import normalise_mac

        with pytest.raises(ValueError, match="Invalid MAC"):
            normalise_mac("aa:bb:cc")


# ── DeviceRepository ──────────────────────────────────────────────────────────


class TestDeviceRepository:
    @pytest.mark.asyncio
    async def test_upsert_creates_new_device(self, repos: dict) -> None:
        """AC1: upsert() creates a new device row."""
        device = await repos["devices"].upsert(
            mac="AA:BB:CC:DD:EE:FF",
            ip="192.168.1.10",
            hostname="my-laptop",
        )
        assert device.mac_address == "aa:bb:cc:dd:ee:ff"
        assert device.current_ip == "192.168.1.10"
        assert device.hostname == "my-laptop"
        assert device.is_online is True
        assert device.lifecycle == "active"

    @pytest.mark.asyncio
    async def test_upsert_normalises_mac(self, repos: dict) -> None:
        """MAC is stored lowercase colon-separated regardless of input format."""
        await repos["devices"].upsert(mac="AA-BB-CC-DD-EE-FF", ip="192.168.1.1")
        device = await repos["devices"].get("aa:bb:cc:dd:ee:ff")
        assert device is not None
        assert device.mac_address == "aa:bb:cc:dd:ee:ff"

    @pytest.mark.asyncio
    async def test_upsert_updates_last_seen_on_second_call(self, repos: dict) -> None:
        """AC2: second upsert updates last_seen but not first_seen."""
        await repos["devices"].upsert(mac="aa:bb:cc:dd:ee:ff", ip="192.168.1.10")
        first = await repos["devices"].get("aa:bb:cc:dd:ee:ff")
        assert first is not None

        await asyncio.sleep(0.01)  # ensure timestamp difference
        await repos["devices"].upsert(mac="aa:bb:cc:dd:ee:ff", ip="192.168.1.11")
        second = await repos["devices"].get("aa:bb:cc:dd:ee:ff")
        assert second is not None

        assert second.first_seen == first.first_seen
        assert second.last_seen >= first.last_seen
        assert second.current_ip == "192.168.1.11"

    @pytest.mark.asyncio
    async def test_get_returns_none_for_unknown_mac(self, repos: dict) -> None:
        """AC4: get() returns None (not an exception) for unknown MAC."""
        result = await repos["devices"].get("ff:ff:ff:ff:ff:ff")
        assert result is None

    @pytest.mark.asyncio
    async def test_list_returns_only_active_by_default(self, repos: dict) -> None:
        """AC3: list() returns active devices only by default."""
        await repos["devices"].upsert(mac="aa:bb:cc:dd:ee:01", ip="192.168.1.1")
        await repos["devices"].upsert(mac="aa:bb:cc:dd:ee:02", ip="192.168.1.2")
        # Set one to historic
        await repos["devices"].set_lifecycle("aa:bb:cc:dd:ee:02", "historic")

        devices = await repos["devices"].list()
        macs = [d.mac_address for d in devices]
        assert "aa:bb:cc:dd:ee:01" in macs
        assert "aa:bb:cc:dd:ee:02" not in macs

    @pytest.mark.asyncio
    async def test_list_historic_filter(self, repos: dict) -> None:
        """list(lifecycle='historic') returns only historic devices."""
        await repos["devices"].upsert(mac="aa:bb:cc:dd:ee:01", ip="192.168.1.1")
        await repos["devices"].upsert(mac="aa:bb:cc:dd:ee:02", ip="192.168.1.2")
        await repos["devices"].set_lifecycle("aa:bb:cc:dd:ee:02", "historic")

        historic = await repos["devices"].list(lifecycle="historic")
        assert len(historic) == 1
        assert historic[0].mac_address == "aa:bb:cc:dd:ee:02"

    @pytest.mark.asyncio
    async def test_set_lifecycle_updates_field(self, repos: dict) -> None:
        """set_lifecycle() changes the lifecycle field."""
        await repos["devices"].upsert(mac="aa:bb:cc:dd:ee:ff", ip="192.168.1.1")
        await repos["devices"].set_lifecycle("aa:bb:cc:dd:ee:ff", "historic")
        device = await repos["devices"].get("aa:bb:cc:dd:ee:ff")
        assert device is not None
        assert device.lifecycle == "historic"

    @pytest.mark.asyncio
    async def test_set_lifecycle_invalid_raises(self, repos: dict) -> None:
        """Invalid lifecycle value raises ValueError."""
        await repos["devices"].upsert(mac="aa:bb:cc:dd:ee:ff", ip="192.168.1.1")
        with pytest.raises(ValueError, match="lifecycle"):
            await repos["devices"].set_lifecycle("aa:bb:cc:dd:ee:ff", "spaceship")

    @pytest.mark.asyncio
    async def test_set_offline_marks_device_offline(self, repos: dict) -> None:
        """set_offline() sets is_online=False."""
        await repos["devices"].upsert(mac="aa:bb:cc:dd:ee:ff", ip="192.168.1.1")
        await repos["devices"].set_offline("aa:bb:cc:dd:ee:ff")
        device = await repos["devices"].get("aa:bb:cc:dd:ee:ff")
        assert device is not None
        assert device.is_online is False

    @pytest.mark.asyncio
    async def test_patch_updates_metadata_fields(self, repos: dict) -> None:
        """patch() updates category, owner, friendly_name, notes."""
        await repos["devices"].upsert(mac="aa:bb:cc:dd:ee:ff", ip="192.168.1.1")
        await repos["devices"].patch(
            mac="aa:bb:cc:dd:ee:ff",
            friendly_name="Ian's MacBook",
            category="Personal Device",
            subcategory="Laptop",
            owner="Ian",
            notes="Work machine",
        )
        device = await repos["devices"].get("aa:bb:cc:dd:ee:ff")
        assert device is not None
        assert device.friendly_name == "Ian's MacBook"
        assert device.category == "Personal Device"
        assert device.owner == "Ian"

    @pytest.mark.asyncio
    async def test_purge_deletes_device_and_related(self, repos: dict) -> None:
        """purge() removes the device and all related rows."""
        await repos["devices"].upsert(mac="aa:bb:cc:dd:ee:ff", ip="192.168.1.1")
        await repos["ip"].upsert(mac="aa:bb:cc:dd:ee:ff", ip="192.168.1.1", source="scan")
        await repos["events"].create(
            mac_address="aa:bb:cc:dd:ee:ff",
            event_type="device.new",
            severity="info",
        )
        await repos["devices"].purge("aa:bb:cc:dd:ee:ff")

        assert await repos["devices"].get("aa:bb:cc:dd:ee:ff") is None
        ips = await repos["ip"].list_for_device("aa:bb:cc:dd:ee:ff")
        assert len(ips) == 0


# ── IpAssignmentRepository ───────────────────────────────────────────────────


class TestIpAssignmentRepository:
    @pytest.mark.asyncio
    async def test_upsert_creates_assignment(self, repos: dict) -> None:
        """upsert() creates an IP assignment row."""
        await repos["devices"].upsert(mac="aa:bb:cc:dd:ee:ff", ip="192.168.1.1")
        await repos["ip"].upsert(mac="aa:bb:cc:dd:ee:ff", ip="192.168.1.1", source="scan")
        ips = await repos["ip"].list_for_device("aa:bb:cc:dd:ee:ff")
        assert len(ips) == 1
        assert ips[0].ip_address == "192.168.1.1"
        assert ips[0].source == "scan"

    @pytest.mark.asyncio
    async def test_upsert_updates_last_seen_for_same_ip(self, repos: dict) -> None:
        """Second upsert for same MAC+IP updates last_seen, not first_seen."""
        await repos["devices"].upsert(mac="aa:bb:cc:dd:ee:ff", ip="192.168.1.1")
        await repos["ip"].upsert(mac="aa:bb:cc:dd:ee:ff", ip="192.168.1.1", source="scan")
        await asyncio.sleep(0.01)
        await repos["ip"].upsert(mac="aa:bb:cc:dd:ee:ff", ip="192.168.1.1", source="dhcp")

        ips = await repos["ip"].list_for_device("aa:bb:cc:dd:ee:ff")
        # Should still be 1 row (same IP) with updated last_seen
        assert len(ips) == 1
        assert ips[0].last_seen > ips[0].first_seen

    @pytest.mark.asyncio
    async def test_multiple_ips_tracked(self, repos: dict) -> None:
        """Different IPs for same device are stored as separate rows."""
        await repos["devices"].upsert(mac="aa:bb:cc:dd:ee:ff", ip="192.168.1.1")
        await repos["ip"].upsert(mac="aa:bb:cc:dd:ee:ff", ip="192.168.1.1", source="scan")
        await repos["ip"].upsert(mac="aa:bb:cc:dd:ee:ff", ip="192.168.1.50", source="dhcp")

        ips = await repos["ip"].list_for_device("aa:bb:cc:dd:ee:ff")
        assert len(ips) == 2

    @pytest.mark.asyncio
    async def test_get_by_ip_returns_mac(self, repos: dict) -> None:
        """get_mac_for_ip() returns the MAC for a known IP."""
        await repos["devices"].upsert(mac="aa:bb:cc:dd:ee:ff", ip="192.168.1.1")
        await repos["ip"].upsert(mac="aa:bb:cc:dd:ee:ff", ip="192.168.1.1", source="scan")
        mac = await repos["ip"].get_mac_for_ip("192.168.1.1")
        assert mac == "aa:bb:cc:dd:ee:ff"

    @pytest.mark.asyncio
    async def test_get_by_ip_returns_none_for_unknown(self, repos: dict) -> None:
        """get_mac_for_ip() returns None for unknown IP."""
        result = await repos["ip"].get_mac_for_ip("10.0.0.99")
        assert result is None


# ── EventRepository ──────────────────────────────────────────────────────────


class TestEventRepository:
    @pytest.mark.asyncio
    async def test_create_returns_id(self, repos: dict) -> None:
        """AC5: create() returns an integer ID."""
        event_id = await repos["events"].create(
            mac_address="aa:bb:cc:dd:ee:ff",
            event_type="device.new",
            severity="urgent",
            details={"ip": "192.168.1.10"},
        )
        assert isinstance(event_id, int)
        assert event_id > 0

    @pytest.mark.asyncio
    async def test_create_system_event_no_mac(self, repos: dict) -> None:
        """System events (mac_address=None) are stored correctly."""
        event_id = await repos["events"].create(
            mac_address=None,
            event_type="system.startup",
            severity="info",
        )
        assert event_id > 0

    @pytest.mark.asyncio
    async def test_list_for_device_returns_events(self, repos: dict) -> None:
        """list_for_device() returns events for the given MAC."""
        await repos["devices"].upsert(mac="aa:bb:cc:dd:ee:ff", ip="192.168.1.1")
        await repos["events"].create(
            mac_address="aa:bb:cc:dd:ee:ff", event_type="device.new", severity="urgent"
        )
        await repos["events"].create(
            mac_address="aa:bb:cc:dd:ee:ff", event_type="device.offline", severity="high"
        )
        events = await repos["events"].list_for_device("aa:bb:cc:dd:ee:ff")
        assert len(events) == 2

    @pytest.mark.asyncio
    async def test_list_for_device_respects_limit(self, repos: dict) -> None:
        """list_for_device() respects the limit parameter."""
        for _i in range(5):
            await repos["events"].create(
                mac_address="aa:bb:cc:00:00:01",
                event_type="device.new",
                severity="info",
            )
        events = await repos["events"].list_for_device("aa:bb:cc:00:00:01", limit=3)
        assert len(events) == 3

    @pytest.mark.asyncio
    async def test_mark_notification_sent(self, repos: dict) -> None:
        """mark_notification_sent() sets notification_sent=1."""
        event_id = await repos["events"].create(
            mac_address=None, event_type="device.new", severity="info"
        )
        await repos["events"].mark_notification_sent(event_id)
        event = await repos["events"].get(event_id)
        assert event is not None
        assert event.notification_sent is True


# ── ScanRunRepository ─────────────────────────────────────────────────────────


class TestScanRunRepository:
    @pytest.mark.asyncio
    async def test_start_returns_id(self, repos: dict) -> None:
        """AC6: start() returns an integer run ID."""
        run_id = await repos["scans"].start(scan_type="arp", profile="quick")
        assert isinstance(run_id, int)
        assert run_id > 0

    @pytest.mark.asyncio
    async def test_complete_sets_end_and_devices(self, repos: dict) -> None:
        """AC6: complete() sets completed_at and devices_found."""
        run_id = await repos["scans"].start(scan_type="standard", profile="standard")
        await repos["scans"].complete(run_id, devices_found=12)

        run = await repos["scans"].get(run_id)
        assert run is not None
        assert run.devices_found == 12
        assert run.completed_at is not None
        assert run.errors is None

    @pytest.mark.asyncio
    async def test_complete_with_errors(self, repos: dict) -> None:
        """complete() can record an error message."""
        run_id = await repos["scans"].start(scan_type="deep")
        await repos["scans"].complete(run_id, devices_found=0, errors="nmap not found")
        run = await repos["scans"].get(run_id)
        assert run is not None
        assert run.errors == "nmap not found"

    @pytest.mark.asyncio
    async def test_get_latest_returns_most_recent(self, repos: dict) -> None:
        """get_latest() returns the most recently started scan."""
        await repos["scans"].start(scan_type="arp")
        await asyncio.sleep(0.01)
        run_id = await repos["scans"].start(scan_type="standard")
        latest = await repos["scans"].get_latest()
        assert latest is not None
        assert latest.id == run_id
