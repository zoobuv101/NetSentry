"""NetSentry scan control endpoints."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from netsentry.api.deps import get_scan_repo
from netsentry.db.repositories.scan_runs import ScanRunRepository

logger = logging.getLogger(__name__)
router = APIRouter()


class ScanTriggerRequest(BaseModel):
    profile: str = "standard"


class ScanTriggerResponse(BaseModel):
    accepted: bool
    profile: str
    message: str


class ScanStatusResponse(BaseModel):
    is_scanning: bool
    last_scan: dict[str, Any] | None


@router.post("/scan/trigger", response_model=ScanTriggerResponse, status_code=202)
async def trigger_scan(
    request: Request,
    body: ScanTriggerRequest = ScanTriggerRequest(),
) -> ScanTriggerResponse:
    """
    Trigger an on-demand scan asynchronously.
    Returns 202 Accepted immediately; scan runs in background.
    """
    profile = body.profile or "standard"
    logger.info("On-demand scan triggered (profile=%s)", profile)

    # Fire scan in background if orchestrator is available
    orchestrator = getattr(request.app.state, "orchestrator", None)
    if orchestrator is not None:
        from netsentry.scanner.profiles import ScanProfile

        try:
            scan_profile = ScanProfile.from_str(profile)
        except ValueError:
            scan_profile = ScanProfile.STANDARD
        asyncio.create_task(orchestrator.run_scan(scan_profile))
    else:
        logger.warning("Orchestrator not available — scan not triggered")

    return ScanTriggerResponse(
        accepted=True,
        profile=profile,
        message=f"Scan accepted (profile={profile}). Running in background.",
    )


@router.get("/scan/status", response_model=ScanStatusResponse)
async def scan_status(
    scans: ScanRunRepository = Depends(get_scan_repo),
) -> ScanStatusResponse:
    """Return current scan state and last scan metadata."""
    latest = await scans.get_latest()
    last_scan_data: dict[str, Any] | None = None
    if latest is not None:
        last_scan_data = {
            "id": latest.id,
            "scan_type": latest.scan_type,
            "profile": latest.profile,
            "started_at": latest.started_at.isoformat(),
            "completed_at": latest.completed_at.isoformat() if latest.completed_at else None,
            "devices_found": latest.devices_found,
        }

    return ScanStatusResponse(
        is_scanning=False,
        last_scan=last_scan_data,
    )
