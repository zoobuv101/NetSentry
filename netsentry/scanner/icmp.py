"""NetSentry ICMP ping sweep scanner."""

from __future__ import annotations

import logging
import re

from netsentry.scanner.models import DiscoveredHost
from netsentry.scanner.utils import run_subprocess

logger = logging.getLogger(__name__)

_IP_LINE = re.compile(r"^(\d{1,3}(?:\.\d{1,3}){3})\s*$")

_run_subprocess = run_subprocess


async def icmp_sweep(
    subnet: str,
    exclusions: set[str] | None = None,
    timeout: float = 30.0,
) -> list[DiscoveredHost]:
    """
    Perform an ICMP ping sweep using fping.
    Returns hosts that responded; MAC is None (ICMP doesn't reveal MAC).

    Args:
        subnet: CIDR notation e.g. '192.168.1.0/24'
        exclusions: Set of IP addresses to exclude
        timeout: Maximum seconds to wait

    Returns:
        List of DiscoveredHost objects. Empty list on tool failure.
    """
    exclusions = exclusions or set()

    try:
        # fping -a: show alive hosts only; -g: generate target list from CIDR
        stdout, _ = await _run_subprocess(
            ["fping", "-a", "-g", subnet],
            timeout=timeout,
        )
    except FileNotFoundError:
        logger.warning("fping not found — ICMP sweep unavailable. Install fping.")
        return []
    except Exception as e:
        logger.warning("fping failed: %s", e)
        return []

    hosts: list[DiscoveredHost] = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        # fping -a output is one IP per line for alive hosts
        if re.match(r"^\d{1,3}(?:\.\d{1,3}){3}$", line):
            if line not in exclusions:
                hosts.append(DiscoveredHost(ip=line, mac=None, source="icmp"))

    logger.debug("ICMP sweep %s: found %d hosts", subnet, len(hosts))
    return hosts
