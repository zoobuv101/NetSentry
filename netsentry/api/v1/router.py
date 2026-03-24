"""API v1 router — aggregates all endpoint modules."""

from fastapi import APIRouter

from netsentry.api.v1.availability import router as availability_router
from netsentry.api.v1.dashboard import router as dashboard_router
from netsentry.api.v1.deco import router as deco_router
from netsentry.api.v1.devices import router as devices_router
from netsentry.api.v1.identification import router as identification_router
from netsentry.api.v1.notifications import router as notifications_router
from netsentry.api.v1.scan import router as scan_router
from netsentry.api.v1.speedtest import router as speedtest_router
from netsentry.api.v1.system import router as system_router

router = APIRouter()
router.include_router(system_router, tags=["system"])
router.include_router(dashboard_router, tags=["dashboard"])
router.include_router(devices_router, tags=["devices"])
router.include_router(scan_router, tags=["scan"])
router.include_router(notifications_router, tags=["notifications"])
router.include_router(deco_router, tags=["deco"])
router.include_router(identification_router, tags=["identification"])
router.include_router(availability_router, tags=["availability"])
router.include_router(speedtest_router, tags=["speedtest"])
