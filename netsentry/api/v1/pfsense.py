"""pfSense network interface status endpoint — serves from backend cache."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()


class InterfaceStatus(BaseModel):
    name: str
    description: str | None
    up: bool
    running: bool
    ip_address: str | None
    ip6_address: str | None
    media: str | None
    flags: list[str]


class InterfacesResponse(BaseModel):
    interfaces: list[InterfaceStatus]
    source: str
    last_updated: str | None


@router.get("/pfsense/interfaces", response_model=InterfacesResponse)
async def get_pfsense_interfaces(request: Request) -> InterfacesResponse:
    """
    Return pfSense interface status from the backend cache.

    The cache is updated by the InterfacePoller scheduler job every 30s.
    This endpoint returns instantly — no SSH on request.
    """
    poller = getattr(request.app.state, "interface_poller", None)

    if poller is None or not poller.cached:
        return InterfacesResponse(
            interfaces=[],
            source="unavailable",
            last_updated=None,
        )

    return InterfacesResponse(
        interfaces=[InterfaceStatus(**iface) for iface in poller.cached],
        source="pfsense",
        last_updated=poller.last_updated,
    )
