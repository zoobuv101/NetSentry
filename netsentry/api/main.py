"""
NetSentry FastAPI application factory.

Usage:
    uvicorn netsentry.api.main:create_app --factory --host 0.0.0.0 --port 8282
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from netsentry.api.v1.router import router as v1_router
from netsentry.core.config import get_settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """FastAPI lifespan — runs migrations, opens DB, starts scheduler."""
    settings = get_settings()

    logging.basicConfig(
        level=getattr(logging, settings.log_level),
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )
    logger.info("NetSentry v%s starting up", settings.app_version)

    # ── Migrations + DB ───────────────────────────────────────────────
    try:
        from netsentry.db.connection import get_connection, run_migrations

        run_migrations(settings.db_path)
        conn = await get_connection(settings.db_path)
        app.state.db = conn
        logger.info("Database ready at %s", settings.db_path)
    except Exception:
        logger.exception("FATAL: database init failed")
        raise

    # ── Scan orchestrator ─────────────────────────────────────────────
    try:
        from netsentry.scanner.orchestrator import ScanOrchestrator
        from netsentry.scanner.oui import OuiDatabase
        from netsentry.scanner.subnets import get_subnets

        oui_db = OuiDatabase()
        subnets = get_subnets(settings.scan_subnets or None)
        if not subnets:
            logger.warning("No subnets detected — set SCAN_SUBNETS=192.168.x.0/24 in .env")

        orchestrator = ScanOrchestrator(conn=conn, oui_db=oui_db, subnets=subnets)
        app.state.orchestrator = orchestrator
        logger.info("Scan orchestrator ready (subnets: %s)", subnets or "auto-detect pending")
    except Exception:
        logger.exception("Scan orchestrator failed to init — scanning disabled")
        orchestrator = None
        subnets = []

    # ── Scheduler ─────────────────────────────────────────────────────
    try:
        from netsentry.core.scheduler import NetSentryScheduler

        scheduler = NetSentryScheduler()

        if orchestrator and subnets:
            scheduler.register_scan_jobs(
                orchestrator,
                arp_interval=settings.scan_interval_arp,
                port_interval=settings.scan_interval_ports,
            )

        # Availability monitor
        if settings.enable_availability_monitoring:
            from netsentry.monitor.monitor import AvailabilityMonitor

            availability_monitor = AvailabilityMonitor(conn=conn)
            scheduler._scheduler.add_job(
                availability_monitor.run_probe_cycle,
                trigger="interval",
                seconds=60,
                id="availability_probe",
                max_instances=1,
            )
            logger.info("Availability monitoring enabled (60s)")

        # Deco poller — only works in router mode; AP mode has no local API
        deco_host = settings.deco_host
        if settings.enable_deco_integration and deco_host and settings.deco_router_mode:
            try:
                from netsentry.integrations.deco.client import DecoClient
                from netsentry.integrations.deco.poller import DecoPoller

                deco_client = DecoClient(
                    host=deco_host,
                    username=settings.deco_username or "admin",
                    password=settings.deco_password or "",
                )
                deco_poller = DecoPoller(client=deco_client, conn=conn)
                scheduler._scheduler.add_job(
                    deco_poller.poll,
                    trigger="interval",
                    seconds=30,
                    id="deco_poll",
                    max_instances=1,
                )
                logger.info("Deco integration enabled (%s, router mode)", deco_host)
            except Exception:
                logger.exception("Deco integration failed to start")

        # AdGuard poller
        if settings.enable_adguard_integration and settings.adguard_url:
            try:
                from netsentry.integrations.adguard.client import AdGuardClient
                from netsentry.integrations.adguard.poller import AdGuardPoller

                adguard_client = AdGuardClient(
                    url=settings.adguard_url,
                    username=settings.adguard_username or "",
                    password=settings.adguard_password or "",
                )
                adguard_poller = AdGuardPoller(client=adguard_client, conn=conn)
                scheduler._scheduler.add_job(
                    adguard_poller.poll,
                    trigger="interval",
                    seconds=60,
                    id="adguard_poll",
                    max_instances=1,
                )
                logger.info("AdGuard integration enabled (%s)", settings.adguard_url)
            except Exception:
                logger.exception("AdGuard integration failed to start")

        # pfSense poller (SSH-based, no REST package needed)
        if settings.enable_pfsense_integration and settings.pfsense_host:
            try:
                from netsentry.integrations.pfsense.client import PfSenseClient
                from netsentry.integrations.pfsense.poller import PfSensePoller

                pfsense_client = PfSenseClient(
                    host=settings.pfsense_host,
                    username=settings.pfsense_username,
                    key_path=settings.pfsense_key_path,
                    port=settings.pfsense_ssh_port,
                )
                pfsense_poller = PfSensePoller(client=pfsense_client, conn=conn)
                scheduler._scheduler.add_job(
                    pfsense_poller.poll,
                    trigger="interval",
                    seconds=120,
                    id="pfsense_poll",
                    max_instances=1,
                )
                logger.info("pfSense integration enabled (%s via SSH)", settings.pfsense_host)
            except Exception:
                logger.exception("pfSense integration failed to start")

        # Speed test
        if settings.enable_speedtest:
            from netsentry.speedtest.runner import run_speed_test

            async def _run_speed_test() -> None:
                await run_speed_test(conn)

            scheduler._scheduler.add_job(
                _run_speed_test,
                trigger="interval",
                seconds=settings.speedtest_interval,
                id="speedtest",
                max_instances=1,
            )
            logger.info("Speed test scheduled every %ds", settings.speedtest_interval)

        scheduler.start()
        app.state.scheduler = scheduler
        logger.info("Scheduler started with %d jobs", len(scheduler.get_jobs()))

    except Exception:
        logger.exception("Scheduler failed to start")

    # ── Initial scan ──────────────────────────────────────────────────
    if orchestrator and subnets:
        from netsentry.scanner.profiles import ScanProfile

        asyncio.create_task(orchestrator.run_scan(ScanProfile.QUICK))
        logger.info("Initial quick scan triggered")

    logger.info("NetSentry startup complete")
    yield

    # ── Shutdown ──────────────────────────────────────────────────────
    logger.info("NetSentry shutting down")
    if hasattr(app.state, "scheduler"):
        app.state.scheduler.shutdown(wait=False)
    if hasattr(app.state, "db"):
        await app.state.db.close()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="NetSentry",
        description="Self-Hosted Network Intelligence Platform",
        version=settings.app_version,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(v1_router, prefix="/api/v1")

    # Serve compiled React frontend — must be after API router
    static_dir = Path(__file__).parent.parent.parent / "frontend" / "dist"
    if static_dir.exists():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="frontend")
        logger.info("Serving frontend from %s", static_dir)
    else:
        logger.warning("Frontend not built — run: cd frontend && pnpm build")

    return app


def main() -> None:
    settings = get_settings()
    uvicorn.run(
        "netsentry.api.main:create_app",
        factory=True,
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
