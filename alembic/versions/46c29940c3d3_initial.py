"""initial

Revision ID: 46c29940c3d3
Revises:
Create Date: 2026-03-22 17:30:02.870720

US0003: All core EP0001 tables.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "46c29940c3d3"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "devices",
        sa.Column("mac_address", sa.Text, primary_key=True),
        sa.Column("friendly_name", sa.Text),
        sa.Column("category", sa.Text),
        sa.Column("subcategory", sa.Text),
        sa.Column("owner", sa.Text),
        sa.Column("notes", sa.Text),
        sa.Column("vendor", sa.Text),
        sa.Column("device_type", sa.Text),
        sa.Column("os_family", sa.Text),
        sa.Column("os_version", sa.Text),
        sa.Column("current_ip", sa.Text),
        sa.Column("hostname", sa.Text),
        sa.Column("lifecycle", sa.Text, nullable=False, server_default="active"),
        sa.Column("connection_type", sa.Text),
        sa.Column("vlan_id", sa.Integer),
        sa.Column("firewall_rules_json", sa.Text),
        sa.Column("first_seen", sa.Text, nullable=False),
        sa.Column("last_seen", sa.Text, nullable=False),
        sa.Column("is_online", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_monitored", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.Text, nullable=False),
        sa.Column("updated_at", sa.Text, nullable=False),
    )
    op.create_index("idx_devices_lifecycle", "devices", ["lifecycle"])
    op.create_index("idx_devices_is_online", "devices", ["is_online"])
    op.create_index("idx_devices_last_seen", "devices", ["last_seen"])

    op.create_table(
        "ip_assignments",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("mac_address", sa.Text, nullable=False),
        sa.Column("ip_address", sa.Text, nullable=False),
        sa.Column("source", sa.Text, nullable=False),
        sa.Column("first_seen", sa.Text, nullable=False),
        sa.Column("last_seen", sa.Text, nullable=False),
    )
    op.create_index("idx_ip_mac", "ip_assignments", ["mac_address"])
    op.create_index("idx_ip_address", "ip_assignments", ["ip_address"])

    op.create_table(
        "events",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("mac_address", sa.Text),
        sa.Column("event_type", sa.Text, nullable=False),
        sa.Column("severity", sa.Text, nullable=False, server_default="info"),
        sa.Column("details", sa.Text, nullable=False, server_default="{}"),
        sa.Column("notification_sent", sa.Integer, nullable=False, server_default="0"),
        sa.Column("timestamp", sa.Text, nullable=False),
    )
    op.create_index("idx_events_mac", "events", ["mac_address"])
    op.create_index("idx_events_type", "events", ["event_type"])
    op.create_index("idx_events_timestamp", "events", ["timestamp"])

    op.create_table(
        "scan_runs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("scan_type", sa.Text, nullable=False),
        sa.Column("profile", sa.Text),
        sa.Column("started_at", sa.Text, nullable=False),
        sa.Column("completed_at", sa.Text),
        sa.Column("devices_found", sa.Integer),
        sa.Column("errors", sa.Text),
    )

    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("event_id", sa.Integer, nullable=False),
        sa.Column("channel", sa.Text, nullable=False),
        sa.Column("status", sa.Text, nullable=False, server_default="pending"),
        sa.Column("priority", sa.Text, nullable=False, server_default="default"),
        sa.Column("sent_at", sa.Text),
        sa.Column("error", sa.Text),
    )
    op.create_index("idx_notif_event", "notifications", ["event_id"])

    op.create_table(
        "system_config",
        sa.Column("key", sa.Text, primary_key=True),
        sa.Column("value", sa.Text, nullable=False),
    )

    op.create_table(
        "tags",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.Text, nullable=False, unique=True),
    )

    op.create_table(
        "device_tags",
        sa.Column("mac_address", sa.Text, nullable=False),
        sa.Column("tag_id", sa.Integer, nullable=False),
        sa.PrimaryKeyConstraint("mac_address", "tag_id"),
    )

    op.create_table(
        "deletion_audit_log",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("mac_address", sa.Text, nullable=False),
        sa.Column("deleted_at", sa.Text, nullable=False),
        sa.Column("friendly_name_at_deletion", sa.Text),
    )


def downgrade() -> None:
    for table in [
        "deletion_audit_log",
        "device_tags",
        "tags",
        "system_config",
        "notifications",
        "scan_runs",
        "events",
        "ip_assignments",
        "devices",
    ]:
        op.drop_table(table)
