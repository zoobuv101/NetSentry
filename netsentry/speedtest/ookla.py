"""NetSentry speed test using speedtest-cli (Python package)."""

from __future__ import annotations

import json
import logging

from netsentry.scanner.utils import run_subprocess
from netsentry.speedtest.models import SpeedTestResult

logger = logging.getLogger(__name__)

_run_subprocess = run_subprocess


async def run_ookla(timeout: float = 120.0) -> SpeedTestResult | None:
    """
    Run a speed test using the speedtest-cli Python package.

    The Python speedtest-cli package is installed via apt as 'speedtest-cli'
    and invoked as 'speedtest-cli --json'.

    Returns:
        SpeedTestResult on success, None on any failure.
    """
    try:
        stdout, _ = await _run_subprocess(
            ["speedtest-cli", "--json", "--secure"],
            timeout=timeout,
        )
    except FileNotFoundError:
        logger.warning("speedtest-cli not found in PATH")
        return None
    except Exception as e:
        logger.warning("speedtest-cli failed: %s", e)
        return None

    try:
        data = json.loads(stdout.strip())
        # speedtest-cli JSON format:
        # download/upload are in bits/s, ping in ms
        download_mbps = float(data["download"]) / 1_000_000
        upload_mbps = float(data["upload"]) / 1_000_000
        ping_ms = float(data["ping"])
        server = data.get("server", {})
        server_name = f"{server.get('name', '')} ({server.get('country', '')})".strip(" ()")

        return SpeedTestResult(
            download_mbps=download_mbps,
            upload_mbps=upload_mbps,
            ping_ms=ping_ms,
            server=server_name or None,
            backend="ookla",
        )
    except (json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
        logger.warning("Failed to parse speedtest-cli output: %s — stdout: %.200s", e, stdout)
        return None
