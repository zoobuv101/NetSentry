"""AdGuard Home integration poller."""

from __future__ import annotations

import json
import logging
from typing import Any, Protocol

import aiosqlite

from netsentry.db.repositories.devices import DeviceRepository
from netsentry.db.utils import to_iso8601, utc_now
from netsentry.integrations.adguard.exceptions import AdGuardError
from netsentry.integrations.adguard.models import AdGuardStats

logger = logging.getLogger(__name__)


class _AdGuardClientProtocol(Protocol):
    async def get_stats(self) -> dict[str, Any]: ...
    async def get_clients(self) -> list[dict[str, Any]]: ...


class AdGuardPoller:
    """Polls AdGuard Home for DNS stats and client names."""

    def __init__(self, client: _AdGuardClientProtocol, conn: aiosqlite.Connection) -> None:
        self._client = client
        self._conn = conn
        self._devices = DeviceRepository(conn)

    async def poll(self) -> None:
        """Execute one poll cycle."""
        try:
            await self._poll_stats()
            await self._poll_clients()
        except AdGuardError as e:
            logger.warning("AdGuard poll failed: %s — continuing", e)
        except Exception as e:
            logger.warning("AdGuard unexpected error: %s", e)

    async def _poll_stats(self) -> None:
        """Fetch DNS stats and store in system_config."""
        raw = await self._client.get_stats()
        stats = AdGuardStats.from_raw(raw)
        stats_json = json.dumps(
            {
                "total_queries": stats.total_queries,
                "blocked_queries": stats.blocked_queries,
                "block_rate": stats.block_rate,
                "avg_processing_ms": stats.avg_processing_ms,
                "updated_at": to_iso8601(utc_now()),
            }
        )
        await self._conn.execute(
            "INSERT OR REPLACE INTO system_config (key, value) VALUES (?, ?)",
            ("adguard.last_stats", stats_json),
        )
        await self._conn.commit()
        logger.debug(
            "AdGuard stats: %d queries, %d blocked (%.1f%%)",
            stats.total_queries,
            stats.blocked_queries,
            stats.block_rate * 100,
        )

    async def _poll_clients(self) -> None:
        """Enrich device hostnames from AdGuard client names."""
        clients = await self._client.get_clients()
        for client in clients:
            name = client.get("name", "").strip()
            if not name:
                continue
            # Each client has a list of IDs (IPs, MACs, or names)
            ids = client.get("ids", [])
            for id_val in ids:
                # Try to find device by IP
                device = await self._find_device_by_ip(id_val)
                if device and not device.hostname:
                    await self._devices.upsert(
                        mac=device.mac_address,
                        ip=device.current_ip,
                        hostname=name,
                        is_online=device.is_online,
                    )
                    logger.debug("AdGuard: enriched %s hostname → %s", device.mac_address, name)

    async def _find_device_by_ip(self, ip: str) -> Any:
        """Look up a device by its current IP."""
        async with self._conn.execute(
            "SELECT mac_address FROM devices WHERE current_ip = ? LIMIT 1", (ip,)
        ) as cur:
            row = await cur.fetchone()
        if row is None:
            return None
        return await self._devices.get(row["mac_address"])
