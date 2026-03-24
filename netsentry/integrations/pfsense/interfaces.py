"""pfSense interface status poller — runs on a schedule, caches in app state."""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# Matches interface header: "em0: flags=8943<UP,BROADCAST,RUNNING,...> metric 0 mtu 1500"
_IFACE_RE = re.compile(r"^(\w+):\s+flags=\w+<([^>]*)>", re.MULTILINE)
_INET_RE = re.compile(r"inet\s+([\d.]+)\s+netmask")
_INET6_RE = re.compile(r"inet6\s+(\S+)")
_MEDIA_RE = re.compile(r"media:\s+(.+)")
_DESC_RE = re.compile(r"description:\s+(.+)")

_SKIP_IFACES = {"lo0", "enc0", "pflog0", "pfsync0"}


def parse_ifconfig(output: str) -> list[dict[str, object]]:
    """Parse ifconfig output into a list of interface dicts."""
    interfaces = []
    for block in re.split(r"(?=^\w+:)", output, flags=re.MULTILINE):
        block = block.strip()
        if not block:
            continue
        m = _IFACE_RE.match(block)
        if not m:
            continue
        name = m.group(1)
        if name in _SKIP_IFACES:
            continue

        flags = [f.strip() for f in m.group(2).split(",") if f.strip()]
        ip_m = _INET_RE.search(block)
        ip6_m = _INET6_RE.search(block)
        media_m = _MEDIA_RE.search(block)
        desc_m = _DESC_RE.search(block)

        ip6 = ip6_m.group(1) if ip6_m else None
        if ip6 and ip6.startswith("fe80::"):
            ip6 = None

        interfaces.append(
            {
                "name": name,
                "description": desc_m.group(1).strip() if desc_m else None,
                "up": "UP" in flags,
                "running": "RUNNING" in flags,
                "ip_address": ip_m.group(1) if ip_m else None,
                "ip6_address": ip6,
                "media": media_m.group(1).strip() if media_m else None,
                "flags": flags,
            }
        )
    return interfaces


class InterfacePoller:
    """
    Polls pfSense for interface status on a schedule.
    Stores result in-memory so the API endpoint never waits for SSH.
    """

    def __init__(
        self,
        host: str,
        username: str,
        key_path: str,
        port: int = 22,
    ) -> None:
        self._host = host
        self._username = username
        self._key_path = key_path
        self._port = port
        self.cached: list[dict[str, object]] = []
        self.last_updated: str | None = None

    async def poll(self) -> None:
        """Fetch ifconfig from pfSense and update the in-memory cache."""
        try:
            from netsentry.db.utils import to_iso8601, utc_now
            from netsentry.integrations.pfsense.client import PfSenseClient

            client = PfSenseClient(
                host=self._host,
                username=self._username,
                key_path=self._key_path,
                port=self._port,
            )
            stdout, _ = await client.run_command("ifconfig")
            self.cached = parse_ifconfig(stdout)
            self.last_updated = to_iso8601(utc_now())
            logger.debug("Interface cache updated: %d interfaces", len(self.cached))
        except Exception as e:
            logger.warning("Interface poll failed: %s", e)
