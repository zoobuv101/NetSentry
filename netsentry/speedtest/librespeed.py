"""NetSentry LibreSpeed CLI runner."""

from __future__ import annotations

import json
import logging

from netsentry.scanner.utils import run_subprocess
from netsentry.speedtest.models import SpeedTestResult

logger = logging.getLogger(__name__)

_run_subprocess = run_subprocess


async def run_librespeed(
    server_url: str | None = None,
    timeout: float = 120.0,
) -> SpeedTestResult | None:
    """
    Run a speed test using the librespeed-cli binary.

    Args:
        server_url: Optional custom LibreSpeed server URL
        timeout: Max seconds to wait for the test to complete

    Returns:
        SpeedTestResult on success, None on any failure.
    """
    cmd = ["librespeed-cli", "--json", "--no-icmp"]
    if server_url:
        cmd += ["--server", server_url]

    try:
        stdout, _ = await _run_subprocess(cmd, timeout=timeout)
    except FileNotFoundError:
        logger.warning("librespeed-cli not found — install it or set SPEEDTEST_BACKEND=ookla")
        return None
    except Exception as e:
        logger.warning("librespeed-cli failed: %s", e)
        return None

    # librespeed outputs a JSON array or single JSON object
    stdout = stdout.strip()
    if not stdout:
        logger.warning("librespeed-cli returned empty output")
        return None

    try:
        data = json.loads(stdout)
        # May be an array — use first result
        if isinstance(data, list):
            if not data:
                return None
            data = data[0]

        download = float(data.get("download", 0))
        upload = float(data.get("upload", 0))
        ping = float(data.get("ping", 0))
        server_info = data.get("server", {})
        server_name = server_info.get("name") if isinstance(server_info, dict) else None

        return SpeedTestResult(
            download_mbps=download,
            upload_mbps=upload,
            ping_ms=ping,
            server=server_name,
            backend="librespeed",
        )
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        logger.warning("Failed to parse librespeed-cli output: %s", e)
        return None
