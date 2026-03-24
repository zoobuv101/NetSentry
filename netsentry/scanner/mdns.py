"""NetSentry mDNS/Bonjour listener and parser."""

from __future__ import annotations

import logging
import re

from netsentry.scanner.models import MdnsRecord

logger = logging.getLogger(__name__)

# Match service type pattern: _service._proto.local
_SERVICE_TYPE_RE = re.compile(r"^(_[a-zA-Z0-9\-]+\._(?:tcp|udp))(?:\.local)?$")


def parse_mdns_record(
    name: str,
    ip: str,
    data: str = "",
) -> MdnsRecord | None:
    """
    Parse an mDNS record into an MdnsRecord.

    Args:
        name: The mDNS service name e.g. '_airplay._tcp.local'
        ip: Source IP address
        data: Optional friendly name / TXT data

    Returns:
        MdnsRecord if the name matches a service type pattern, else None.
    """
    match = _SERVICE_TYPE_RE.match(name)
    if not match:
        return None

    service_type = match.group(1)
    return MdnsRecord(
        ip=ip,
        service_type=service_type,
        name=data.strip() or None,
    )


async def start_mdns_listener(
    callback: object,
    timeout: float | None = None,
) -> None:
    """
    Start a passive mDNS multicast listener.

    Calls callback(MdnsRecord) for each valid service announcement received.
    This is a long-running async task — run as an APScheduler background task.

    Note: Full scapy-based implementation is added in US0007 when the
    scanner orchestrator wires all tasks together. This stub allows
    the module to be imported and the parser to be unit tested.
    """
    logger.info("mDNS listener started (stub — full impl in US0007)")
