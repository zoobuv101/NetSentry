"""speedtest

Revision ID: de0c75081e97
Revises: b482706ff78e
Create Date: 2026-03-24

US0034: speed_tests table.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "de0c75081e97"
down_revision: str | None = "b482706ff78e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "speed_tests",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("download_mbps", sa.Float, nullable=False),
        sa.Column("upload_mbps", sa.Float, nullable=False),
        sa.Column("ping_ms", sa.Float, nullable=False),
        sa.Column("server", sa.Text),
        sa.Column("backend", sa.Text, nullable=False),
        sa.Column("grade", sa.Text),
        sa.Column("tested_at", sa.Text, nullable=False),
    )
    op.create_index("idx_speed_tested_at", "speed_tests", ["tested_at"])


def downgrade() -> None:
    op.drop_table("speed_tests")
