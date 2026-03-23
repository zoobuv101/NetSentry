"""NetSentry device repository."""

from __future__ import annotations

import logging

import aiosqlite

from netsentry.db.base import BaseRepository
from netsentry.db.models import Device
from netsentry.db.utils import (
    from_iso8601,
    normalise_mac,
    to_iso8601,
    utc_now,
    validate_lifecycle,
)

logger = logging.getLogger(__name__)


def _row_to_device(row: aiosqlite.Row) -> Device:
    return Device(
        mac_address=row["mac_address"],
        friendly_name=row["friendly_name"],
        category=row["category"],
        subcategory=row["subcategory"],
        owner=row["owner"],
        notes=row["notes"],
        vendor=row["vendor"],
        device_type=row["device_type"],
        os_family=row["os_family"],
        os_version=row["os_version"],
        current_ip=row["current_ip"],
        hostname=row["hostname"],
        lifecycle=row["lifecycle"],
        connection_type=row["connection_type"],
        vlan_id=row["vlan_id"],
        firewall_rules_json=row["firewall_rules_json"],
        is_online=bool(row["is_online"]),
        is_monitored=bool(row["is_monitored"]),
        first_seen=from_iso8601(row["first_seen"]),
        last_seen=from_iso8601(row["last_seen"]),
        created_at=from_iso8601(row["created_at"]),
        updated_at=from_iso8601(row["updated_at"]),
    )


class DeviceRepository(BaseRepository):
    """Async repository for the devices table."""

    async def upsert(
        self,
        mac: str,
        ip: str | None = None,
        hostname: str | None = None,
        vendor: str | None = None,
        is_online: bool = True,
    ) -> Device:
        """
        Insert a new device or update last_seen/current_ip if it already exists.
        MAC is normalised before write. first_seen is preserved on update.
        """
        mac = normalise_mac(mac)
        now = to_iso8601(utc_now())

        existing = await self.fetchone("SELECT * FROM devices WHERE mac_address = ?", (mac,))

        if existing is None:
            await self.execute(
                """
                INSERT INTO devices
                    (mac_address, current_ip, hostname, vendor, is_online,
                     lifecycle, first_seen, last_seen, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, 'active', ?, ?, ?, ?)
                """,
                (mac, ip, hostname, vendor, 1 if is_online else 0, now, now, now, now),
            )
        else:
            await self.execute(
                """
                UPDATE devices
                SET current_ip = COALESCE(?, current_ip),
                    hostname   = COALESCE(?, hostname),
                    vendor     = COALESCE(?, vendor),
                    is_online  = ?,
                    last_seen  = ?,
                    updated_at = ?
                WHERE mac_address = ?
                """,
                (ip, hostname, vendor, 1 if is_online else 0, now, now, mac),
            )

        row = await self.fetchone("SELECT * FROM devices WHERE mac_address = ?", (mac,))
        assert row is not None
        return _row_to_device(row)

    async def get(self, mac: str) -> Device | None:
        """Return a Device by MAC address, or None if not found."""
        mac = normalise_mac(mac)
        row = await self.fetchone("SELECT * FROM devices WHERE mac_address = ?", (mac,))
        return _row_to_device(row) if row is not None else None

    async def list(
        self,
        lifecycle: str = "active",
        limit: int = 500,
    ) -> list[Device]:
        """List devices filtered by lifecycle. Default: active only."""
        rows = await self.fetchall(
            "SELECT * FROM devices WHERE lifecycle = ? ORDER BY last_seen DESC LIMIT ?",
            (lifecycle, limit),
        )
        return [_row_to_device(r) for r in rows]

    async def set_lifecycle(self, mac: str, lifecycle: str) -> None:
        """Set lifecycle state. Raises ValueError for invalid values."""
        mac = normalise_mac(mac)
        validate_lifecycle(lifecycle)
        now = to_iso8601(utc_now())
        await self.execute(
            "UPDATE devices SET lifecycle = ?, updated_at = ? WHERE mac_address = ?",
            (lifecycle, now, mac),
        )

    async def set_offline(self, mac: str) -> None:
        """Mark a device as offline."""
        mac = normalise_mac(mac)
        now = to_iso8601(utc_now())
        await self.execute(
            "UPDATE devices SET is_online = 0, updated_at = ? WHERE mac_address = ?",
            (now, mac),
        )

    async def patch(
        self,
        mac: str,
        friendly_name: str | None = None,
        category: str | None = None,
        subcategory: str | None = None,
        owner: str | None = None,
        notes: str | None = None,
        os_family: str | None = None,
        os_version: str | None = None,
        vendor: str | None = None,
        device_type: str | None = None,
        connection_type: str | None = None,
    ) -> None:
        """Update user-editable metadata fields. None values are ignored."""
        mac = normalise_mac(mac)
        now = to_iso8601(utc_now())

        # Build dynamic SET clause for non-None fields only
        fields: list[tuple[str, object]] = [("updated_at", now)]
        for col, val in [
            ("friendly_name", friendly_name),
            ("category", category),
            ("subcategory", subcategory),
            ("owner", owner),
            ("notes", notes),
            ("os_family", os_family),
            ("os_version", os_version),
            ("vendor", vendor),
            ("device_type", device_type),
            ("connection_type", connection_type),
        ]:
            if val is not None:
                fields.append((col, val))

        set_clause = ", ".join(f"{col} = ?" for col, _ in fields)
        params = tuple(val for _, val in fields) + (mac,)
        await self.execute(
            f"UPDATE devices SET {set_clause} WHERE mac_address = ?",  # noqa: S608
            params,
        )

    async def purge(self, mac: str) -> None:
        """
        Permanently delete a device and ALL related rows.
        Caller is responsible for creating the deletion_audit_log entry.
        """
        mac = normalise_mac(mac)
        # Delete notifications linked to this device's events
        await self.execute(
            """
            DELETE FROM notifications WHERE event_id IN (
                SELECT id FROM events WHERE mac_address = ?
            )
            """,
            (mac,),
        )
        # Delete rows that reference mac_address directly
        for table in ("ip_assignments", "events", "device_tags"):
            await self.execute(
                f"DELETE FROM {table} WHERE mac_address = ?",  # noqa: S608
                (mac,),
            )
        await self.execute("DELETE FROM devices WHERE mac_address = ?", (mac,))
