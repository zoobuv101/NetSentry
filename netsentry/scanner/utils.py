"""NetSentry scanner subprocess utilities."""

from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)


async def run_subprocess(
    cmd: list[str],
    timeout: float = 60.0,
) -> tuple[str, str]:
    """
    Run a subprocess asynchronously and return (stdout, stderr).

    Raises:
        FileNotFoundError: If the binary is not found.
        asyncio.TimeoutError: If the command exceeds the timeout.
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
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
