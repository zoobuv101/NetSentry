"""API v1 router — aggregates all endpoint modules."""

from fastapi import APIRouter

from netsentry.api.v1.devices import router as devices_router
from netsentry.api.v1.scan import router as scan_router
from netsentry.api.v1.system import router as system_router

router = APIRouter()
router.include_router(system_router, tags=["system"])
router.include_router(devices_router, tags=["devices"])
router.include_router(scan_router, tags=["scan"])
