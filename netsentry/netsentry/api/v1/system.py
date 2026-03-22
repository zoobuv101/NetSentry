"""System endpoints — health check, config, version."""

from fastapi import APIRouter
from pydantic import BaseModel

from netsentry import __version__

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    version: str


@router.get("/system/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Health check endpoint.
    Returns 200 when the application is running.
    Used by Docker healthcheck and monitoring systems.
    """
    return HealthResponse(status="ok", version=__version__)
