"""NetSentry events log endpoint."""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from netsentry.api.deps import get_device_repo, get_event_repo
from netsentry.db.repositories.devices import DeviceRepository
from netsentry.db.repositories.events import EventRepository

logger = logging.getLogger(__name__)
router = APIRouter()

EVENT_TYPE_LABELS: dict[str, str] = {
    "device.new": "New device",
    "device.offline": "Device offline",
    "device.online": "Device online",
    "availability.down": "Unreachable",
    "availability.up": "Reachable again",
    "system.scan_failed": "Scan failed",
    "speed.slow": "Speed degraded",
    "deco.device_roamed": "Device roamed",
}

SEVERITY_ORDER = ["urgent", "high", "info", "low"]


class DeviceContext(BaseModel):
    hostname: str | None
    friendly_name: str | None
    current_ip: str | None
    vendor: str | None


class EventLogEntry(BaseModel):
    id: int
    event_type: str
    event_label: str
    severity: str
    mac_address: str | None
    details: dict[str, Any]
    timestamp: str
    notification_sent: bool
    device: DeviceContext | None


class EventLogResponse(BaseModel):
    events: list[EventLogEntry]
    total: int
    limit: int
    offset: int


@router.get("/events", response_model=EventLogResponse)
async def list_events(
    q: str | None = Query(default=None, description="Filter by name, MAC, IP, hostname, vendor"),
    event_type: str | None = Query(default=None),
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    event_repo: EventRepository = Depends(get_event_repo),
    device_repo: DeviceRepository = Depends(get_device_repo),
) -> EventLogResponse:
    """
    Return paginated event log with optional full-text search.
    Search matches against device name, hostname, IP, MAC, vendor, event details.
    """
    events = await event_repo.search(query=q, event_type=event_type, limit=limit, offset=offset)
    total = await event_repo.count(query=q, event_type=event_type)

    # Batch-fetch device context for all MACs in one pass
    macs = {e.mac_address for e in events if e.mac_address}
    device_map: dict[str, DeviceContext] = {}
    for mac in macs:
        device = await device_repo.get(mac)
        if device:
            device_map[mac] = DeviceContext(
                hostname=device.hostname or device.netbios_name,
                friendly_name=device.friendly_name,
                current_ip=device.current_ip,
                vendor=device.vendor,
            )

    entries = []
    for e in events:
        try:
            details = json.loads(e.details) if isinstance(e.details, str) else e.details
        except (json.JSONDecodeError, TypeError):
            details = {}

        entries.append(
            EventLogEntry(
                id=e.id,
                event_type=e.event_type,
                event_label=EVENT_TYPE_LABELS.get(e.event_type, e.event_type),
                severity=e.severity,
                mac_address=e.mac_address,
                details=details,
                timestamp=e.timestamp.isoformat(),
                notification_sent=e.notification_sent,
                device=device_map.get(e.mac_address) if e.mac_address else None,
            )
        )

    return EventLogResponse(events=entries, total=total, limit=limit, offset=offset)
