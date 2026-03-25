"""NetSentry event repository."""

from __future__ import annotations

import json
import logging
from typing import Any

import aiosqlite

from netsentry.db.base import BaseRepository
from netsentry.db.models import Event
from netsentry.db.utils import from_iso8601, to_iso8601, utc_now

logger = logging.getLogger(__name__)


def _row_to_event(row: aiosqlite.Row) -> Event:
    return Event(
        id=row["id"],
        mac_address=row["mac_address"],
        event_type=row["event_type"],
        severity=row["severity"],
        details=row["details"],
        notification_sent=bool(row["notification_sent"]),
        timestamp=from_iso8601(row["timestamp"]),
    )


class EventRepository(BaseRepository):
    """Async repository for the events table."""

    async def create(
        self,
        event_type: str,
        severity: str,
        mac_address: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> int:
        """
        Create a new event record. Returns the new event ID.
        mac_address is optional (None for system-level events).
        """
        now = to_iso8601(utc_now())
        details_json = json.dumps(details or {})

        cursor = await self.execute(
            """
            INSERT INTO events (mac_address, event_type, severity, details, timestamp)
            VALUES (?, ?, ?, ?, ?)
            """,
            (mac_address, event_type, severity, details_json, now),
        )
        return cursor.lastrowid  # type: ignore[return-value]

    async def get(self, event_id: int) -> Event | None:
        """Return an event by ID, or None if not found."""
        row = await self.fetchone("SELECT * FROM events WHERE id = ?", (event_id,))
        return _row_to_event(row) if row is not None else None

    async def list_for_device(
        self,
        mac_address: str,
        limit: int = 50,
    ) -> list[Event]:
        """Return events for a device, newest first."""
        rows = await self.fetchall(
            "SELECT * FROM events WHERE mac_address = ? ORDER BY timestamp DESC LIMIT ?",
            (mac_address, limit),
        )
        return [_row_to_event(r) for r in rows]

    async def list_recent(
        self,
        limit: int = 100,
        event_type: str | None = None,
    ) -> list[Event]:
        """Return recent events, optionally filtered by type."""
        if event_type:
            rows = await self.fetchall(
                "SELECT * FROM events WHERE event_type = ? ORDER BY timestamp DESC LIMIT ?",
                (event_type, limit),
            )
        else:
            rows = await self.fetchall(
                "SELECT * FROM events ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            )
        return [_row_to_event(r) for r in rows]

    async def mark_notification_sent(self, event_id: int) -> None:
        """Mark an event's notification as dispatched."""
        await self.execute(
            "UPDATE events SET notification_sent = 1 WHERE id = ?",
            (event_id,),
        )

    async def search(
        self,
        query: str | None = None,
        event_type: str | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> list[Event]:
        """
        Search events joined with device data for cross-field filtering.

        Matches query string against: event_type, mac_address, details JSON,
        device hostname, device friendly_name, device current_ip,
        device netbios_name, device vendor.
        """
        params: list[object] = []
        where: list[str] = []

        if event_type:
            where.append("e.event_type = ?")
            params.append(event_type)

        if query and query.strip():
            q = f"%{query.strip()}%"
            where.append("""(
                e.event_type LIKE ?
                OR e.mac_address LIKE ?
                OR e.details LIKE ?
                OR d.hostname LIKE ?
                OR d.friendly_name LIKE ?
                OR d.current_ip LIKE ?
                OR d.netbios_name LIKE ?
                OR d.vendor LIKE ?
            )""")
            params.extend([q, q, q, q, q, q, q, q])

        where_clause = ("WHERE " + " AND ".join(where)) if where else ""
        params.extend([limit, offset])

        rows = await self.fetchall(
            f"""
            SELECT e.*
            FROM events e
            LEFT JOIN devices d ON e.mac_address = d.mac_address
            {where_clause}
            ORDER BY e.timestamp DESC
            LIMIT ? OFFSET ?
            """,  # noqa: S608
            tuple(params),
        )
        return [_row_to_event(r) for r in rows]

    async def count(
        self,
        query: str | None = None,
        event_type: str | None = None,
    ) -> int:
        """Count events matching the same filters as search()."""
        params: list[object] = []
        where: list[str] = []

        if event_type:
            where.append("e.event_type = ?")
            params.append(event_type)

        if query and query.strip():
            q = f"%{query.strip()}%"
            where.append("""(
                e.event_type LIKE ?
                OR e.mac_address LIKE ?
                OR e.details LIKE ?
                OR d.hostname LIKE ?
                OR d.friendly_name LIKE ?
                OR d.current_ip LIKE ?
                OR d.netbios_name LIKE ?
                OR d.vendor LIKE ?
            )""")
            params.extend([q, q, q, q, q, q, q, q])

        where_clause = ("WHERE " + " AND ".join(where)) if where else ""

        async with self._conn.execute(
            f"""
            SELECT COUNT(*)
            FROM events e
            LEFT JOIN devices d ON e.mac_address = d.mac_address
            {where_clause}
            """,  # noqa: S608
            tuple(params),
        ) as cur:
            row = await cur.fetchone()
        return int(row[0]) if row else 0
