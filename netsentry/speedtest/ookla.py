"""NetSentry Ookla speedtest-cli runner."""

from __future__ import annotations

import json
import logging

from netsentry.scanner.utils import run_subprocess
from netsentry.speedtest.models import SpeedTestResult

logger = logging.getLogger(__name__)

_BYTES_TO_MBPS = 8 / 1_000_000  # bytes/s → Mbps

_run_subprocess = run_subprocess


async def run_ookla(timeout: float = 120.0) -> SpeedTestResult | None:
    """
    Run a speed test using the official Ookla speedtest-cli.

    Returns:
        SpeedTestResult on success, None on any failure.
    """
    try:
        stdout, _ = await _run_subprocess(
            ["speedtest", "--format=json", "--accept-license", "--accept-gdpr"],
            timeout=timeout,
        )
    except FileNotFoundError:
        logger.warning("speedtest (Ookla) not found — install speedtest-cli")
        return None
    except Exception as e:
        logger.warning("Ookla speedtest failed: %s", e)
        return None

    try:
        data = json.loads(stdout.strip())
        download_bps = float(data["download"]["bandwidth"])
        upload_bps = float(data["upload"]["bandwidth"])
        ping_ms = float(data["ping"]["latency"])
        server = data.get("server", {})
        server_name = server.get("name") if isinstance(server, dict) else None

        return SpeedTestResult(
            download_mbps=download_bps * _BYTES_TO_MBPS,
            upload_mbps=upload_bps * _BYTES_TO_MBPS,
            ping_ms=ping_ms,
            server=server_name,
            backend="ookla",
        )
    except (json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
        logger.warning("Failed to parse Ookla speedtest output: %s", e)
        return None
