"""device_alerts_enabled

Revision ID: 991b8fba38ca
Revises: 02570df1b69f
Create Date: 2026-03-25

Add alerts_enabled column to devices table.
Default 1 (enabled) — existing devices keep getting alerts.
Set to 0 per device to suppress all notifications for that device.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "991b8fba38ca"
down_revision: str | None = "02570df1b69f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("devices") as batch_op:
        batch_op.add_column(
            sa.Column("alerts_enabled", sa.Integer, nullable=False, server_default="1")
        )


def downgrade() -> None:
    with op.batch_alter_table("devices") as batch_op:
        batch_op.drop_column("alerts_enabled")
