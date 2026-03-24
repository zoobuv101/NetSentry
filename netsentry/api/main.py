"""
NetSentry FastAPI application factory.

Usage:
    uvicorn netsentry.api.main:create_app --factory --host 0.0.0.0 --port 8282
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

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

    # Serve the compiled React frontend
    # Built by: cd frontend && pnpm build  (output → frontend/dist)
    static_dir = Path(__file__).parent.parent.parent / "frontend" / "dist"
    if static_dir.exists():
        # Serve static assets (JS, CSS, images)
        app.mount(
            "/assets",
            StaticFiles(directory=static_dir / "assets"),
            name="assets",
        )

        # SPA catch-all — any non-API route returns index.html
        # API routes that don't exist will still naturally 404 via FastAPI
        @app.get("/{full_path:path}", include_in_schema=False)
        async def spa_fallback(full_path: str) -> FileResponse:
            # Let API routes fall through to FastAPI's normal 404 handling
            if full_path.startswith("api/"):
                from fastapi import HTTPException

                raise HTTPException(status_code=404)
            return FileResponse(static_dir / "index.html")

    else:
        logger.warning(
            "Frontend dist not found at %s — run 'cd frontend && pnpm build'", static_dir
        )

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
