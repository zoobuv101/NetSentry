"""
NetSentry base repository.

All database access goes through repository classes that extend BaseRepository.
This enforces a consistent async interface and keeps SQL out of business logic.
"""

from __future__ import annotations

import logging
from typing import Any

import aiosqlite

logger = logging.getLogger(__name__)


class BaseRepository:
    """
    Async repository base class.

    Wraps an aiosqlite.Connection and provides typed helper methods.
    All database access in NetSentry goes through repository subclasses.
    """

    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn

    async def execute(self, sql: str, params: tuple[Any, ...] = ()) -> aiosqlite.Cursor:
        """Execute a SQL statement (INSERT, UPDATE, DELETE) and commit."""
        cursor = await self._conn.execute(sql, params)
        await self._conn.commit()
        return cursor

    async def executemany(self, sql: str, params_seq: list[tuple[Any, ...]]) -> None:
        """Execute a SQL statement multiple times and commit."""
        await self._conn.executemany(sql, params_seq)
        await self._conn.commit()

    async def fetchone(self, sql: str, params: tuple[Any, ...] = ()) -> aiosqlite.Row | None:
        """Execute a SELECT and return the first row, or None if no rows."""
        async with self._conn.execute(sql, params) as cursor:
            return await cursor.fetchone()

    async def fetchall(self, sql: str, params: tuple[Any, ...] = ()) -> list[aiosqlite.Row]:
        """Execute a SELECT and return all rows as a list."""
        async with self._conn.execute(sql, params) as cursor:
            rows = await cursor.fetchall()
            return list(rows)

    async def fetchscalar(self, sql: str, params: tuple[Any, ...] = ()) -> Any:
        """Execute a SELECT returning a single value (first column of first row)."""
        row = await self.fetchone(sql, params)
        if row is None:
            return None
        return row[0]
