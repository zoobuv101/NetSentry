"""availability

Revision ID: b482706ff78e
Revises: e8a6efb57ac6
Create Date: 2026-03-24

US0029: availability_checks table.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b482706ff78e"
down_revision: str | None = "e8a6efb57ac6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "availability_checks",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("mac_address", sa.Text, nullable=False),
        sa.Column("ip_address", sa.Text),
        sa.Column("alive", sa.Integer, nullable=False),
        sa.Column("rtt_ms", sa.Float),
        sa.Column("checked_at", sa.Text, nullable=False),
    )
    op.create_index("idx_avail_mac", "availability_checks", ["mac_address"])
    op.create_index("idx_avail_checked_at", "availability_checks", ["checked_at"])


def downgrade() -> None:
    op.drop_table("availability_checks")
