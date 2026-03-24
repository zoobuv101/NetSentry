"""NetSentry scanner subprocess utilities."""

from __future__ import annotations

import asyncio
import logging
import os

logger = logging.getLogger(__name__)

# When running as non-root (UID != 0), prefix network scanning commands with sudo.
# The Dockerfile grants passwordless sudo for arp-scan, nmap, fping, nbtscan.
_NEED_SUDO = {"arp-scan", "nmap", "fping", "nbtscan"}
_IS_ROOT = os.getuid() == 0


def _build_cmd(cmd: list[str]) -> list[str]:
    """Prepend sudo if running as non-root and the binary needs it."""
    if _IS_ROOT:
        return cmd
    if cmd and cmd[0] in _NEED_SUDO:
        return ["sudo", "-n"] + cmd
    return cmd


async def run_subprocess(
    cmd: list[str],
    timeout: float = 60.0,
) -> tuple[str, str]:
    """
    Run a subprocess asynchronously and return (stdout, stderr).

    Automatically prepends sudo for network scanning tools when running
    as non-root. Raises FileNotFoundError or asyncio.TimeoutError on failure.
    """
    actual_cmd = _build_cmd(cmd)
    try:
        proc = await asyncio.create_subprocess_exec(
            *actual_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError:
        raise
    except OSError as e:
        raise FileNotFoundError(f"Failed to start {cmd[0]}: {e}") from e

    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except TimeoutError:
        proc.kill()
        await proc.communicate()
        raise

    return stdout_bytes.decode(errors="replace"), stderr_bytes.decode(errors="replace")
