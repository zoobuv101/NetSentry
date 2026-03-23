"""Alembic migration environment — configured for SQLite."""

from __future__ import annotations

import os
from logging.config import fileConfig

from sqlalchemy import create_engine, pool

from alembic import context

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = None


def get_url() -> str:
    """
    Get the DB URL. Priority:
    1. Value set programmatically via config.set_main_option() (from run_migrations())
    2. DB_PATH environment variable
    3. alembic.ini sqlalchemy.url value
    """
    url = config.get_main_option("sqlalchemy.url")
    if url:
        return url
    db_path = os.environ.get("DB_PATH", "/data/netsentry.db")
    return f"sqlite:///{db_path}"


def run_migrations_offline() -> None:
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    url = get_url()
    connectable = create_engine(url, poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
