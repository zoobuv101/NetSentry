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
    Run a speed test using the configured backend (default: librespeed).
    Falls back to Ookla if LibreSpeed is not available.

    Saves the result to the database if successful.

    Returns:
        SpeedTestResult on success, None if no backend available.
    """
    backend = os.environ.get("SPEEDTEST_BACKEND", "librespeed").lower()
    result: SpeedTestResult | None = None

    if backend in ("librespeed", "auto"):
        from netsentry.speedtest.librespeed import run_librespeed

        server_url = os.environ.get("LIBRESPEED_SERVER_URL")
        result = await run_librespeed(server_url=server_url)

    if result is None and backend in ("ookla", "auto"):
        logger.info("LibreSpeed unavailable — falling back to Ookla")
        from netsentry.speedtest.ookla import run_ookla

        result = await run_ookla()

    if result is None:
        logger.warning("All speed test backends failed or unavailable")
        return None

    storage = SpeedTestStorage(conn=conn)
    await storage.save(result)
    return result
