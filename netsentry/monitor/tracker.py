"""NetSentry availability tracker — records probes and calculates uptime."""

from __future__ import annotations

import logging
from collections import defaultdict

import aiosqlite

from netsentry.db.repositories.devices import DeviceRepository
from netsentry.db.repositories.events import EventRepository
from netsentry.db.utils import to_iso8601, utc_now

logger = logging.getLogger(__name__)

_DEFAULT_OFFLINE_THRESHOLD = 2  # consecutive failures before marking offline


class AvailabilityTracker:
    """
    Records availability probe results and manages online/offline state transitions.

    Emits availability.down when a device crosses the offline threshold.
    Emits availability.up when a device recovers.
    """

    def __init__(
        self,
        conn: aiosqlite.Connection,
        offline_threshold: int = _DEFAULT_OFFLINE_THRESHOLD,
    ) -> None:
        self._conn = conn
        self._offline_threshold = offline_threshold
        self._devices = DeviceRepository(conn)
        self._events = EventRepository(conn)
        # In-memory consecutive failure counter
        self._fail_count: dict[str, int] = defaultdict(int)

    async def record_probe(
        self,
        mac: str,
        ip: str,
        alive: bool,
        rtt_ms: float | None = None,
    ) -> None:
        """
        Record a single availability probe result.

        Updates device online state and emits events on transitions.
        """
        now = to_iso8601(utc_now())

        # Write raw check record
        await self._conn.execute(
            "INSERT INTO availability_checks (mac_address, ip_address, alive, rtt_ms, checked_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (mac, ip, 1 if alive else 0, rtt_ms, now),
        )
        await self._conn.commit()

        device = await self._devices.get(mac)
        if device is None:
            return

        if alive:
            was_offline = not device.is_online
            self._fail_count[mac] = 0
            await self._devices.upsert(mac=mac, ip=ip, is_online=True)

            if was_offline:
                await self._events.create(
                    mac_address=mac,
                    event_type="availability.up",
                    severity="info",
                    details={"ip": ip, "rtt_ms": rtt_ms},
                )
                logger.info("Device %s (%s) is back online", mac, ip)

        else:
            self._fail_count[mac] += 1
            if self._fail_count[mac] >= self._offline_threshold and device.is_online:
                await self._devices.set_offline(mac)
                await self._events.create(
                    mac_address=mac,
                    event_type="availability.down",
                    severity="urgent",
                    details={"ip": ip, "consecutive_failures": self._fail_count[mac]},
                )
                logger.info(
                    "Device %s (%s) offline after %d failures", mac, ip, self._fail_count[mac]
                )

    async def get_uptime_pct(self, mac: str, hours: int = 24) -> float | None:
        """
        Calculate uptime percentage for a device over the last N hours.

        Returns:
            Float 0.0–100.0, or None if no data available.
        """
        from datetime import UTC, datetime, timedelta

        cutoff = to_iso8601(datetime.now(UTC) - timedelta(hours=hours))

        async with self._conn.execute(
            "SELECT COUNT(*) as total, SUM(alive) as alive_count "
            "FROM availability_checks "
            "WHERE mac_address = ? AND checked_at >= ?",
            (mac, cutoff),
        ) as cur:
            row = await cur.fetchone()

        if row is None or int(row["total"]) == 0:
            return None

        return (int(row["alive_count"]) / int(row["total"])) * 100.0

    async def get_avg_rtt(self, mac: str, hours: int = 1) -> float | None:
        """Return average RTT in ms for a device over the last N hours."""
        from datetime import UTC, datetime, timedelta

        cutoff = to_iso8601(datetime.now(UTC) - timedelta(hours=hours))

        async with self._conn.execute(
            "SELECT AVG(rtt_ms) FROM availability_checks "
            "WHERE mac_address = ? AND alive = 1 AND checked_at >= ?",
            (mac, cutoff),
        ) as cur:
            row = await cur.fetchone()

        if row is None or row[0] is None:
            return None
        return float(row[0])
