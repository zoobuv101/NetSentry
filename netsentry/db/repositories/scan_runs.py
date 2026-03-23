"""NetSentry scan run repository."""

from __future__ import annotations

import logging

import aiosqlite

from netsentry.db.base import BaseRepository
from netsentry.db.models import ScanRun
from netsentry.db.utils import from_iso8601, to_iso8601, utc_now

logger = logging.getLogger(__name__)


def _row_to_run(row: aiosqlite.Row) -> ScanRun:
    return ScanRun(
        id=row["id"],
        scan_type=row["scan_type"],
        profile=row["profile"],
        started_at=from_iso8601(row["started_at"]),
        completed_at=from_iso8601(row["completed_at"]) if row["completed_at"] else None,
        devices_found=row["devices_found"],
        errors=row["errors"],
    )


class ScanRunRepository(BaseRepository):
    """Async repository for the scan_runs table."""

    async def start(self, scan_type: str, profile: str | None = None) -> int:
        """Record the start of a scan. Returns the new scan run ID."""
        now = to_iso8601(utc_now())
        cursor = await self.execute(
            "INSERT INTO scan_runs (scan_type, profile, started_at) VALUES (?, ?, ?)",
            (scan_type, profile, now),
        )
        return cursor.lastrowid  # type: ignore[return-value]

    async def complete(
        self,
        run_id: int,
        devices_found: int = 0,
        errors: str | None = None,
    ) -> None:
        """Record scan completion with result counts."""
        now = to_iso8601(utc_now())
        await self.execute(
            """
            UPDATE scan_runs
            SET completed_at = ?, devices_found = ?, errors = ?
            WHERE id = ?
            """,
            (now, devices_found, errors, run_id),
        )

    async def get(self, run_id: int) -> ScanRun | None:
        """Return a scan run by ID, or None if not found."""
        row = await self.fetchone("SELECT * FROM scan_runs WHERE id = ?", (run_id,))
        return _row_to_run(row) if row is not None else None

    async def get_latest(self) -> ScanRun | None:
        """Return the most recently started scan run."""
        row = await self.fetchone("SELECT * FROM scan_runs ORDER BY started_at DESC LIMIT 1")
        return _row_to_run(row) if row is not None else None

    async def list_recent(self, limit: int = 20) -> list[ScanRun]:
        """Return recent scan runs, newest first."""
        rows = await self.fetchall(
            "SELECT * FROM scan_runs ORDER BY started_at DESC LIMIT ?",
            (limit,),
        )
        return [_row_to_run(r) for r in rows]
