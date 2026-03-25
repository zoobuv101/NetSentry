"""NetSentry device repository."""

from __future__ import annotations

import logging
from typing import Any

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
    keys = row.keys() if hasattr(row, "keys") else []

    def _get(col: str, default: object = None) -> object:
        return row[col] if col in keys else default

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
        alerts_enabled=bool(_get("alerts_enabled", 1)),
        first_seen=from_iso8601(row["first_seen"]),
        last_seen=from_iso8601(row["last_seen"]),
        created_at=from_iso8601(row["created_at"]),
        updated_at=from_iso8601(row["updated_at"]),
        open_ports_json=str(_get("open_ports_json", "[]")),
        services_json=str(_get("services_json", "[]")),
        mdns_services_json=str(_get("mdns_services_json", "[]")),
        netbios_name=_get("netbios_name"),  # type: ignore[arg-type]
        ssdp_device_type=_get("ssdp_device_type"),  # type: ignore[arg-type]
        last_port_scan=_get("last_port_scan"),  # type: ignore[arg-type]
        last_os_scan=_get("last_os_scan"),  # type: ignore[arg-type]
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

    async def set_alerts_enabled(self, mac: str, enabled: bool) -> None:
        """Enable or disable notifications for a specific device."""
        mac = normalise_mac(mac)
        await self.execute(
            "UPDATE devices SET alerts_enabled = ?, updated_at = ? WHERE mac_address = ?",
            (1 if enabled else 0, to_iso8601(utc_now()), mac),
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

    async def enrich(
        self,
        mac: str,
        open_ports: list[int] | None = None,  # type: ignore[valid-type]
        services: list[Any] | None = None,  # type: ignore[valid-type]
        os_family: str | None = None,
        os_version: str | None = None,
        netbios_name: str | None = None,
        ssdp_device_type: str | None = None,
        mdns_services: list[str] | None = None,  # type: ignore[valid-type]
        mark_port_scan: bool = False,
        mark_os_scan: bool = False,
    ) -> None:
        """
        Update enrichment fields for a device without touching identity fields.
        Only provided (non-None) values are written.
        """
        import json

        mac = normalise_mac(mac)
        now = to_iso8601(utc_now())

        updates: list[tuple[str, object]] = [("updated_at", now)]

        if open_ports is not None:
            updates.append(("open_ports_json", json.dumps(sorted(open_ports))))
        if services is not None:
            updates.append(("services_json", json.dumps(services)))
        if os_family is not None:
            updates.append(("os_family", os_family))
        if os_version is not None:
            updates.append(("os_version", os_version))
        if netbios_name is not None:
            updates.append(("netbios_name", netbios_name))
        if ssdp_device_type is not None:
            updates.append(("ssdp_device_type", ssdp_device_type))
        if mdns_services is not None:
            updates.append(("mdns_services_json", json.dumps(mdns_services)))
        if mark_port_scan:
            updates.append(("last_port_scan", now))
        if mark_os_scan:
            updates.append(("last_os_scan", now))

        if len(updates) <= 1:
            return  # nothing to write

        set_clause = ", ".join(f"{col} = ?" for col, _ in updates)
        values = [v for _, v in updates] + [mac]
        await self.execute(
            f"UPDATE devices SET {set_clause} WHERE mac_address = ?",  # noqa: S608
            tuple(values),
        )
