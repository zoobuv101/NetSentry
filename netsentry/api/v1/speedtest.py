"""NetSentry speed test API endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()


class SpeedTestResultResponse(BaseModel):
    download_mbps: float
    upload_mbps: float
    ping_ms: float
    server: str | None
    backend: str
    grade: str
    tested_at: str | None


class SpeedTestListResponse(BaseModel):
    results: list[SpeedTestResultResponse]
    count: int


def _to_response(result: object) -> SpeedTestResultResponse:
    from netsentry.speedtest.models import SpeedTestResult

    assert isinstance(result, SpeedTestResult)
    return SpeedTestResultResponse(
        download_mbps=result.download_mbps,
        upload_mbps=result.upload_mbps,
        ping_ms=result.ping_ms,
        server=result.server,
        backend=result.backend,
        grade=result.grade,
        tested_at=result.tested_at,
    )


@router.get("/speedtest/latest", response_model=SpeedTestResultResponse | None)
async def get_latest_speedtest(request: Request) -> SpeedTestResultResponse | None:
    """Return the most recent speed test result."""
    from netsentry.speedtest.storage import SpeedTestStorage

    storage = SpeedTestStorage(conn=request.app.state.db)
    result = await storage.get_latest()
    return _to_response(result) if result else None


@router.get("/speedtest/history", response_model=SpeedTestListResponse)
async def get_speedtest_history(request: Request) -> SpeedTestListResponse:
    """Return the last 30 speed test results."""
    from netsentry.speedtest.storage import SpeedTestStorage

    storage = SpeedTestStorage(conn=request.app.state.db)
    results = await storage.get_history(limit=30)
    return SpeedTestListResponse(
        results=[_to_response(r) for r in results],
        count=len(results),
    )


@router.post("/speedtest/run", response_model=SpeedTestResultResponse | None, status_code=202)
async def trigger_speedtest(request: Request) -> SpeedTestResultResponse | None:
    """Trigger an on-demand speed test. Runs synchronously (may take ~60s)."""
    from netsentry.speedtest.runner import run_speed_test

    result = await run_speed_test(conn=request.app.state.db)
    return _to_response(result) if result else None
