"""NetSentry device identification and lifecycle API endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from netsentry.db.utils import normalise_mac

logger = logging.getLogger(__name__)
router = APIRouter()


class CategoriseResponse(BaseModel):
    mac_address: str
    category: str | None
    device_type: str | None
    confidence: float
    source: str


class LifecycleUpdateRequest(BaseModel):
    lifecycle: str


class LifecycleUpdateResponse(BaseModel):
    mac_address: str
    lifecycle: str


class PurgeResponse(BaseModel):
    mac_address: str
    purged: bool


@router.post("/devices/{mac}/categorise", response_model=CategoriseResponse)
async def categorise_device(mac: str, request: Request) -> CategoriseResponse:
    """Trigger identification and categorisation for a single device."""
    try:
        norm_mac = normalise_mac(mac)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid MAC: {mac}") from None

    from netsentry.identification.categoriser import DeviceCategoriser

    categoriser = DeviceCategoriser(conn=request.app.state.db, overwrite_manual=True)
    result = await categoriser.categorise(norm_mac)

    if result is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "DEVICE_NOT_FOUND", "message": f"No device with MAC {norm_mac}"},
        )

    return CategoriseResponse(
        mac_address=norm_mac,
        category=result.category,
        device_type=result.device_type,
        confidence=result.confidence,
        source=result.source,
    )


@router.patch("/devices/{mac}/lifecycle", response_model=LifecycleUpdateResponse)
async def update_lifecycle(
    mac: str, body: LifecycleUpdateRequest, request: Request
) -> LifecycleUpdateResponse:
    """Update a device's lifecycle state (active / historic)."""
    try:
        norm_mac = normalise_mac(mac)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid MAC: {mac}") from None

    from netsentry.db.repositories.devices import DeviceRepository

    repo = DeviceRepository(request.app.state.db)
    try:
        await repo.set_lifecycle(norm_mac, body.lifecycle)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    return LifecycleUpdateResponse(mac_address=norm_mac, lifecycle=body.lifecycle)


@router.delete("/devices/{mac}", response_model=PurgeResponse)
async def purge_device(mac: str, request: Request) -> PurgeResponse:
    """Permanently delete a device and all related data."""
    try:
        norm_mac = normalise_mac(mac)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid MAC: {mac}") from None

    from netsentry.identification.lifecycle import LifecycleManager

    manager = LifecycleManager(conn=request.app.state.db)
    await manager.purge_device(norm_mac)
    return PurgeResponse(mac_address=norm_mac, purged=True)
