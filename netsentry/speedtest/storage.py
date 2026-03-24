"""NetSentry speed test result storage."""

from __future__ import annotations

import logging

import aiosqlite

from netsentry.db.utils import to_iso8601, utc_now
from netsentry.speedtest.models import SpeedTestResult

logger = logging.getLogger(__name__)


class SpeedTestStorage:
    """Persists speed test results to the speed_tests table."""

    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn

    async def save(self, result: SpeedTestResult) -> None:
        """Write a speed test result to the database."""
        now = to_iso8601(utc_now())
        await self._conn.execute(
            "INSERT INTO speed_tests "
            "(download_mbps, upload_mbps, ping_ms, server, backend, grade, tested_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                result.download_mbps,
                result.upload_mbps,
                result.ping_ms,
                result.server,
                result.backend,
                result.grade,
                now,
            ),
        )
        await self._conn.commit()
        logger.info(
            "Speed test saved: ↓%.1f Mbps ↑%.1f Mbps ping=%.1fms (%s)",
            result.download_mbps,
            result.upload_mbps,
            result.ping_ms,
            result.grade,
        )

    async def get_latest(self) -> SpeedTestResult | None:
        """Return the most recently stored speed test result."""
        async with self._conn.execute(
            "SELECT * FROM speed_tests ORDER BY tested_at DESC LIMIT 1"
        ) as cur:
            row = await cur.fetchone()

        if row is None:
            return None

        return SpeedTestResult(
            download_mbps=float(row["download_mbps"]),
            upload_mbps=float(row["upload_mbps"]),
            ping_ms=float(row["ping_ms"]),
            server=row["server"],
            backend=row["backend"],
            tested_at=row["tested_at"],
        )

    async def get_history(self, limit: int = 30) -> list[SpeedTestResult]:
        """Return the last N speed test results, newest first."""
        async with self._conn.execute(
            "SELECT * FROM speed_tests ORDER BY tested_at DESC LIMIT ?",
            (limit,),
        ) as cur:
            rows = await cur.fetchall()

        return [
            SpeedTestResult(
                download_mbps=float(row["download_mbps"]),
                upload_mbps=float(row["upload_mbps"]),
                ping_ms=float(row["ping_ms"]),
                server=row["server"],
                backend=row["backend"],
                tested_at=row["tested_at"],
            )
            for row in rows
        ]
