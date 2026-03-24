"""NetSentry device lifecycle management."""

from __future__ import annotations

import logging

import aiosqlite

from netsentry.db.repositories.devices import DeviceRepository
from netsentry.db.utils import to_iso8601, utc_now

logger = logging.getLogger(__name__)

_DEFAULT_ARCHIVE_AFTER_DAYS = 90


class LifecycleManager:
    """
    Manages device lifecycle transitions: active → historic → deleted.

    Provides:
    - archive_device(): manually mark a device historic
    - purge_device(): permanently delete with audit trail
    - auto_archive_stale(): archive devices not seen for N days
    """

    def __init__(
        self,
        conn: aiosqlite.Connection,
        archive_after_days: int = _DEFAULT_ARCHIVE_AFTER_DAYS,
    ) -> None:
        self._conn = conn
        self._archive_after_days = archive_after_days
        self._devices = DeviceRepository(conn)

    async def archive_device(self, mac: str) -> None:
        """
        Mark a device as historic (soft delete).
        The device remains in the database for historical reporting.
        """
        await self._devices.set_lifecycle(mac, "historic")
        logger.info("Archived device %s", mac)

    async def purge_device(self, mac: str) -> None:
        """
        Permanently delete a device and all its related data.

        Writes a deletion_audit_log entry first so the MAC
        can still be referenced in reports after deletion.
        """
        device = await self._devices.get(mac)
        friendly_name = device.friendly_name if device else None

        # Write audit log entry before deleting
        now = to_iso8601(utc_now())
        await self._conn.execute(
            "INSERT INTO deletion_audit_log "
            "(mac_address, deleted_at, friendly_name_at_deletion) VALUES (?, ?, ?)",
            (mac, now, friendly_name),
        )
        await self._conn.commit()

        # Cascade delete
        await self._devices.purge(mac)
        logger.info("Purged device %s (was: %r)", mac, friendly_name)

    async def auto_archive_stale(self) -> int:
        """
        Archive all active devices not seen for more than archive_after_days.

        Returns the count of devices archived.
        """
        from datetime import UTC, datetime, timedelta

        cutoff = datetime.now(UTC) - timedelta(days=self._archive_after_days)
        cutoff_str = to_iso8601(cutoff)

        async with self._conn.execute(
            "SELECT mac_address FROM devices WHERE lifecycle = 'active' AND last_seen < ?",
            (cutoff_str,),
        ) as cur:
            rows = await cur.fetchall()

        count = 0
        for row in rows:
            mac = row["mac_address"] if hasattr(row, "keys") else row[0]
            await self._devices.set_lifecycle(mac, "historic")
            count += 1
            logger.info(
                "Auto-archived stale device %s (not seen for >%d days)",
                mac,
                self._archive_after_days,
            )

        if count:
            logger.info("Auto-archive complete: %d devices archived", count)
        return count
