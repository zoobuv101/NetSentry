"""NetSentry ARP sweep scanner."""

from __future__ import annotations

import ipaddress
import logging
import re

from netsentry.scanner.models import DiscoveredHost
from netsentry.scanner.utils import run_subprocess

logger = logging.getLogger(__name__)

# arp-scan output line: IP\tMAC\tVendor
_ARP_LINE = re.compile(
    r"^(\d{1,3}(?:\.\d{1,3}){3})\s+"
    r"([0-9a-fA-F]{2}(?:[:\-][0-9a-fA-F]{2}){5})"
    r"(?:\s+(.*))?$"
)

# Re-export for mocking in tests
_run_subprocess = run_subprocess


def _validate_subnet(subnet: str) -> None:
    try:
        ipaddress.IPv4Network(subnet, strict=False)
    except ValueError:
        raise ValueError(f"Invalid subnet CIDR: '{subnet}'") from None


async def arp_sweep(
    subnet: str,
    exclusions: set[str] | None = None,
    timeout: float = 30.0,
) -> list[DiscoveredHost]:
    """
    Perform an ARP sweep of the given subnet using arp-scan.

    Args:
        subnet: CIDR notation e.g. '192.168.1.0/24'
        exclusions: Set of IP addresses to exclude from results
        timeout: Maximum seconds to wait for arp-scan to complete

    Returns:
        List of DiscoveredHost objects. Empty list on tool failure.
    """
    _validate_subnet(subnet)
    exclusions = exclusions or set()

    try:
        stdout, stderr = await _run_subprocess(
            ["arp-scan", "--localnet", "--quiet", subnet],
            timeout=timeout,
        )
    except FileNotFoundError:
        logger.warning("arp-scan not found — ARP sweep unavailable. Install arp-scan.")
        return []
    except Exception as e:
        logger.warning("arp-scan failed: %s", e)
        return []

    hosts: list[DiscoveredHost] = []
    seen_macs: set[str] = set()

    for line in stdout.splitlines():
        match = _ARP_LINE.match(line.strip())
        if not match:
            continue
        ip, mac, vendor = match.group(1), match.group(2), match.group(3)

        if ip in exclusions:
            continue

        # Normalise MAC and deduplicate
        from netsentry.db.utils import normalise_mac

        try:
            norm_mac = normalise_mac(mac)
        except ValueError:
            continue

        if norm_mac in seen_macs:
            continue
        seen_macs.add(norm_mac)

        hosts.append(
            DiscoveredHost(
                ip=ip,
                mac=norm_mac,
                vendor=vendor.strip() if vendor else None,
                source="arp",
            )
        )

    logger.debug("ARP sweep %s: found %d hosts", subnet, len(hosts))
    return hosts
