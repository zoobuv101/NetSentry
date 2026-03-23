"""
NetSentry database models.

Typed dataclasses returned by repository methods.
These are the internal domain models — not Pydantic API schemas.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class Device:
    mac_address: str
    first_seen: datetime
    last_seen: datetime
    created_at: datetime
    updated_at: datetime
    friendly_name: str | None = None
    category: str | None = None
    subcategory: str | None = None
    owner: str | None = None
    notes: str | None = None
    vendor: str | None = None
    device_type: str | None = None
    os_family: str | None = None
    os_version: str | None = None
    current_ip: str | None = None
    hostname: str | None = None
    lifecycle: str = "active"
    connection_type: str | None = None
    vlan_id: int | None = None
    firewall_rules_json: str | None = None
    is_online: bool = False
    is_monitored: bool = False


@dataclass
class IpAssignment:
    id: int
    mac_address: str
    ip_address: str
    source: str
    first_seen: datetime
    last_seen: datetime


@dataclass
class Event:
    id: int
    event_type: str
    severity: str
    details: str
    notification_sent: bool
    timestamp: datetime
    mac_address: str | None = None


@dataclass
class ScanRun:
    id: int
    scan_type: str
    started_at: datetime
    profile: str | None = None
    completed_at: datetime | None = None
    devices_found: int | None = None
    errors: str | None = None
