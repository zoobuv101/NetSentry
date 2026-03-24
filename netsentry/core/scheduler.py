"""NetSentry APScheduler wrapper."""

from __future__ import annotations

import logging
from typing import Protocol

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from netsentry.scanner.profiles import ScanProfile

logger = logging.getLogger(__name__)


class _Orchestrator(Protocol):
    """Protocol for the ScanOrchestrator — avoids circular imports."""

    async def run_scan(self, profile: ScanProfile) -> int: ...


class NetSentryScheduler:
    """
    Thin wrapper around APScheduler's AsyncIOScheduler.

    Manages all periodic tasks: scan cycles, availability probes,
    speed tests, and maintenance jobs. One instance lives in the
    FastAPI lifespan for the duration of the application.
    """

    def __init__(self) -> None:
        self._scheduler = AsyncIOScheduler()

    def register_scan_jobs(
        self,
        orchestrator: _Orchestrator,
        arp_interval: int = 300,
        port_interval: int = 900,
    ) -> None:
        """Register the recurring ARP and port scan jobs."""
        self._scheduler.add_job(
            self._run_quick_scan,
            trigger=IntervalTrigger(seconds=arp_interval),
            id="scan_arp",
            args=[orchestrator],
            replace_existing=True,
            max_instances=1,
        )
        self._scheduler.add_job(
            self._run_standard_scan,
            trigger=IntervalTrigger(seconds=port_interval),
            id="scan_ports",
            args=[orchestrator],
            replace_existing=True,
            max_instances=1,
        )
        logger.info("Registered scan jobs — ARP: %ds, ports: %ds", arp_interval, port_interval)

    @staticmethod
    async def _run_quick_scan(orchestrator: _Orchestrator) -> None:
        await orchestrator.run_scan(ScanProfile.QUICK)

    @staticmethod
    async def _run_standard_scan(orchestrator: _Orchestrator) -> None:
        await orchestrator.run_scan(ScanProfile.STANDARD)

    def start(self) -> None:
        """Start the scheduler."""
        self._scheduler.start()
        logger.info("NetSentry scheduler started")

    def shutdown(self, wait: bool = True) -> None:
        """Shut down the scheduler."""
        if self._scheduler.running:
            self._scheduler.shutdown(wait=wait)
            logger.info("NetSentry scheduler stopped")

    def get_jobs(self) -> list:  # type: ignore[type-arg]
        """Return all registered jobs."""
        return list(self._scheduler.get_jobs())

    @property
    def running(self) -> bool:
        return bool(self._scheduler.running)
