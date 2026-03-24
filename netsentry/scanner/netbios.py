"""NetSentry NetBIOS scanner."""

from __future__ import annotations

import logging
import re

from netsentry.scanner.models import DiscoveredHost
from netsentry.scanner.utils import run_subprocess

logger = logging.getLogger(__name__)

# nbtscan output: IP  Name  Server  User  MAC
_NBTSCAN_LINE = re.compile(
    r"^(\d{1,3}(?:\.\d{1,3}){3})\s+"
    r"(\S+)\s+"
    r"\S+\s+"
    r"\S+\s+"
    r"([0-9a-fA-F]{2}(?:[:\-][0-9a-fA-F]{2}){5})"
)

_run_subprocess = run_subprocess


async def netbios_scan(
    hosts: list[str],
    timeout: float = 15.0,
) -> list[DiscoveredHost]:
    """
    Query NetBIOS names for a list of host IPs using nbtscan.

    Args:
        hosts: List of IP addresses to query
        timeout: Maximum seconds to wait

    Returns:
        List of DiscoveredHost with hostname populated. Empty on tool failure.
    """
    if not hosts:
        return []

    try:
        stdout, _ = await _run_subprocess(
            ["nbtscan", "-q"] + hosts,
            timeout=timeout,
        )
    except FileNotFoundError:
        logger.warning("nbtscan not found — NetBIOS names unavailable. Install nbtscan.")
        return []
    except Exception as e:
        logger.warning("nbtscan failed: %s", e)
        return []

    results: list[DiscoveredHost] = []
    for line in stdout.splitlines():
        match = _NBTSCAN_LINE.match(line.strip())
        if not match:
            continue
        ip = match.group(1)
        name = match.group(2)
        mac = match.group(3)

        from netsentry.db.utils import normalise_mac

        try:
            norm_mac = normalise_mac(mac)
        except ValueError:
            norm_mac = None

        results.append(
            DiscoveredHost(
                ip=ip,
                mac=norm_mac,
                hostname=name,
                source="netbios",
            )
        )

    logger.debug("NetBIOS scan: found %d names", len(results))
    return results
