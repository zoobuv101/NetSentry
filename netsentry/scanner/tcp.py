"""NetSentry TCP port scanner and service detector."""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET

from netsentry.scanner.models import PortScanResult, ServiceRecord
from netsentry.scanner.utils import run_subprocess

logger = logging.getLogger(__name__)

# Common ports probed in Standard scan profile
DEFAULT_PORTS = [
    21,
    22,
    23,
    25,
    53,
    80,
    110,
    143,
    443,
    445,
    554,
    1883,
    3306,
    5353,
    5900,
    8080,
    8443,
    8883,
    9100,
]

_run_subprocess = run_subprocess


def _ports_arg(ports: list[int]) -> str:
    return ",".join(str(p) for p in ports)


def _parse_nmap_xml(xml_text: str) -> dict[str, list[int]]:
    """Parse nmap XML output. Returns {ip: [open_ports]}."""
    results: dict[str, list[int]] = {}
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        logger.warning("Failed to parse nmap XML output")
        return results

    for host in root.findall("host"):
        addr_el = host.find("address[@addrtype='ipv4']")
        if addr_el is None:
            continue
        ip = addr_el.get("addr", "")
        open_ports: list[int] = []
        ports_el = host.find("ports")
        if ports_el is not None:
            for port_el in ports_el.findall("port"):
                state_el = port_el.find("state")
                if state_el is not None and state_el.get("state") == "open":
                    try:
                        open_ports.append(int(port_el.get("portid", "0")))
                    except ValueError:
                        pass
        results[ip] = open_ports
    return results


async def tcp_syn_probe(
    hosts: list[str],
    ports: list[int] | None = None,
    timeout: float = 60.0,
) -> list[PortScanResult]:
    """
    Run a TCP SYN scan on a list of hosts using nmap.

    Args:
        hosts: List of IP addresses to scan
        ports: Port list to probe (defaults to DEFAULT_PORTS)
        timeout: Maximum seconds to wait

    Returns:
        List of PortScanResult. Empty list on tool failure.
    """
    if not hosts:
        return []

    ports = ports or DEFAULT_PORTS
    port_spec = _ports_arg(ports)

    try:
        stdout, _ = await _run_subprocess(
            ["nmap", "-sS", "-p", port_spec, "-oX", "-", "--open"] + hosts,
            timeout=timeout,
        )
    except FileNotFoundError:
        logger.warning("nmap not found — TCP port scanning unavailable. Install nmap.")
        return []
    except Exception as e:
        logger.warning("nmap TCP scan failed: %s", e)
        return []

    parsed = _parse_nmap_xml(stdout)
    return [PortScanResult(ip=ip, open_ports=open_ports) for ip, open_ports in parsed.items()]


def _parse_services_xml(xml_text: str, ip: str) -> list[ServiceRecord]:
    """Parse nmap -sV XML output for a single host."""
    services: list[ServiceRecord] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return services

    for host in root.findall("host"):
        addr_el = host.find("address[@addrtype='ipv4']")
        if addr_el is None or addr_el.get("addr") != ip:
            continue
        ports_el = host.find("ports")
        if ports_el is None:
            continue
        for port_el in ports_el.findall("port"):
            state_el = port_el.find("state")
            if state_el is None or state_el.get("state") != "open":
                continue
            portid = int(port_el.get("portid", "0"))
            protocol = port_el.get("protocol", "tcp")
            svc_el = port_el.find("service")
            if svc_el is not None:
                name = svc_el.get("name")
                product = svc_el.get("product", "")
                version = svc_el.get("version", "")
                version_str = f"{product} {version}".strip() or None
                services.append(
                    ServiceRecord(
                        port=portid,
                        protocol=protocol,
                        service=name,
                        version=version_str,
                    )
                )
    return services


async def service_detect(
    host: str,
    ports: list[int] | None = None,
    timeout: float = 60.0,
) -> list[ServiceRecord]:
    """
    Run nmap -sV service detection on a single host.

    Args:
        host: IP address to scan
        ports: Ports to probe (defaults to DEFAULT_PORTS)
        timeout: Maximum seconds to wait

    Returns:
        List of ServiceRecord. Empty on tool failure.
    """
    ports = ports or DEFAULT_PORTS
    port_spec = _ports_arg(ports)

    try:
        stdout, _ = await _run_subprocess(
            ["nmap", "-sV", "-p", port_spec, "-oX", "-", host],
            timeout=timeout,
        )
    except FileNotFoundError:
        logger.warning("nmap not found — service detection unavailable.")
        return []
    except Exception as e:
        logger.warning("nmap service detect failed: %s", e)
        return []

    return _parse_services_xml(stdout, host)
