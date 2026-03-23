"""
US0003 — TDD tests for SQLite schema, Alembic migration, and DB connection layer.
Tests are written BEFORE implementation per TDD approach.
"""

from __future__ import annotations

import aiosqlite
import pytest


@pytest.fixture
async def db(tmp_path: pytest.TempPathFactory) -> aiosqlite.Connection:
    """Provide a fresh in-memory SQLite connection with migrations applied."""
    from netsentry.db.connection import get_connection, run_migrations

    db_path = str(tmp_path / "test.db")  # type: ignore[operator]
    run_migrations(db_path)
    conn = await get_connection(db_path)
    yield conn  # type: ignore[misc]
    await conn.close()


class TestMigration:
    """AC1–AC3: Alembic migration creates schema correctly."""

    def test_migration_creates_all_tables(self, tmp_path: pytest.TempPathFactory) -> None:
        """All EP0001 tables exist after running migrations."""
        from netsentry.db.connection import run_migrations

        db_path = str(tmp_path / "test.db")  # type: ignore[operator]
        run_migrations(db_path)

        import sqlite3

        conn = sqlite3.connect(db_path)
        tables = {
            row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        conn.close()

        expected = {
            "devices",
            "ip_assignments",
            "events",
            "scan_runs",
            "system_config",
            "tags",
            "device_tags",
            "notifications",
            "deletion_audit_log",
            "alembic_version",
        }
        assert expected.issubset(tables), f"Missing tables: {expected - tables}"

    def test_migration_idempotent(self, tmp_path: pytest.TempPathFactory) -> None:
        """Running migrations twice raises no error."""
        from netsentry.db.connection import run_migrations

        db_path = str(tmp_path / "test.db")  # type: ignore[operator]
        run_migrations(db_path)
        run_migrations(db_path)  # Second run — should be a no-op

    def test_alembic_version_recorded(self, tmp_path: pytest.TempPathFactory) -> None:
        """alembic_version table contains the initial revision ID."""
        from netsentry.db.connection import run_migrations

        db_path = str(tmp_path / "test.db")  # type: ignore[operator]
        run_migrations(db_path)

        import sqlite3

        conn = sqlite3.connect(db_path)
        row = conn.execute("SELECT version_num FROM alembic_version").fetchone()
        conn.close()

        assert row is not None
        assert len(row[0]) > 0  # Non-empty revision ID


class TestDbConnection:
    """AC4, AC6: Async DB connection with WAL mode."""

    @pytest.mark.asyncio
    async def test_get_connection_returns_aiosqlite(self, tmp_path: pytest.TempPathFactory) -> None:
        """get_connection() returns an aiosqlite.Connection."""
        from netsentry.db.connection import get_connection, run_migrations

        db_path = str(tmp_path / "test.db")  # type: ignore[operator]
        run_migrations(db_path)
        conn = await get_connection(db_path)
        assert isinstance(conn, aiosqlite.Connection)
        await conn.close()

    @pytest.mark.asyncio
    async def test_wal_mode_enabled(self, tmp_path: pytest.TempPathFactory) -> None:
        """WAL journal mode is enabled on connection."""
        from netsentry.db.connection import get_connection, run_migrations

        db_path = str(tmp_path / "test.db")  # type: ignore[operator]
        run_migrations(db_path)
        conn = await get_connection(db_path)
        async with conn.execute("PRAGMA journal_mode") as cursor:
            row = await cursor.fetchone()
        await conn.close()

        assert row is not None
        assert row[0] == "wal"

    @pytest.mark.asyncio
    async def test_connection_executes_select(self, tmp_path: pytest.TempPathFactory) -> None:
        """Connection can execute a simple SELECT."""
        from netsentry.db.connection import get_connection, run_migrations

        db_path = str(tmp_path / "test.db")  # type: ignore[operator]
        run_migrations(db_path)
        conn = await get_connection(db_path)
        async with conn.execute("SELECT 1 AS val") as cursor:
            row = await cursor.fetchone()
        await conn.close()

        assert row is not None
        assert row[0] == 1


class TestBaseRepository:
    """AC4: BaseRepository async interface."""

    @pytest.mark.asyncio
    async def test_execute_returns_cursor(self, tmp_path: pytest.TempPathFactory) -> None:
        """BaseRepository.execute() returns a cursor result."""
        from netsentry.db.base import BaseRepository
        from netsentry.db.connection import get_connection, run_migrations

        db_path = str(tmp_path / "test.db")  # type: ignore[operator]
        run_migrations(db_path)
        conn = await get_connection(db_path)
        repo = BaseRepository(conn)
        rows = await repo.fetchall("SELECT name FROM sqlite_master WHERE type='table'")
        await conn.close()

        assert isinstance(rows, list)
        assert len(rows) > 0

    @pytest.mark.asyncio
    async def test_fetchone_returns_none_on_empty(self, tmp_path: pytest.TempPathFactory) -> None:
        """fetchone() returns None when query returns no rows."""
        from netsentry.db.base import BaseRepository
        from netsentry.db.connection import get_connection, run_migrations

        db_path = str(tmp_path / "test.db")  # type: ignore[operator]
        run_migrations(db_path)
        conn = await get_connection(db_path)
        repo = BaseRepository(conn)
        row = await repo.fetchone(
            "SELECT * FROM devices WHERE mac_address = ?", ("ff:ff:ff:ff:ff:ff",)
        )
        await conn.close()

        assert row is None

    @pytest.mark.asyncio
    async def test_execute_insert_and_fetchone(self, tmp_path: pytest.TempPathFactory) -> None:
        """execute() can insert a row; fetchone() retrieves it."""
        from netsentry.db.base import BaseRepository
        from netsentry.db.connection import get_connection, run_migrations

        db_path = str(tmp_path / "test.db")  # type: ignore[operator]
        run_migrations(db_path)
        conn = await get_connection(db_path)
        repo = BaseRepository(conn)

        await repo.execute(
            "INSERT INTO system_config (key, value) VALUES (?, ?)",
            ("test_key", "test_value"),
        )
        row = await repo.fetchone("SELECT value FROM system_config WHERE key = ?", ("test_key",))
        await conn.close()

        assert row is not None
        assert row[0] == "test_value"


class TestDevicesTableSchema:
    """AC5: devices table has correct columns and constraints."""

    def test_devices_table_has_required_columns(self, tmp_path: pytest.TempPathFactory) -> None:
        """devices table contains all required columns."""
        import sqlite3

        from netsentry.db.connection import run_migrations

        db_path = str(tmp_path / "test.db")  # type: ignore[operator]
        run_migrations(db_path)

        conn = sqlite3.connect(db_path)
        cols = {row[1] for row in conn.execute("PRAGMA table_info(devices)")}
        conn.close()

        required = {
            "mac_address",
            "friendly_name",
            "category",
            "subcategory",
            "owner",
            "notes",
            "vendor",
            "device_type",
            "os_family",
            "os_version",
            "current_ip",
            "hostname",
            "lifecycle",
            "connection_type",
            "first_seen",
            "last_seen",
            "is_online",
            "is_monitored",
            "created_at",
            "updated_at",
        }
        assert required.issubset(cols), f"Missing columns: {required - cols}"

    def test_devices_lifecycle_default_is_active(self, tmp_path: pytest.TempPathFactory) -> None:
        """devices.lifecycle DEFAULT is 'active'."""
        import sqlite3

        from netsentry.db.connection import run_migrations

        db_path = str(tmp_path / "test.db")  # type: ignore[operator]
        run_migrations(db_path)

        conn = sqlite3.connect(db_path)
        # Insert minimal device row without specifying lifecycle
        conn.execute(
            "INSERT INTO devices (mac_address, first_seen, last_seen, created_at, updated_at) "
            "VALUES ('aa:bb:cc:dd:ee:ff', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z', "
            "'2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')"
        )
        row = conn.execute(
            "SELECT lifecycle FROM devices WHERE mac_address = 'aa:bb:cc:dd:ee:ff'"
        ).fetchone()
        conn.close()

        assert row is not None
        assert row[0] == "active"

    def test_ip_assignments_table_has_required_columns(
        self, tmp_path: pytest.TempPathFactory
    ) -> None:
        """ip_assignments table has all required columns."""
        import sqlite3

        from netsentry.db.connection import run_migrations

        db_path = str(tmp_path / "test.db")  # type: ignore[operator]
        run_migrations(db_path)

        conn = sqlite3.connect(db_path)
        cols = {row[1] for row in conn.execute("PRAGMA table_info(ip_assignments)")}
        conn.close()

        required = {"id", "mac_address", "ip_address", "source", "first_seen", "last_seen"}
        assert required.issubset(cols)

    def test_events_table_has_required_columns(self, tmp_path: pytest.TempPathFactory) -> None:
        """events table has all required columns."""
        import sqlite3

        from netsentry.db.connection import run_migrations

        db_path = str(tmp_path / "test.db")  # type: ignore[operator]
        run_migrations(db_path)

        conn = sqlite3.connect(db_path)
        cols = {row[1] for row in conn.execute("PRAGMA table_info(events)")}
        conn.close()

        assert {
            "id",
            "mac_address",
            "event_type",
            "severity",
            "details",
            "notification_sent",
            "timestamp",
        }.issubset(cols)
