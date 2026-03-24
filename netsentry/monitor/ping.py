"""NetSentry availability ping probe using fping."""

from __future__ import annotations

import logging
import re

from netsentry.scanner.utils import run_subprocess

logger = logging.getLogger(__name__)

# fping verbose output: "IP : [N], SIZE bytes, RTT ms (...)"
_ALIVE_RE = re.compile(r"^([\d.]+)\s+:\s+\[\d+\],\s+\d+\s+bytes,\s+([\d.]+)\s+ms")
# fping loss output: "IP : xmt/rcv/%loss = N/N/100%"
_DEAD_RE = re.compile(r"^([\d.]+)\s+:")

_run_subprocess = run_subprocess


async def ping_host(ip: str, count: int = 1, timeout: float = 5.0) -> tuple[bool, float | None]:
    """
    Ping a single host and return (alive, rtt_ms).

    Args:
        ip: IP address to probe
        count: Number of ping packets to send
        timeout: Maximum seconds to wait

    Returns:
        (True, rtt_ms) if alive, (False, None) if unreachable or error.
    """
    results = await ping_hosts_batch([ip], count=count, timeout=timeout)
    return results.get(ip, (False, None))


async def ping_hosts_batch(
    ips: list[str],
    count: int = 1,
    timeout: float = 10.0,
) -> dict[str, tuple[bool, float | None]]:
    """
    Ping multiple hosts in a single fping call.

    Args:
        ips: List of IP addresses to probe
        count: Packets per host
        timeout: Total seconds to wait for all responses

    Returns:
        Dict mapping IP → (alive, rtt_ms).
        Hosts not in the result had no response.
    """
    if not ips:
        return {}

    try:
        stdout, _ = await _run_subprocess(
            ["fping", "-c", str(count), "-q"] + ips,
            timeout=timeout,
        )
    except FileNotFoundError:
        logger.warning("fping not found — availability monitoring unavailable")
        return dict.fromkeys(ips, (False, None))
    except Exception as e:
        logger.warning("fping batch probe failed: %s", e)
        return dict.fromkeys(ips, (False, None))

    results: dict[str, tuple[bool, float | None]] = {}

    for line in stdout.splitlines():
        alive_match = _ALIVE_RE.match(line.strip())
        if alive_match:
            ip = alive_match.group(1)
            rtt = float(alive_match.group(2))
            results[ip] = (True, rtt)
            continue

        dead_match = _DEAD_RE.match(line.strip())
        if dead_match and "100%" in line:
            results[dead_match.group(1)] = (False, None)

    # Any IPs not seen in output are treated as unreachable
    for ip in ips:
        if ip not in results:
            results[ip] = (False, None)

    alive_count = sum(1 for v in results.values() if v[0])
    logger.debug("Batch ping %d hosts: %d alive", len(ips), alive_count)
    return results
