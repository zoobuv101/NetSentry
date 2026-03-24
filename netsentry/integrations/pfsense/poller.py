"""pfSense integration poller."""

from __future__ import annotations

import logging
from typing import Protocol

import aiosqlite

from netsentry.db.repositories.devices import DeviceRepository
from netsentry.db.repositories.ip_assignments import IpAssignmentRepository
from netsentry.integrations.pfsense.arp import fetch_arp_table
from netsentry.integrations.pfsense.dhcp import fetch_dhcp_leases
from netsentry.integrations.pfsense.models import ArpEntry, DhcpLease

logger = logging.getLogger(__name__)


class _PfSenseClientProtocol(Protocol):
    async def run_command(self, command: str) -> tuple[str, str]: ...


class PfSensePoller:
    """
    Polls pfSense for ARP table and DHCP leases, enriches device inventory.
    """

    def __init__(
        self,
        client: _PfSenseClientProtocol,
        conn: aiosqlite.Connection,
    ) -> None:
        self._client = client
        self._conn = conn
        self._devices = DeviceRepository(conn)
        self._ip_repo = IpAssignmentRepository(conn)

    async def poll(self) -> None:
        """Execute one poll cycle."""
        try:
            arp_entries = await self._fetch_arp()
            dhcp_leases = await self._fetch_dhcp()
            await self._enrich(arp_entries, dhcp_leases)
            logger.info(
                "pfSense poll OK — %d ARP entries, %d DHCP leases",
                len(arp_entries),
                len(dhcp_leases),
            )
        except Exception as e:
            logger.warning("pfSense poll error: %s", e)

    async def _fetch_arp(self) -> list[ArpEntry]:
        return await fetch_arp_table(self._client)

    async def _fetch_dhcp(self) -> list[DhcpLease]:
        return await fetch_dhcp_leases(self._client)

    async def _enrich(
        self,
        arp_entries: list[ArpEntry],
        dhcp_leases: list[DhcpLease],
    ) -> None:
        """Merge ARP + DHCP data into device inventory."""
        dhcp_by_mac = {lease.mac: lease for lease in dhcp_leases}

        for entry in arp_entries:
            lease = dhcp_by_mac.get(entry.mac)
            hostname = lease.hostname if lease else None
            ip = lease.ip if lease else entry.ip

            existing = await self._devices.get(entry.mac)
            if existing is None:
                await self._devices.upsert(
                    mac=entry.mac,
                    ip=ip,
                    hostname=hostname,
                    is_online=True,
                )
            else:
                await self._devices.upsert(
                    mac=entry.mac,
                    ip=ip,
                    hostname=hostname or existing.hostname,
                    is_online=True,
                )

            await self._ip_repo.upsert(mac=entry.mac, ip=ip, source="pfsense_arp")

        # Enrich hostnames from DHCP for devices not in ARP (offline but known)
        arp_macs = {e.mac for e in arp_entries}
        for lease in dhcp_leases:
            if lease.mac in arp_macs:
                continue
            existing = await self._devices.get(lease.mac)
            if existing and lease.hostname and not existing.hostname:
                await self._devices.upsert(
                    mac=lease.mac,
                    ip=lease.ip,
                    hostname=lease.hostname,
                    is_online=existing.is_online,
                )
                await self._ip_repo.upsert(mac=lease.mac, ip=lease.ip, source="pfsense_dhcp")
