"""Alembic migration environment — configured for SQLite with aiosqlite."""

from __future__ import annotations

import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# Load the Alembic config object
config = context.config

# Apply logging config from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Substitute DB_PATH env var into the connection URL
db_path = os.environ.get("DB_PATH", "/data/netsentry.db")
config.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")

# Target metadata — None for now; will be set when SQLAlchemy models are added
target_metadata = None


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (no DB connection required)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (with a live DB connection)."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # Enable WAL mode via connection event (set in US0003)
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
