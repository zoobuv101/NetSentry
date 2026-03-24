"""NetSentry scanner data models."""

from __future__ import annotations

from dataclasses import dataclass, field

from netsentry.db.utils import normalise_mac


@dataclass
class DiscoveredHost:
    """A host discovered by any scanner method."""

    ip: str
    mac: str | None = None
    hostname: str | None = None
    vendor: str | None = None
    source: str = "scan"  # arp, icmp, netbios, mdns, ssdp

    def __post_init__(self) -> None:
        if self.mac is not None:
            self.mac = normalise_mac(self.mac)


@dataclass
class PortScanResult:
    """Result of a TCP port scan for a single host."""

    ip: str
    open_ports: list[int] = field(default_factory=list)


@dataclass
class ServiceRecord:
    """A detected service on an open port."""

    port: int
    protocol: str
    service: str | None = None
    version: str | None = None


@dataclass
class OsFingerprint:
    """OS detection result from nmap -O."""

    os_family: str
    os_version: str | None = None
    confidence: float = 0.0


@dataclass
class MdnsRecord:
    """An mDNS/Bonjour service announcement."""

    ip: str
    service_type: str
    name: str | None = None


@dataclass
class SsdpRecord:
    """A SSDP/UPnP device announcement."""

    ip: str
    device_type: str | None = None
    usn: str | None = None
    location: str | None = None
