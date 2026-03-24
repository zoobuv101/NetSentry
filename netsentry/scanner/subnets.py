"""NetSentry subnet detection utilities."""

from __future__ import annotations

import ipaddress
import logging

logger = logging.getLogger(__name__)

try:
    import netifaces  # noqa: F401

    _NETIFACES_AVAILABLE = True
except ImportError:
    netifaces = None  # noqa: F841
    _NETIFACES_AVAILABLE = False

# Interface name prefixes to exclude from auto-detection
_EXCLUDED_PREFIXES = ("lo", "docker", "br-", "veth", "virbr", "vmnet", "tun", "tap")


def detect_subnets() -> list[str]:
    """
    Auto-detect LAN subnets from host network interfaces.
    Excludes loopback, Docker bridges, and virtual interfaces.
    Returns list of CIDR strings e.g. ['192.168.1.0/24'].
    """
    if netifaces is None:
        logger.warning("netifaces not installed — subnet auto-detection unavailable")
        return []

    subnets: list[str] = []
    for iface in netifaces.interfaces():
        if any(iface.startswith(prefix) for prefix in _EXCLUDED_PREFIXES):
            continue
        addrs = netifaces.ifaddresses(iface)
        ipv4_addrs = addrs.get(netifaces.AF_INET, [])
        for addr in ipv4_addrs:
            ip = addr.get("addr", "")
            netmask = addr.get("netmask", "")
            if not ip or not netmask:
                continue
            try:
                network = ipaddress.IPv4Network(f"{ip}/{netmask}", strict=False)
                cidr = str(network)
                # Skip loopback and link-local
                if network.is_loopback or network.is_link_local:
                    continue
                # Skip Docker/VM bridge ranges
                if any(cidr.startswith(p) for p in ("172.17.", "172.18.", "172.19.")):
                    continue
                if cidr not in subnets:
                    subnets.append(cidr)
                    logger.debug("Auto-detected subnet: %s (interface: %s)", cidr, iface)
            except ValueError:
                continue

    return subnets


def subnets_from_config(config_value: str) -> list[str]:
    """
    Parse a comma-separated subnet list from configuration.
    Validates each entry as a valid CIDR.

    Raises:
        ValueError: If any subnet is not a valid CIDR.
    """
    subnets = []
    for raw in config_value.split(","):
        cidr = raw.strip()
        if not cidr:
            continue
        try:
            ipaddress.IPv4Network(cidr, strict=False)
        except ValueError:
            raise ValueError(f"Invalid subnet CIDR: '{cidr}'") from None
        subnets.append(cidr)
    return subnets


def get_subnets(scan_subnets_config: str | None = None) -> list[str]:
    """
    Get the list of subnets to scan.
    Uses config value if provided, otherwise auto-detects from interfaces.
    """
    if scan_subnets_config:
        return subnets_from_config(scan_subnets_config)
    subnets = detect_subnets()
    if not subnets:
        logger.warning("No subnets detected — set SCAN_SUBNETS in .env")
    return subnets
