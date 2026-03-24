"""pfSense ARP table fetcher."""

from __future__ import annotations

import logging
import re
from typing import Protocol

from netsentry.db.utils import normalise_mac
from netsentry.integrations.pfsense.exceptions import PfSenseError
from netsentry.integrations.pfsense.models import ArpEntry

logger = logging.getLogger(__name__)


class _ClientProtocol(Protocol):
    async def run_command(self, command: str) -> tuple[str, str]: ...


# Match: ? (IP) at MAC on IFACE expires in N seconds [ethernet]
_ARP_RE = re.compile(
    r"\?\s+\((\d{1,3}(?:\.\d{1,3}){3})\)\s+at\s+"
    r"([0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5})\s+on\s+(\S+)"
)


async def fetch_arp_table(client: _ClientProtocol) -> list[ArpEntry]:
    """
    Fetch and parse the ARP table from pfSense.

    Returns:
        List of ArpEntry. Empty list on error.
    """
    try:
        stdout, _ = await client.run_command("arp -an")
    except PfSenseError as e:
        logger.warning("Failed to fetch pfSense ARP table: %s", e)
        return []

    entries: list[ArpEntry] = []
    for line in stdout.splitlines():
        match = _ARP_RE.search(line)
        if not match:
            continue
        ip, raw_mac, iface = match.group(1), match.group(2), match.group(3)
        try:
            mac = normalise_mac(raw_mac)
        except ValueError:
            continue
        entries.append(ArpEntry(ip=ip, mac=mac, interface=iface))

    logger.debug("pfSense ARP table: %d entries", len(entries))
    return entries
