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
from netsentry.monitor.ping import ping_hosts_batch
from netsentry.notifications.registry import notify
from netsentry.scanner.arp import arp_sweep
from netsentry.scanner.icmp import icmp_sweep
from netsentry.scanner.models import DiscoveredHost
from netsentry.scanner.netbios import netbios_scan
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
        offline_threshold: int = 8,
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
                    if not any(d.ip == h.ip for d in discovered.values()):
                        discovered[h.ip] = h

        # ── Port scan (STANDARD+) ──────────────────────────────────────────
        # Run TCP SYN probe on all discovered hosts and build ip→ports map
        port_results: dict[str, list[int]] = {}  # ip → open_ports
        if "tcp" in tools and discovered:
            ips = [h.ip for h in discovered.values() if h.ip]
            scan_results = await tcp_syn_probe(ips)
            for r in scan_results:
                if r.open_ports:
                    port_results[r.ip] = r.open_ports
            if port_results:
                logger.info(
                    "Port scan: %d/%d hosts have open ports",
                    len(port_results),
                    len(ips),
                )

        # ── NetBIOS name resolution (STANDARD+) ───────────────────────────
        netbios_results: dict[str, str] = {}  # ip → name
        if "tcp" in tools and discovered:
            ips = [h.ip for h in discovered.values() if h.ip]
            nb_hosts = await netbios_scan(ips)
            for nb in nb_hosts:
                if nb.hostname and nb.ip:
                    netbios_results[nb.ip] = nb.hostname
            if netbios_results:
                logger.info("NetBIOS: resolved %d hostnames", len(netbios_results))

        # ── Inventory update phase ─────────────────────────────────────────
        seen_macs: set[str] = set()
        for _key, host in discovered.items():
            if host.mac is None:
                continue
            seen_macs.add(host.mac)
            vendor = self._oui_db.lookup(host.mac)
            existing = await self._devices.get(host.mac)

            # Prefer NetBIOS hostname over ARP hostname
            hostname = host.hostname or netbios_results.get(host.ip or "") or None

            if existing is None:
                # Brand new device
                await self._devices.upsert(
                    mac=host.mac,
                    ip=host.ip,
                    hostname=hostname,
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
                    hostname=hostname,
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
                    hostname=hostname or existing.hostname,
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

            # ── Enrich: store port scan results ───────────────────────────
            open_ports = port_results.get(host.ip or "", [])
            if open_ports or (host.ip and host.ip in port_results):
                await self._devices.enrich(
                    mac=host.mac,
                    open_ports=open_ports,
                    mark_port_scan=True,
                )

            # ── Enrich: run device identification with ports ───────────────
            # Feed vendor + hostname + open_ports into the rule engine
            if open_ports or vendor or hostname:
                from netsentry.identification.rules import identify_by_rules

                result = identify_by_rules(
                    vendor=vendor or existing.vendor if existing else vendor,
                    hostname=hostname or (existing.hostname if existing else None),
                    open_ports=open_ports,
                )
                if result.category and result.confidence >= 0.6:
                    existing_now = await self._devices.get(host.mac)
                    # Don't overwrite manually-set category
                    if existing_now and not existing_now.category:
                        await self._devices.patch(
                            mac=host.mac,
                            category=result.category,
                            device_type=result.device_type,
                        )

        # ── OS fingerprinting (DEEP profile only) ─────────────────────────
        if "os" in tools:
            from netsentry.scanner.os_detect import os_fingerprint

            fingerprint_targets = [
                host
                for host in discovered.values()
                if host.mac and host.ip and port_results.get(host.ip or "")
            ]
            logger.info("OS fingerprinting %d hosts with open ports", len(fingerprint_targets))
            for host in fingerprint_targets:
                fp = await os_fingerprint(host.ip or "")
                if fp and fp.confidence >= 0.7:
                    await self._devices.enrich(
                        mac=host.mac or "",
                        os_family=fp.os_family,
                        os_version=fp.os_version,
                        mark_os_scan=True,
                    )
                    logger.debug(
                        "OS detected for %s: %s %s (%.0f%%)",
                        host.mac,
                        fp.os_family,
                        fp.os_version or "",
                        fp.confidence * 100,
                    )

        # ── Offline detection phase ────────────────────────────────────────
        # For every online device not seen in the ARP scan, do a direct
        # ICMP ping to its last known IP before marking it offline.
        # ARP misses are common (sleeping phones, power-saving devices, DHCP
        # renewal gaps) — ICMP confirms whether the device is truly unreachable.
        all_active = await self._devices.list(lifecycle="active")
        offline_candidates = [
            d for d in all_active if d.mac_address not in seen_macs and d.is_online and d.current_ip
        ]

        if offline_candidates:
            # Batch-ping all candidates in one fping call
            candidate_ips = {d.current_ip: d for d in offline_candidates if d.current_ip}
            ping_results = await ping_hosts_batch(list(candidate_ips.keys()), timeout=10.0)

            for device in offline_candidates:
                ip = device.current_ip
                alive, _ = ping_results.get(ip, (False, None)) if ip else (False, None)

                if alive:
                    # Device responds to ping — it's online, reset miss counter
                    self._missed_cycles[device.mac_address] = 0
                    logger.debug(
                        "Device %s (%s) missed ARP but responded to ping — still online",
                        device.mac_address,
                        ip,
                    )
                    continue

                # Neither ARP nor ping — increment missed counter
                self._missed_cycles[device.mac_address] += 1
                if self._missed_cycles[device.mac_address] >= self._offline_threshold:
                    await self._devices.set_offline(device.mac_address)
                    await self._events.create(
                        mac_address=device.mac_address,
                        event_type="device.offline",
                        severity="high",
                        details={"last_ip": device.current_ip},
                    )
                    if device.alerts_enabled:
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
                    logger.info(
                        "Device offline (missed ARP + ping x%d): %s (%s)",
                        self._missed_cycles[device.mac_address],
                        device.mac_address,
                        device.current_ip,
                    )
        else:
            # No candidates — also check devices without IPs
            for device in all_active:
                no_ip = not device.current_ip
                if device.mac_address not in seen_macs and device.is_online and no_ip:
                    self._missed_cycles[device.mac_address] += 1
                    if self._missed_cycles[device.mac_address] >= self._offline_threshold:
                        await self._devices.set_offline(device.mac_address)
                        await self._events.create(
                            mac_address=device.mac_address,
                            event_type="device.offline",
                            severity="high",
                            details={"last_ip": None},
                        )

        # ── Finalise scan run ──────────────────────────────────────────────
        await self._scans.complete(run_id, devices_found=len(seen_macs))
        logger.info("Scan complete (run_id=%d, devices=%d)", run_id, len(seen_macs))
        return len(seen_macs)
