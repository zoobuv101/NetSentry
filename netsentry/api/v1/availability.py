"""NetSentry availability monitoring API endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from netsentry.db.utils import normalise_mac

logger = logging.getLogger(__name__)
router = APIRouter()


class UptimeResponse(BaseModel):
    mac_address: str
    uptime_pct_24h: float | None
    avg_rtt_ms: float | None


class MonitorToggleRequest(BaseModel):
    monitored: bool


class MonitorToggleResponse(BaseModel):
    mac_address: str
    is_monitored: bool


@router.get("/devices/{mac}/availability", response_model=UptimeResponse)
async def get_device_availability(
    mac: str,
    request: Request,
) -> UptimeResponse:
    """Return uptime percentage and average RTT for a device."""
    try:
        norm_mac = normalise_mac(mac)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid MAC: {mac}") from None

    from netsentry.monitor.tracker import AvailabilityTracker

    tracker = AvailabilityTracker(conn=request.app.state.db)

    uptime = await tracker.get_uptime_pct(norm_mac, hours=24)
    avg_rtt = await tracker.get_avg_rtt(norm_mac, hours=1)

    return UptimeResponse(
        mac_address=norm_mac,
        uptime_pct_24h=uptime,
        avg_rtt_ms=avg_rtt,
    )


@router.patch("/devices/{mac}/monitor", response_model=MonitorToggleResponse)
async def toggle_monitoring(
    mac: str,
    body: MonitorToggleRequest,
    request: Request,
) -> MonitorToggleResponse:
    """Enable or disable availability monitoring for a device."""
    try:
        norm_mac = normalise_mac(mac)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid MAC: {mac}") from None

    conn = request.app.state.db
    from netsentry.db.utils import to_iso8601, utc_now

    now = to_iso8601(utc_now())
    await conn.execute(
        "UPDATE devices SET is_monitored = ?, updated_at = ? WHERE mac_address = ?",
        (1 if body.monitored else 0, now, norm_mac),
    )
    await conn.commit()

    return MonitorToggleResponse(mac_address=norm_mac, is_monitored=body.monitored)
