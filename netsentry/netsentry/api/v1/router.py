"""API v1 router — aggregates all endpoint modules."""

from fastapi import APIRouter

from netsentry.api.v1.system import router as system_router

router = APIRouter()
router.include_router(system_router, tags=["system"])
