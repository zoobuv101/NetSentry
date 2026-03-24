"""
NetSentry rule-based device identification.

Applies vendor, hostname, and port heuristics to classify devices
before (or instead of) calling the AI identifier.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class IdentificationResult:
    """Result from any identification method."""

    category: str | None = None
    device_type: str | None = None
    confidence: float = 0.0
    source: str = "rules"


# ── Vendor prefix rules ───────────────────────────────────────────────────────
# (vendor substring → category, device_type, confidence)

_VENDOR_RULES: list[tuple[str, str, str, float]] = [
    # Networking
    ("Cisco", "Network Infrastructure", "Cisco Device", 0.85),
    ("pfSense", "Network Infrastructure", "Firewall", 0.95),
    ("Netgate", "Network Infrastructure", "Firewall", 0.90),
    ("Ubiquiti", "Network Infrastructure", "Ubiquiti Device", 0.85),
    ("TP-Link", "Network Infrastructure", "TP-Link Device", 0.80),
    ("Deco", "Network Infrastructure", "Deco Mesh Node", 0.90),
    ("NETGEAR", "Network Infrastructure", "NETGEAR Device", 0.80),
    ("Asus", "Network Infrastructure", "ASUS Device", 0.75),
    # Apple
    ("Apple", "Personal Device", "Apple Device", 0.80),
    # Samsung
    ("Samsung", "Personal Device", "Samsung Device", 0.70),
    # Printers
    ("HP", "Printer", "HP Printer", 0.70),
    ("Canon", "Printer", "Canon Printer", 0.75),
    ("Epson", "Printer", "Epson Printer", 0.75),
    ("Brother", "Printer", "Brother Printer", 0.80),
    ("Xerox", "Printer", "Xerox Printer", 0.80),
    # NAS / Storage
    ("Synology", "NAS / Storage", "Synology NAS", 0.95),
    ("QNAP", "NAS / Storage", "QNAP NAS", 0.95),
    ("Western Digital", "NAS / Storage", "WD NAS", 0.80),
    # Smart Home
    ("Amazon", "Smart Speaker", "Amazon Echo", 0.80),
    ("Google", "Smart Speaker", "Google Device", 0.75),
    ("Sonos", "Smart Speaker", "Sonos Speaker", 0.95),
    ("Philips", "Smart Home", "Philips Device", 0.70),
    ("Belkin", "Smart Home", "Belkin Device", 0.70),
    # Gaming
    ("Sony", "Games Console", "PlayStation", 0.75),
    ("Microsoft", "Games Console", "Xbox", 0.70),
    ("Nintendo", "Games Console", "Nintendo Device", 0.85),
]

# ── Hostname pattern rules ────────────────────────────────────────────────────

_HOSTNAME_RULES: list[tuple[re.Pattern[str], str, str, float]] = [
    (
        re.compile(r"\b(iphone|ipad|macbook|imac|mac-?mini|airpods)\b", re.I),
        "Personal Device",
        "Apple Device",
        0.80,
    ),
    (
        re.compile(r"\b(android|pixel|galaxy|oneplus|huawei)\b", re.I),
        "Personal Device",
        "Android Device",
        0.75,
    ),
    (
        re.compile(r"\b(laptop|desktop|pc|computer|workstation)\b", re.I),
        "Personal Device",
        "Computer",
        0.65,
    ),
    (re.compile(r"\b(printer|print)\b", re.I), "Printer", "Printer", 0.80),
    (re.compile(r"\b(nas|synology|qnap|storage)\b", re.I), "NAS / Storage", "NAS", 0.80),
    (
        re.compile(r"\b(tv|television|firetv|appletv|chromecast|roku)\b", re.I),
        "Smart TV",
        "Smart TV",
        0.85,
    ),
    (
        re.compile(r"\b(echo|alexa|google-?home|homepod)\b", re.I),
        "Smart Speaker",
        "Smart Speaker",
        0.85,
    ),
    (
        re.compile(r"\b(switch|router|gateway|ap|access-?point|deco)\b", re.I),
        "Network Infrastructure",
        "Network Device",
        0.80,
    ),
    (re.compile(r"\b(camera|cam|nvr|dvr)\b", re.I), "Camera", "IP Camera", 0.80),
    (
        re.compile(r"\b(xbox|playstation|ps[345]|nintendo|wii)\b", re.I),
        "Games Console",
        "Games Console",
        0.90,
    ),
    (re.compile(r"\b(phone|mobile)\b", re.I), "Personal Device", "Phone", 0.70),
]

# ── Port-based rules ──────────────────────────────────────────────────────────
# (port set superset check → category, device_type, confidence)

_PORT_RULES: list[tuple[set[int], str, str, float]] = [
    ({9100}, "Printer", "Network Printer", 0.90),
    ({515}, "Printer", "LPD Printer", 0.85),
    ({631}, "Printer", "IPP Printer", 0.85),
    ({445}, "NAS / Storage", "File Server", 0.80),
    ({554}, "Camera", "IP Camera", 0.85),
    ({1935}, "Media Server", "Streaming Server", 0.75),
    ({8096}, "Media Server", "Jellyfin Server", 0.90),
    ({32400}, "Media Server", "Plex Media Server", 0.95),
    ({1883}, "Smart Home", "MQTT Broker", 0.90),
    ({3306}, "Server", "Database Server", 0.80),
    ({5900}, "Personal Device", "Desktop (VNC)", 0.70),
    ({22, 80, 443}, "Network Infrastructure", "Gateway/Router", 0.75),
]


def identify_by_rules(
    vendor: str | None,
    hostname: str | None,
    open_ports: list[int],
) -> IdentificationResult:
    """
    Apply vendor, hostname, and port rules to identify a device.

    Returns the best matching IdentificationResult. If no rule fires,
    returns a result with category=None and confidence=0.0.
    """
    best = IdentificationResult()
    port_set = set(open_ports)

    # 1. Port rules (highest precision)
    for required_ports, category, device_type, confidence in _PORT_RULES:
        if required_ports.issubset(port_set):
            if confidence > best.confidence:
                best = IdentificationResult(
                    category=category,
                    device_type=device_type,
                    confidence=confidence,
                    source="rules:ports",
                )

    # 2. Hostname rules
    if hostname:
        for pattern, category, device_type, confidence in _HOSTNAME_RULES:
            if pattern.search(hostname):
                # Combine with port result if same category
                total_conf = confidence
                if best.category == category:
                    total_conf = min(1.0, confidence + 0.1)
                if total_conf > best.confidence:
                    best = IdentificationResult(
                        category=category,
                        device_type=device_type,
                        confidence=total_conf,
                        source="rules:hostname",
                    )

    # 3. Vendor rules
    if vendor:
        vendor_lower = vendor.lower()
        for prefix, category, device_type, confidence in _VENDOR_RULES:
            if prefix.lower() in vendor_lower:
                # Combine signals if same category
                total_conf = confidence
                if best.category == category:
                    total_conf = min(1.0, confidence + 0.1)
                if total_conf > best.confidence:
                    best = IdentificationResult(
                        category=category,
                        device_type=device_type,
                        confidence=total_conf,
                        source="rules:vendor",
                    )

    return best
