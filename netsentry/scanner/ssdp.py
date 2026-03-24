"""NetSentry SSDP/UPnP listener and parser."""

from __future__ import annotations

import logging
import re

from netsentry.scanner.models import SsdpRecord

logger = logging.getLogger(__name__)

# Match NT headers for UPnP device types
_DEVICE_NT_RE = re.compile(r"urn:schemas-upnp-org:device:([^:]+):\d+", re.IGNORECASE)


def parse_ssdp_packet(raw: str, source_ip: str) -> SsdpRecord | None:
    """
    Parse a raw SSDP NOTIFY or M-SEARCH response packet.

    Args:
        raw: Raw HTTP-like SSDP packet as a string
        source_ip: Source IP address of the packet

    Returns:
        SsdpRecord if this is a device announcement, else None.
    """
    headers: dict[str, str] = {}
    for line in raw.splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            headers[key.strip().upper()] = value.strip()

    nt = headers.get("NT", "")
    usn = headers.get("USN")
    location = headers.get("LOCATION")

    if not nt:
        return None

    match = _DEVICE_NT_RE.search(nt)
    if not match:
        return None

    device_type = match.group(1)
    return SsdpRecord(
        ip=source_ip,
        device_type=device_type,
        usn=usn,
        location=location,
    )


async def start_ssdp_listener(
    callback: object,
    timeout: float | None = None,
) -> None:
    """
    Start a passive SSDP multicast listener on UDP 239.255.255.250:1900.

    Calls callback(SsdpRecord) for each valid device announcement.
    Long-running async task — wired into APScheduler in US0007.
    """
    logger.info("SSDP listener started (stub — full impl in US0007)")
