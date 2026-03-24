"""
FastAPI dependency injection for database repositories.

All endpoints depend on these functions to get typed repository instances
backed by the application-wide DB connection opened in the lifespan.
"""

from __future__ import annotations

from fastapi import Request

from netsentry.db.repositories.devices import DeviceRepository
from netsentry.db.repositories.events import EventRepository
from netsentry.db.repositories.ip_assignments import IpAssignmentRepository
from netsentry.db.repositories.scan_runs import ScanRunRepository


def get_device_repo(request: Request) -> DeviceRepository:
    return DeviceRepository(request.app.state.db)


def get_ip_repo(request: Request) -> IpAssignmentRepository:
    return IpAssignmentRepository(request.app.state.db)


def get_event_repo(request: Request) -> EventRepository:
    return EventRepository(request.app.state.db)


def get_scan_repo(request: Request) -> ScanRunRepository:
    return ScanRunRepository(request.app.state.db)
