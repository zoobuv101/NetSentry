"""device_enrichment

Revision ID: 02570df1b69f
Revises: de0c75081e97
Create Date: 2026-03-24

Add enrichment columns to devices table:
- open_ports_json: JSON array of open TCP ports from latest port scan
- services_json: JSON array of {port, service, version} from nmap -sV
- mdns_services_json: JSON array of mDNS/Bonjour service types
- netbios_name: Windows NetBIOS hostname
- ssdp_device_type: UPnP device type from SSDP
- last_port_scan: ISO timestamp of most recent port scan
- last_os_scan: ISO timestamp of most recent OS fingerprint attempt
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "02570df1b69f"
down_revision: str | None = "de0c75081e97"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("devices") as batch_op:
        batch_op.add_column(sa.Column("open_ports_json", sa.Text, server_default="[]"))
        batch_op.add_column(sa.Column("services_json", sa.Text, server_default="[]"))
        batch_op.add_column(sa.Column("mdns_services_json", sa.Text, server_default="[]"))
        batch_op.add_column(sa.Column("netbios_name", sa.Text))
        batch_op.add_column(sa.Column("ssdp_device_type", sa.Text))
        batch_op.add_column(sa.Column("last_port_scan", sa.Text))
        batch_op.add_column(sa.Column("last_os_scan", sa.Text))


def downgrade() -> None:
    with op.batch_alter_table("devices") as batch_op:
        for col in [
            "open_ports_json",
            "services_json",
            "mdns_services_json",
            "netbios_name",
            "ssdp_device_type",
            "last_port_scan",
            "last_os_scan",
        ]:
            batch_op.drop_column(col)
