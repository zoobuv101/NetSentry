"""pfSense network interface status endpoint."""

from __future__ import annotations

import logging
import re

from fastapi import APIRouter, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()

# Matches interface header: "em0: flags=8943<UP,BROADCAST,RUNNING,...> metric 0 mtu 1500"
_IFACE_RE = re.compile(r"^(\w+):\s+flags=\w+<([^>]*)>", re.MULTILINE)
# Matches: "        inet 192.168.1.254 netmask 0xffffff00 broadcast 192.168.1.255"
_INET_RE = re.compile(r"inet\s+([\d.]+)\s+netmask")
# Matches: "        inet6 fe80::..."
_INET6_RE = re.compile(r"inet6\s+(\S+)")
# Matches: "        media: Ethernet 1000baseT <full-duplex>"
_MEDIA_RE = re.compile(r"media:\s+(.+)")
# Matches: "        description: WAN"
_DESC_RE = re.compile(r"description:\s+(.+)")


class InterfaceStatus(BaseModel):
    name: str
    description: str | None
    up: bool
    running: bool
    ip_address: str | None
    ip6_address: str | None
    media: str | None
    flags: list[str]


class InterfacesResponse(BaseModel):
    interfaces: list[InterfaceStatus]
    source: str  # "pfsense" or "unavailable"


def _parse_ifconfig(output: str) -> list[InterfaceStatus]:
    """Parse ifconfig output into structured interface records."""
    interfaces = []

    # Split on interface name at start of line
    blocks = re.split(r"(?=^\w+:)", output, flags=re.MULTILINE)

    for block in blocks:
        block = block.strip()
        if not block:
            continue

        # Interface name and flags
        iface_match = _IFACE_RE.match(block)
        if not iface_match:
            continue

        name = iface_match.group(1)
        flags_str = iface_match.group(2)
        flags = [f.strip() for f in flags_str.split(",") if f.strip()]

        # Skip loopback and internal pfSense interfaces
        if name in ("lo0", "enc0", "pflog0", "pfsync0"):
            continue

        up = "UP" in flags
        running = "RUNNING" in flags

        # Extract fields from block lines
        ip_match = _INET_RE.search(block)
        ip6_match = _INET6_RE.search(block)
        media_match = _MEDIA_RE.search(block)
        desc_match = _DESC_RE.search(block)

        ip_address = ip_match.group(1) if ip_match else None
        ip6_raw = ip6_match.group(1) if ip6_match else None
        # Skip link-local IPv6 addresses (fe80::) unless it's the only one
        ip6_address = ip6_raw if ip6_raw and not ip6_raw.startswith("fe80::") else None

        media = media_match.group(1).strip() if media_match else None
        description = desc_match.group(1).strip() if desc_match else None

        interfaces.append(
            InterfaceStatus(
                name=name,
                description=description,
                up=up,
                running=running,
                ip_address=ip_address,
                ip6_address=ip6_address,
                media=media,
                flags=flags,
            )
        )

    return interfaces


@router.get("/pfsense/interfaces", response_model=InterfacesResponse)
async def get_pfsense_interfaces(request: Request) -> InterfacesResponse:
    """
    Fetch real-time pfSense interface status via SSH.
    Returns UP/DOWN, IP addresses, and media type for each interface.
    """
    # Get settings from environment
    import os

    host = os.environ.get("PFSENSE_HOST")
    username = os.environ.get("PFSENSE_USERNAME", "admin")
    key_path = os.environ.get("PFSENSE_KEY_PATH", "/config/id_rsa")
    port = int(os.environ.get("PFSENSE_SSH_PORT", "22"))
    enabled = os.environ.get("ENABLE_PFSENSE_INTEGRATION", "true").lower() == "true"

    if not enabled or not host:
        return InterfacesResponse(interfaces=[], source="unavailable")

    try:
        from netsentry.integrations.pfsense.client import PfSenseClient

        client = PfSenseClient(host=host, username=username, key_path=key_path, port=port)
        stdout, _ = await client.run_command("ifconfig")
        interfaces = _parse_ifconfig(stdout)
        logger.debug("pfSense interfaces fetched: %d", len(interfaces))
        return InterfacesResponse(interfaces=interfaces, source="pfsense")
    except Exception as e:
        logger.warning("pfSense interface fetch failed: %s", e)
        return InterfacesResponse(interfaces=[], source="unavailable")
