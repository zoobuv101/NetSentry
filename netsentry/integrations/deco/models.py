"""TP-Link Deco data models."""

from __future__ import annotations

from dataclasses import dataclass

from netsentry.db.utils import normalise_mac


@dataclass
class DecoClientData:
    """A single client from the Deco client_list endpoint."""

    mac: str
    ip: str | None
    name: str | None
    is_online: bool
    device_type: str | None
    connection_type: str | None  # "wireless" or "wired"
    deco_mac: str | None  # MAC of the Deco node this client connects through
    band: str | None  # "2.4GHz" or "5GHz"
    up_speed: int | None  # bytes/sec
    down_speed: int | None  # bytes/sec

    @classmethod
    def from_raw(cls, raw: dict) -> DecoClientData:  # type: ignore[type-arg]
        """Parse a raw Deco client_list dict into a DecoClientData."""
        mac_raw = raw.get("mac", "")
        deco_mac_raw = raw.get("access_host", "")
        try:
            mac = normalise_mac(mac_raw)
        except ValueError:
            mac = mac_raw.lower()
        try:
            deco_mac = normalise_mac(deco_mac_raw) if deco_mac_raw else None
        except ValueError:
            deco_mac = None

        ip = raw.get("ip")
        if ip in ("UNKNOWN", "", None):
            ip = None

        return cls(
            mac=mac,
            ip=ip,
            name=raw.get("name"),
            is_online=bool(raw.get("online", False)),
            device_type=raw.get("type"),
            connection_type=raw.get("connection_type"),
            deco_mac=deco_mac,
            band=raw.get("band"),
            up_speed=raw.get("up_speed"),
            down_speed=raw.get("down_speed"),
        )


@dataclass
class DecoNodeData:
    """A single Deco mesh node from the device_list endpoint."""

    mac: str
    model: str | None
    is_online: bool
    role: str | None  # "main" or "slave"/"satellite"
    cpu_usage: float | None = None
    mem_usage: float | None = None

    @classmethod
    def from_raw(cls, raw: dict) -> DecoNodeData:  # type: ignore[type-arg]
        """Parse a raw Deco device_list dict into a DecoNodeData."""
        mac_raw = raw.get("mac", "")
        try:
            mac = normalise_mac(mac_raw)
        except ValueError:
            mac = mac_raw.lower()

        inet_status = raw.get("inet_status", "")
        is_online = inet_status.lower() == "online"

        return cls(
            mac=mac,
            model=raw.get("device_model"),
            is_online=is_online,
            role=raw.get("role"),
            cpu_usage=raw.get("cpu_usage"),
            mem_usage=raw.get("mem_usage"),
        )
