"""
NetSentry database connection layer.

Provides:
- get_connection(): async SQLite connection with WAL mode enabled
- run_migrations(): runs Alembic upgrade head synchronously at startup
"""

from __future__ import annotations

import logging
import os

import aiosqlite

logger = logging.getLogger(__name__)


async def get_connection(db_path: str) -> aiosqlite.Connection:
    """
    Open an async SQLite connection with WAL mode and sensible pragmas.

    Args:
        db_path: Path to the SQLite database file, or ":memory:" for tests.

    Returns:
        An open aiosqlite.Connection. Caller is responsible for closing it.
    """
    conn = await aiosqlite.connect(db_path)
    conn.row_factory = aiosqlite.Row

    # Enable WAL mode for better concurrent read performance
    await conn.execute("PRAGMA journal_mode=WAL")
    # Disable foreign key enforcement at DB level — enforced in repository layer
    await conn.execute("PRAGMA foreign_keys=OFF")
    # Faster writes: synchronous=NORMAL is safe with WAL mode
    await conn.execute("PRAGMA synchronous=NORMAL")

    await conn.commit()
    return conn


def run_migrations(db_path: str) -> None:
    """
    Run Alembic migrations synchronously.

    Called at application startup (in FastAPI lifespan) before accepting
    requests. Idempotent — safe to call on every startup.

    Args:
        db_path: Path to the SQLite database file.
    """
    from alembic.config import Config

    from alembic import command

    # Find alembic.ini relative to this file's package root
    package_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    alembic_ini = os.path.join(package_root, "alembic.ini")

    if not os.path.exists(alembic_ini):
        logger.warning("alembic.ini not found at %s — skipping migrations", alembic_ini)
        return

    cfg = Config(alembic_ini)
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")

    logger.info("Running database migrations (db=%s)", db_path)
    command.upgrade(cfg, "head")
    logger.info("Database migrations complete")
