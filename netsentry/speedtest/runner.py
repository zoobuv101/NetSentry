"""NetSentry speed test runner — selects backend and stores result."""

from __future__ import annotations

import logging
import os

import aiosqlite

from netsentry.speedtest.models import SpeedTestResult
from netsentry.speedtest.storage import SpeedTestStorage

logger = logging.getLogger(__name__)


async def _try_ookla() -> SpeedTestResult | None:
    """Run Ookla speedtest-cli (installed via apt in Docker)."""
    from netsentry.speedtest.ookla import run_ookla

    return await run_ookla()


async def _try_librespeed() -> SpeedTestResult | None:
    """Run librespeed-cli (optional install)."""
    from netsentry.speedtest.librespeed import run_librespeed

    server_url = os.environ.get("LIBRESPEED_SERVER_URL")
    return await run_librespeed(server_url=server_url)


async def run_speed_test(conn: aiosqlite.Connection) -> SpeedTestResult | None:
    """
    Run a speed test trying backends in order until one succeeds.

    Order: configured backend first, then fallbacks.
    Results are saved to the database.
    """
    backend = os.environ.get("SPEEDTEST_BACKEND", "ookla").lower()
    result: SpeedTestResult | None = None

    # Build ordered list of backends to try
    if backend == "librespeed":
        backends = [_try_librespeed, _try_ookla]
    elif backend == "ookla":
        backends = [_try_ookla, _try_librespeed]
    else:  # auto
        backends = [_try_ookla, _try_librespeed]

    for backend_fn in backends:
        try:
            result = await backend_fn()
            if result is not None:
                logger.info(
                    "Speed test: ↓%.1f Mbps ↑%.1f Mbps ping=%.0fms via %s",
                    result.download_mbps,
                    result.upload_mbps,
                    result.ping_ms,
                    result.backend,
                )
                break
        except Exception as e:
            logger.warning("Speed test backend %s failed: %s", backend_fn.__name__, e)

    if result is None:
        logger.warning(
            "All speed test backends failed. "
            "Ensure speedtest-cli is installed (it should be in the Docker image)."
        )
        return None

    storage = SpeedTestStorage(conn=conn)
    await storage.save(result)
    return result
