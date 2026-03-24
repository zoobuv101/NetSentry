"""NetSentry device API endpoints."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from netsentry.api.deps import get_device_repo, get_event_repo, get_ip_repo
from netsentry.db.repositories.devices import DeviceRepository
from netsentry.db.repositories.events import EventRepository
from netsentry.db.repositories.ip_assignments import IpAssignmentRepository
from netsentry.db.utils import normalise_mac

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Response schemas ──────────────────────────────────────────────────────────


class DeviceResponse(BaseModel):
    mac_address: str
    friendly_name: str | None
    category: str | None
    subcategory: str | None
    owner: str | None
    notes: str | None
    vendor: str | None
    device_type: str | None
    os_family: str | None
    os_version: str | None
    current_ip: str | None
    hostname: str | None
    lifecycle: str
    connection_type: str | None
    is_online: bool
    is_monitored: bool
    first_seen: str
    last_seen: str


class IpHistoryEntry(BaseModel):
    ip_address: str
    source: str
    first_seen: str
    last_seen: str


class EventEntry(BaseModel):
    id: int
    event_type: str
    severity: str
    timestamp: str
    details: str


class DeviceDetailResponse(DeviceResponse):
    ip_history: list[IpHistoryEntry]
    recent_events: list[EventEntry]


class ScanTriggerRequest(BaseModel):
    profile: str = "standard"


class ScanTriggerResponse(BaseModel):
    accepted: bool
    profile: str
    message: str


class ScanStatusResponse(BaseModel):
    is_scanning: bool
    last_scan: dict[str, Any] | None


# ── Helpers ───────────────────────────────────────────────────────────────────


def _normalise_mac_param(mac: str) -> str:
    """Normalise MAC from URL path; raise 422 on invalid format."""
    try:
        return normalise_mac(mac)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid MAC address: '{mac}'") from None


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.get("/devices", response_model=list[DeviceResponse])
async def list_devices(
    lifecycle: str = Query(default="active"),
    limit: int = Query(default=500, le=1000),
    devices: DeviceRepository = Depends(get_device_repo),
) -> list[DeviceResponse]:
    """
    List devices filtered by lifecycle.
    Default: active devices only.
    Use ?lifecycle=historic for archived devices.
    """
    device_list = await devices.list(lifecycle=lifecycle, limit=limit)
    return [
        DeviceResponse(
            mac_address=d.mac_address,
            friendly_name=d.friendly_name,
            category=d.category,
            subcategory=d.subcategory,
            owner=d.owner,
            notes=d.notes,
            vendor=d.vendor,
            device_type=d.device_type,
            os_family=d.os_family,
            os_version=d.os_version,
            current_ip=d.current_ip,
            hostname=d.hostname,
            lifecycle=d.lifecycle,
            connection_type=d.connection_type,
            is_online=d.is_online,
            is_monitored=d.is_monitored,
            first_seen=d.first_seen.isoformat(),
            last_seen=d.last_seen.isoformat(),
        )
        for d in device_list
    ]


@router.get("/devices/{mac}", response_model=DeviceDetailResponse)
async def get_device(
    mac: str,
    devices: DeviceRepository = Depends(get_device_repo),
    ip_repo: IpAssignmentRepository = Depends(get_ip_repo),
    event_repo: EventRepository = Depends(get_event_repo),
) -> DeviceDetailResponse:
    """Get a single device with full enrichment data."""
    norm_mac = _normalise_mac_param(mac)
    device = await devices.get(norm_mac)
    if device is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "DEVICE_NOT_FOUND", "message": f"No device found with MAC {norm_mac}"},
        )

    ip_history = await ip_repo.list_for_device(norm_mac)
    recent_events = await event_repo.list_for_device(norm_mac, limit=10)

    return DeviceDetailResponse(
        mac_address=device.mac_address,
        friendly_name=device.friendly_name,
        category=device.category,
        subcategory=device.subcategory,
        owner=device.owner,
        notes=device.notes,
        vendor=device.vendor,
        device_type=device.device_type,
        os_family=device.os_family,
        os_version=device.os_version,
        current_ip=device.current_ip,
        hostname=device.hostname,
        lifecycle=device.lifecycle,
        connection_type=device.connection_type,
        is_online=device.is_online,
        is_monitored=device.is_monitored,
        first_seen=device.first_seen.isoformat(),
        last_seen=device.last_seen.isoformat(),
        ip_history=[
            IpHistoryEntry(
                ip_address=ip.ip_address,
                source=ip.source,
                first_seen=ip.first_seen.isoformat(),
                last_seen=ip.last_seen.isoformat(),
            )
            for ip in ip_history
        ],
        recent_events=[
            EventEntry(
                id=e.id,
                event_type=e.event_type,
                severity=e.severity,
                timestamp=e.timestamp.isoformat(),
                details=e.details,
            )
            for e in recent_events
        ],
    )
