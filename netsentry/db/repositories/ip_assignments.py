"""NetSentry IP assignment repository."""

from __future__ import annotations

import logging

import aiosqlite

from netsentry.db.base import BaseRepository
from netsentry.db.models import IpAssignment
from netsentry.db.utils import from_iso8601, normalise_mac, to_iso8601, utc_now

logger = logging.getLogger(__name__)


def _row_to_ip(row: aiosqlite.Row) -> IpAssignment:
    return IpAssignment(
        id=row["id"],
        mac_address=row["mac_address"],
        ip_address=row["ip_address"],
        source=row["source"],
        first_seen=from_iso8601(row["first_seen"]),
        last_seen=from_iso8601(row["last_seen"]),
    )


class IpAssignmentRepository(BaseRepository):
    """Async repository for the ip_assignments table."""

    async def upsert(self, mac: str, ip: str, source: str) -> IpAssignment:
        """
        Insert or update an IP assignment for a device.
        Same MAC + IP pair updates last_seen and source; different IP creates new row.
        """
        mac = normalise_mac(mac)
        now = to_iso8601(utc_now())

        existing = await self.fetchone(
            "SELECT * FROM ip_assignments WHERE mac_address = ? AND ip_address = ?",
            (mac, ip),
        )

        if existing is None:
            await self.execute(
                """
                INSERT INTO ip_assignments (mac_address, ip_address, source, first_seen, last_seen)
                VALUES (?, ?, ?, ?, ?)
                """,
                (mac, ip, source, now, now),
            )
        else:
            await self.execute(
                """
                UPDATE ip_assignments
                SET last_seen = ?, source = ?
                WHERE mac_address = ? AND ip_address = ?
                """,
                (now, source, mac, ip),
            )

        row = await self.fetchone(
            "SELECT * FROM ip_assignments WHERE mac_address = ? AND ip_address = ?",
            (mac, ip),
        )
        assert row is not None
        return _row_to_ip(row)

    async def list_for_device(self, mac: str) -> list[IpAssignment]:
        """Return all IP assignments for a device, newest last_seen first."""
        mac = normalise_mac(mac)
        rows = await self.fetchall(
            "SELECT * FROM ip_assignments WHERE mac_address = ? ORDER BY last_seen DESC",
            (mac,),
        )
        return [_row_to_ip(r) for r in rows]

    async def get_mac_for_ip(self, ip: str) -> str | None:
        """Return the MAC address most recently associated with an IP, or None."""
        row = await self.fetchone(
            "SELECT mac_address FROM ip_assignments WHERE ip_address = ? "
            "ORDER BY last_seen DESC LIMIT 1",
            (ip,),
        )
        return row["mac_address"] if row is not None else None
