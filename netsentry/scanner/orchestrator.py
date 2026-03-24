"""
NetSentry Scan Orchestrator.

Coordinates all scanner tools, writes results to the device inventory,
manages the online/offline state machine, and emits events.
"""

from __future__ import annotations

import logging
from collections import defaultdict

import aiosqlite

from netsentry.db.repositories.devices import DeviceRepository
from netsentry.db.repositories.events import EventRepository
from netsentry.db.repositories.ip_assignments import IpAssignmentRepository
from netsentry.db.repositories.scan_runs import ScanRunRepository
from netsentry.notifications.registry import notify
from netsentry.scanner.arp import arp_sweep
from netsentry.scanner.icmp import icmp_sweep
from netsentry.scanner.models import DiscoveredHost
from netsentry.scanner.oui import OuiDatabase
from netsentry.scanner.profiles import ScanProfile, get_profile_tools
from netsentry.scanner.tcp import tcp_syn_probe

logger = logging.getLogger(__name__)


class ScanOrchestrator:
    """
    Coordinates all scanner tools for a single scan run.

    Responsibilities:
    - Run the correct tools for the requested profile
    - Merge discovered hosts with the device inventory
    - Resolve OUI vendor for new devices
    - Track missed scan cycles and mark devices offline
    - Emit device.new / device.offline / device.online events
    - Record scan_run metadata
    """

    def __init__(
        self,
        conn: aiosqlite.Connection,
        oui_db: OuiDatabase,
        subnets: list[str],
        offline_threshold: int = 5,
    ) -> None:
        self._conn = conn
        self._oui_db = oui_db
        self._subnets = subnets
        self._offline_threshold = offline_threshold
        # In-memory missed cycle counter: {mac: consecutive_missed_count}
        # Seeded from DB on first scan to survive container restarts.
        self._missed_cycles: dict[str, int] = defaultdict(int)
        self._cycles_seeded = False

        self._devices = DeviceRepository(conn)
        self._ip_repo = IpAssignmentRepository(conn)
        self._events = EventRepository(conn)
        self._scans = ScanRunRepository(conn)

    async def _seed_missed_cycles(self) -> None:
        """
        Pre-populate _missed_cycles from the database on first scan after
        a restart so we don't fire false offline events for devices that
        were simply not seen during the first post-restart scan.

        Strategy: any device that was already offline in the DB starts at
        the threshold (already marked offline, no double-firing). Any device
        that was online starts at 0. This is conservative — we require a
        fresh run of consecutive misses before firing device.offline.
        """
        all_active = await self._devices.list(lifecycle="active")
        for device in all_active:
            if not device.is_online:
                # Already marked offline — don't re-fire
                self._missed_cycles[device.mac_address] = self._offline_threshold
            else:
                self._missed_cycles[device.mac_address] = 0
        self._cycles_seeded = True
        logger.info(
            "Seeded missed_cycles for %d devices (%d already offline)",
            len(all_active),
            sum(1 for d in all_active if not d.is_online),
        )

    async def run_scan(self, profile: ScanProfile = ScanProfile.STANDARD) -> int:
        """
        Execute a full scan cycle for the given profile.

        Returns the number of devices discovered.
        """
        if not self._cycles_seeded:
            await self._seed_missed_cycles()

        run_id = await self._scans.start(scan_type=profile.value, profile=profile.value)
        tools = get_profile_tools(profile)
        logger.info(
            "Starting %s scan (run_id=%d, subnets=%s)", profile.value, run_id, self._subnets
        )

        # ── Discovery phase ────────────────────────────────────────────────
        discovered: dict[str, DiscoveredHost] = {}  # mac -> host

        for subnet in self._subnets:
            if "arp" in tools:
                arp_hosts = await arp_sweep(subnet)
                for h in arp_hosts:
                    if h.mac:
                        discovered[h.mac] = h

            if "icmp" in tools:
                icmp_hosts = await icmp_sweep(subnet)
                for h in icmp_hosts:
                    # ICMP hosts have no MAC — only add if not already seen via ARP
                    if not any(d.ip == h.ip for d in discovered.values()):
                        discovered[h.ip] = h  # use IP as key for MAC-less hosts

            if "tcp" in tools and discovered:
                ips = [h.ip for h in discovered.values()]
                await tcp_syn_probe(ips)  # Results stored in US0008+ device detail

        # ── Inventory update phase ─────────────────────────────────────────
        seen_macs: set[str] = set()
        for _key, host in discovered.items():
            if host.mac is None:
                continue
            seen_macs.add(host.mac)
            vendor = self._oui_db.lookup(host.mac)
            existing = await self._devices.get(host.mac)

            if existing is None:
                # Brand new device
                await self._devices.upsert(
                    mac=host.mac,
                    ip=host.ip,
                    hostname=host.hostname,
                    vendor=vendor,
                    is_online=True,
                )
                await self._ip_repo.upsert(mac=host.mac, ip=host.ip, source=host.source)
                await self._events.create(
                    mac_address=host.mac,
                    event_type="device.new",
                    severity="urgent",
                    details={"ip": host.ip, "vendor": vendor},
                )
                await notify(
                    event_type="device.new",
                    severity="urgent",
                    mac=host.mac,
                    hostname=host.hostname,
                    ip=host.ip,
                    details={"vendor": vendor},
                )
                self._missed_cycles[host.mac] = 0
                logger.info("New device: %s (%s)", host.mac, host.ip)
            else:
                # Existing device — update and check for reappearance
                was_offline = not existing.is_online
                await self._devices.upsert(
                    mac=host.mac,
                    ip=host.ip,
                    hostname=host.hostname or existing.hostname,
                    vendor=vendor or existing.vendor,
                    is_online=True,
                )
                await self._ip_repo.upsert(mac=host.mac, ip=host.ip, source=host.source)
                self._missed_cycles[host.mac] = 0

                if was_offline:
                    await self._events.create(
                        mac_address=host.mac,
                        event_type="device.online",
                        severity="info",
                        details={"ip": host.ip},
                    )
                    logger.info("Device back online: %s", host.mac)

        # ── Offline detection phase ────────────────────────────────────────
        all_active = await self._devices.list(lifecycle="active")
        for device in all_active:
            if device.mac_address in seen_macs:
                continue
            if not device.is_online:
                continue
            self._missed_cycles[device.mac_address] += 1
            if self._missed_cycles[device.mac_address] >= self._offline_threshold:
                await self._devices.set_offline(device.mac_address)
                await self._events.create(
                    mac_address=device.mac_address,
                    event_type="device.offline",
                    severity="high",
                    details={"last_ip": device.current_ip},
                )
                await notify(
                    event_type="device.offline",
                    severity="high",
                    mac=device.mac_address,
                    hostname=device.hostname or device.friendly_name,
                    ip=device.current_ip,
                    details={
                        "last_ip": device.current_ip,
                        "missed_cycles": self._missed_cycles[device.mac_address],
                    },
                )
                logger.info("Device offline: %s", device.mac_address)

        # ── Finalise scan run ──────────────────────────────────────────────
        await self._scans.complete(run_id, devices_found=len(seen_macs))
        logger.info("Scan complete (run_id=%d, devices=%d)", run_id, len(seen_macs))
        return len(seen_macs)
