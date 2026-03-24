"""
NetSentry FastAPI application factory.

Usage:
    uvicorn netsentry.api.main:create_app --factory --host 0.0.0.0 --port 8080
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from netsentry.api.v1.router import router as v1_router
from netsentry.core.config import get_settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    FastAPI lifespan — runs migrations, opens DB, starts scheduler.
    """
    settings = get_settings()

    logging.basicConfig(
        level=getattr(logging, settings.log_level),
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )
    logger.info("NetSentry v%s starting up", settings.app_version)
    settings.warn_missing_optional()

    # Run Alembic migrations before accepting any requests
    from netsentry.db.connection import get_connection, run_migrations

    run_migrations(settings.db_path)

    # Open the shared async DB connection and attach to app state
    conn = await get_connection(settings.db_path)
    app.state.db = conn

    logger.info("Database ready at %s", settings.db_path)

    yield

    # Shutdown: close DB connection
    await conn.close()
    logger.info("NetSentry shutting down")


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
    return app


def main() -> None:
    """Entry point for `netsentry` CLI command."""
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
