"""NetSentry speed test runner — selects backend and stores result."""

from __future__ import annotations

import logging
import os

import aiosqlite

from netsentry.speedtest.models import SpeedTestResult
from netsentry.speedtest.storage import SpeedTestStorage

logger = logging.getLogger(__name__)


async def run_speed_test(conn: aiosqlite.Connection) -> SpeedTestResult | None:
    """
    Run a speed test using the configured backend.

    Backend priority:
    - librespeed: tries librespeed-cli, requires LIBRESPEED_SERVER_URL if
                  no public server is configured (self-hosted only)
    - ookla:      tries official speedtest-cli (installed in container)
    - auto:       tries librespeed first, then ookla

    If the configured backend fails, always falls back through all available
    backends before giving up.

    Saves the result to the database if successful.
    """
    backend = os.environ.get("SPEEDTEST_BACKEND", "ookla").lower()
    result: SpeedTestResult | None = None

    # Try librespeed first if configured or auto
    if backend in ("librespeed", "auto"):
        from netsentry.speedtest.librespeed import run_librespeed

        server_url = os.environ.get("LIBRESPEED_SERVER_URL")
        result = await run_librespeed(server_url=server_url)
        if result:
            logger.info("Speed test completed via librespeed")

    # Try ookla — always attempt as fallback even if librespeed was configured
    if result is None:
        if backend in ("ookla", "auto") or backend == "librespeed":
            from netsentry.speedtest.ookla import run_ookla

            logger.info("Trying Ookla speedtest backend")
            result = await run_ookla()
            if result:
                logger.info("Speed test completed via ookla")

    if result is None:
        logger.warning(
            "All speed test backends failed. "
            "Ensure speedtest-cli is installed or set LIBRESPEED_SERVER_URL."
        )
        return None

    storage = SpeedTestStorage(conn=conn)
    await storage.save(result)
    return result
