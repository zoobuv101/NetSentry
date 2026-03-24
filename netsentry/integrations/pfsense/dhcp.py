"""pfSense DHCP lease fetcher."""

from __future__ import annotations

import logging
import re
from typing import Protocol

from netsentry.db.utils import normalise_mac
from netsentry.integrations.pfsense.exceptions import PfSenseError
from netsentry.integrations.pfsense.models import DhcpLease

logger = logging.getLogger(__name__)


class _ClientProtocol(Protocol):
    async def run_command(self, command: str) -> tuple[str, str]: ...


_LEASE_BLOCK_RE = re.compile(r"lease\s+([\d.]+)\s*\{([^}]+)\}", re.DOTALL)
_HARDWARE_RE = re.compile(r"hardware ethernet\s+([0-9a-fA-F:]+);")
_HOSTNAME_RE = re.compile(r'client-hostname\s+"([^"]+)";')
_STARTS_RE = re.compile(r"starts\s+\d+\s+([\d/]+\s+[\d:]+);")
_ENDS_RE = re.compile(r"ends\s+\d+\s+([\d/]+\s+[\d:]+);")

_LEASES_FILE = "/var/dhcpd/var/db/dhcpd.leases"


async def fetch_dhcp_leases(client: _ClientProtocol) -> list[DhcpLease]:
    """
    Fetch and parse DHCP leases from pfSense dhcpd.leases file.

    Returns most recent IP per MAC. Empty list on error.
    """
    try:
        stdout, _ = await client.run_command(f"cat {_LEASES_FILE}")
    except PfSenseError as e:
        logger.warning("Failed to fetch pfSense DHCP leases: %s", e)
        return []

    # Parse all lease blocks, keep most recent per MAC
    leases_by_mac: dict[str, DhcpLease] = {}

    for match in _LEASE_BLOCK_RE.finditer(stdout):
        ip = match.group(1)
        block = match.group(2)

        hw_match = _HARDWARE_RE.search(block)
        if not hw_match:
            continue

        try:
            mac = normalise_mac(hw_match.group(1))
        except ValueError:
            continue

        hostname_match = _HOSTNAME_RE.search(block)
        starts_match = _STARTS_RE.search(block)
        ends_match = _ENDS_RE.search(block)

        lease = DhcpLease(
            mac=mac,
            ip=ip,
            hostname=hostname_match.group(1) if hostname_match else None,
            starts=starts_match.group(1) if starts_match else None,
            ends=ends_match.group(1) if ends_match else None,
        )
        # Keep most recent (later in file = more recent)
        leases_by_mac[mac] = lease

    result = list(leases_by_mac.values())
    logger.debug("pfSense DHCP leases: %d unique devices", len(result))
    return result
