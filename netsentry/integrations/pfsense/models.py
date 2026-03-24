"""pfSense data models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ArpEntry:
    """A single ARP table entry from pfSense."""

    ip: str
    mac: str
    interface: str


@dataclass
class DhcpLease:
    """A DHCP lease from pfSense dhcpd.leases."""

    mac: str
    ip: str
    hostname: str | None = None
    starts: str | None = None
    ends: str | None = None
