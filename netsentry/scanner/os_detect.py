"""NetSentry OS fingerprinting via nmap -O."""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET

from netsentry.scanner.models import OsFingerprint
from netsentry.scanner.utils import run_subprocess

logger = logging.getLogger(__name__)

_run_subprocess = run_subprocess


async def os_fingerprint(
    host: str,
    timeout: float = 30.0,
) -> OsFingerprint | None:
    """
    Run nmap OS fingerprinting on a single host.

    Requires CAP_NET_RAW (already granted to the scanner container).

    Args:
        host: IP address to fingerprint
        timeout: Maximum seconds to wait

    Returns:
        OsFingerprint if OS detected with sufficient confidence, else None.
    """
    try:
        stdout, _ = await _run_subprocess(
            ["nmap", "-O", "--osscan-guess", "-oX", "-", host],
            timeout=timeout,
        )
    except FileNotFoundError:
        logger.warning("nmap not found — OS fingerprinting unavailable.")
        return None
    except Exception as e:
        logger.warning("nmap OS fingerprint failed: %s", e)
        return None

    return _parse_os_xml(stdout)


def _parse_os_xml(xml_text: str) -> OsFingerprint | None:
    """Parse nmap -O XML output and return best OS match, or None."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return None

    best_accuracy = 0
    best: OsFingerprint | None = None

    for host in root.findall("host"):
        os_el = host.find("os")
        if os_el is None:
            continue
        for match in os_el.findall("osmatch"):
            accuracy = int(match.get("accuracy", "0"))
            if accuracy <= best_accuracy:
                continue
            # Get OS family from first osclass child
            osclass = match.find("osclass")
            if osclass is None:
                continue
            os_family = osclass.get("osfamily", "Unknown")
            os_gen = osclass.get("osgen")
            best_accuracy = accuracy
            best = OsFingerprint(
                os_family=os_family,
                os_version=os_gen,
                confidence=accuracy / 100.0,
            )

    return best
