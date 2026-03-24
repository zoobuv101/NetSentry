"""deco

Revision ID: e8a6efb57ac6
Revises: 46c29940c3d3
Create Date: 2026-03-24

US0010: mesh_assignments and deco_nodes tables.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e8a6efb57ac6"
down_revision: str | None = "46c29940c3d3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "deco_nodes",
        sa.Column("mac_address", sa.Text, primary_key=True),
        sa.Column("model", sa.Text),
        sa.Column("role", sa.Text),
        sa.Column("is_online", sa.Integer, nullable=False, server_default="1"),
        sa.Column("cpu_usage", sa.Float),
        sa.Column("mem_usage", sa.Float),
        sa.Column("updated_at", sa.Text, nullable=False),
    )

    op.create_table(
        "mesh_assignments",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("mac_address", sa.Text, nullable=False),
        sa.Column("deco_node_mac", sa.Text),
        sa.Column("band", sa.Text),
        sa.Column("connection_type", sa.Text),
        sa.Column("up_speed_bps", sa.Integer),
        sa.Column("down_speed_bps", sa.Integer),
        sa.Column("last_known_ip", sa.Text),
        sa.Column("connected_at", sa.Text, nullable=False),
        sa.Column("disconnected_at", sa.Text),
    )
    op.create_index("idx_mesh_mac", "mesh_assignments", ["mac_address"])


def downgrade() -> None:
    op.drop_table("mesh_assignments")
    op.drop_table("deco_nodes")
