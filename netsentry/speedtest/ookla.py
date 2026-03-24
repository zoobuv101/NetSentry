"""
NetSentry speed test — Ookla backend.

Tries the official Ookla CLI ('speedtest') first — it's multi-threaded
and gives accurate results on gigabit connections. Falls back to the
Python 'speedtest-cli' package if the official binary isn't available.

Set SPEEDTEST_SERVER_ID in .env to pin a specific server (recommended
for consistent results). Find your server ID at:
  speedtest --list | grep "your ISP or city"
"""

from __future__ import annotations

import json
import logging
import os

from netsentry.scanner.utils import run_subprocess
from netsentry.speedtest.models import SpeedTestResult

logger = logging.getLogger(__name__)

_run_subprocess = run_subprocess


async def run_ookla(timeout: float = 120.0) -> SpeedTestResult | None:
    """
    Run a speed test using the Ookla CLI.

    Attempts:
    1. Official Ookla 'speedtest' binary (multi-threaded, accurate on gigabit)
    2. Python 'speedtest-cli' fallback (single-threaded, ~100Mbps cap)

    Returns:
        SpeedTestResult on success, None on any failure.
    """
    result = await _run_official_ookla(timeout)
    if result is not None:
        return result

    logger.info("Official Ookla CLI unavailable — trying speedtest-cli fallback")
    return await _run_python_speedtest_cli(timeout)


async def _run_official_ookla(timeout: float) -> SpeedTestResult | None:
    """Run the official Ookla 'speedtest' binary (installed from packagecloud)."""
    server_id = os.environ.get("SPEEDTEST_SERVER_ID", "").strip()

    cmd = ["speedtest", "--format=json", "--accept-license", "--accept-gdpr"]
    if server_id:
        cmd += ["--server-id", server_id]

    try:
        stdout, _ = await _run_subprocess(cmd, timeout=timeout)
    except FileNotFoundError:
        return None
    except Exception as e:
        logger.warning("Official Ookla speedtest failed: %s", e)
        return None

    try:
        data = json.loads(stdout.strip())
        # Official Ookla JSON: download.bandwidth and upload.bandwidth in bytes/s
        download_mbps = float(data["download"]["bandwidth"]) * 8 / 1_000_000
        upload_mbps = float(data["upload"]["bandwidth"]) * 8 / 1_000_000
        ping_ms = float(data["ping"]["latency"])
        server = data.get("server", {})
        server_name = f"{server.get('name', '')} ({server.get('location', '')})"
        server_name = server_name.strip(" ()")

        logger.info(
            "Ookla speedtest: ↓%.1f Mbps ↑%.1f Mbps ping=%.1fms server=%s",
            download_mbps,
            upload_mbps,
            ping_ms,
            server_name,
        )
        return SpeedTestResult(
            download_mbps=download_mbps,
            upload_mbps=upload_mbps,
            ping_ms=ping_ms,
            server=server_name or None,
            backend="ookla",
        )
    except (json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
        logger.warning("Failed to parse Ookla output: %s — stdout: %.200s", e, stdout)
        return None


async def _run_python_speedtest_cli(timeout: float) -> SpeedTestResult | None:
    """Fallback: Python speedtest-cli package. Single-threaded, caps ~100Mbps."""
    server_id = os.environ.get("SPEEDTEST_SERVER_ID", "").strip()
    cmd = ["speedtest-cli", "--json", "--secure"]
    if server_id:
        cmd += ["--server", server_id]

    try:
        stdout, _ = await _run_subprocess(cmd, timeout=timeout)
    except FileNotFoundError:
        logger.warning("No speed test binary found (tried 'speedtest' and 'speedtest-cli')")
        return None
    except Exception as e:
        logger.warning("speedtest-cli failed: %s", e)
        return None

    try:
        data = json.loads(stdout.strip())
        # speedtest-cli JSON: download/upload in bits/s
        download_mbps = float(data["download"]) / 1_000_000
        upload_mbps = float(data["upload"]) / 1_000_000
        ping_ms = float(data["ping"])
        server = data.get("server", {})
        server_name = f"{server.get('name', '')} ({server.get('country', '')})"
        server_name = server_name.strip(" ()")

        logger.info(
            "speedtest-cli: ↓%.1f Mbps ↑%.1f Mbps ping=%.1fms [single-threaded fallback]",
            download_mbps,
            upload_mbps,
            ping_ms,
        )
        return SpeedTestResult(
            download_mbps=download_mbps,
            upload_mbps=upload_mbps,
            ping_ms=ping_ms,
            server=server_name or None,
            backend="ookla-cli",
        )
    except (json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
        logger.warning("Failed to parse speedtest-cli output: %s", e)
        return None
