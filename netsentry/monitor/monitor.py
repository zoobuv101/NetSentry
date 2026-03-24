"""NetSentry availability monitor — probes monitored devices on a schedule."""

from __future__ import annotations

import logging

import aiosqlite

from netsentry.monitor.ping import ping_hosts_batch
from netsentry.monitor.tracker import AvailabilityTracker

logger = logging.getLogger(__name__)


class AvailabilityMonitor:
    """
    Runs availability probe cycles against all monitored devices.

    A "monitored" device has is_monitored=1 in the devices table.
    Users can toggle monitoring per device via the API.
    """

    def __init__(
        self,
        conn: aiosqlite.Connection,
        offline_threshold: int = 2,
    ) -> None:
        self._conn = conn
        self._tracker = AvailabilityTracker(conn=conn, offline_threshold=offline_threshold)

    async def run_probe_cycle(self) -> int:
        """
        Probe all monitored active devices.

        Returns:
            Number of devices probed.
        """
        # Fetch monitored devices with an IP
        async with self._conn.execute(
            "SELECT mac_address, current_ip FROM devices "
            "WHERE is_monitored = 1 AND lifecycle = 'active' "
            "AND current_ip IS NOT NULL AND current_ip != ''",
        ) as cur:
            rows = await cur.fetchall()

        if not rows:
            return 0

        ip_to_mac: dict[str, str] = {row["current_ip"]: row["mac_address"] for row in rows}
        ips = list(ip_to_mac.keys())

        logger.debug("Probing %d monitored devices", len(ips))
        results = await ping_hosts_batch(ips)

        for ip, (alive, rtt_ms) in results.items():
            mac = ip_to_mac.get(ip)
            if mac:
                await self._tracker.record_probe(mac=mac, ip=ip, alive=alive, rtt_ms=rtt_ms)

        return len(ips)
