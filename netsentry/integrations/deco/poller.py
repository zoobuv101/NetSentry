"""TP-Link Deco mesh integration poller."""

from __future__ import annotations

import logging
from typing import Any, Protocol

import aiosqlite

from netsentry.db.repositories.devices import DeviceRepository
from netsentry.db.repositories.events import EventRepository
from netsentry.db.repositories.ip_assignments import IpAssignmentRepository
from netsentry.db.utils import to_iso8601, utc_now
from netsentry.integrations.deco.exceptions import DecoError
from netsentry.integrations.deco.models import DecoClientData, DecoNodeData

logger = logging.getLogger(__name__)

_CLIENT_LIST_ENDPOINT = "/cgi-bin/luci/;stok=/ds"
_DEVICE_LIST_ENDPOINT = "/cgi-bin/luci/;stok=/ds"


class _DecoClientProtocol(Protocol):
    async def request(
        self, method: str, endpoint: str, payload: dict[str, Any]
    ) -> dict[str, Any]: ...


class DecoPoller:
    """
    Polls the TP-Link Deco local API and writes enrichment data to the DB.

    Run as an APScheduler task every 30 seconds.
    """

    def __init__(self, client: _DecoClientProtocol, conn: aiosqlite.Connection) -> None:
        self._client = client
        self._conn = conn
        self._devices = DeviceRepository(conn)
        self._ip_repo = IpAssignmentRepository(conn)
        self._events = EventRepository(conn)
        # In-memory: last seen Deco node per device MAC
        self._last_deco_node: dict[str, str] = {}

    async def poll(self) -> None:
        """Execute one poll cycle: fetch client list and device list."""
        try:
            await self._poll_clients()
            await self._poll_nodes()
        except DecoError as e:
            logger.warning("Deco poll failed: %s — continuing with stale data", e)
        except Exception as e:
            logger.warning("Unexpected Deco poll error: %s", e)

    async def _poll_clients(self) -> None:
        """Fetch client_list and upsert device/mesh_assignment records."""
        resp = await self._client.request(
            "POST",
            _CLIENT_LIST_ENDPOINT,
            {"method": "get", "params": {"page_size": 2000, "page_num": 1}},
        )
        raw_clients = resp.get("data", {}).get("client_list", [])

        for raw in raw_clients:
            client = DecoClientData.from_raw(raw)
            if not client.mac:
                continue

            # Upsert device inventory
            existing = await self._devices.get(client.mac)
            if existing is None:
                await self._devices.upsert(
                    mac=client.mac,
                    ip=client.ip,
                    hostname=client.name,
                    is_online=client.is_online,
                )
            else:
                await self._devices.upsert(
                    mac=client.mac,
                    ip=client.ip or existing.current_ip,
                    hostname=client.name or existing.hostname,
                    is_online=client.is_online,
                )

            # Patch connection_type
            if client.connection_type:
                await self._devices.patch(mac=client.mac, connection_type=client.connection_type)

            # Upsert IP assignment
            if client.ip:
                await self._ip_repo.upsert(mac=client.mac, ip=client.ip, source="deco")

            # Roaming detection
            if client.deco_mac:
                previous_node = self._last_deco_node.get(client.mac)
                if previous_node and previous_node != client.deco_mac:
                    await self._events.create(
                        mac_address=client.mac,
                        event_type="deco.device_roamed",
                        severity="info",
                        details={
                            "from_node": previous_node,
                            "to_node": client.deco_mac,
                        },
                    )
                    logger.info(
                        "Device %s roamed from %s to %s", client.mac, previous_node, client.deco_mac
                    )
                self._last_deco_node[client.mac] = client.deco_mac

            # Write mesh_assignment
            await self._upsert_mesh_assignment(client)

    async def _upsert_mesh_assignment(self, client: DecoClientData) -> None:
        """Insert or update a mesh_assignment row for this device."""
        now = to_iso8601(utc_now())
        existing = await self._conn.execute(
            "SELECT id FROM mesh_assignments WHERE mac_address = ? AND disconnected_at IS NULL",
            (client.mac,),
        )
        row = await existing.fetchone()

        if row is None:
            await self._conn.execute(
                "INSERT INTO mesh_assignments "
                "(mac_address, deco_node_mac, band, connection_type, "
                "up_speed_bps, down_speed_bps, last_known_ip, connected_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    client.mac,
                    client.deco_mac,
                    client.band,
                    client.connection_type,
                    client.up_speed,
                    client.down_speed,
                    client.ip,
                    now,
                ),
            )
        else:
            await self._conn.execute(
                "UPDATE mesh_assignments SET deco_node_mac=?, band=?, "
                "up_speed_bps=?, down_speed_bps=?, last_known_ip=? "
                "WHERE mac_address=? AND disconnected_at IS NULL",
                (
                    client.deco_mac,
                    client.band,
                    client.up_speed,
                    client.down_speed,
                    client.ip,
                    client.mac,
                ),
            )
        await self._conn.commit()

    async def _poll_nodes(self) -> None:
        """Fetch device_list and upsert deco_nodes records."""
        resp = await self._client.request(
            "POST", _DEVICE_LIST_ENDPOINT, {"method": "get", "params": {"device_list_opt": 1}}
        )
        raw_nodes = resp.get("data", {}).get("device_list", [])
        now = to_iso8601(utc_now())

        for raw in raw_nodes:
            node = DecoNodeData.from_raw(raw)
            await self._conn.execute(
                "INSERT OR REPLACE INTO deco_nodes "
                "(mac_address, model, role, is_online, cpu_usage, mem_usage, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    node.mac,
                    node.model,
                    node.role,
                    1 if node.is_online else 0,
                    node.cpu_usage,
                    node.mem_usage,
                    now,
                ),
            )
        await self._conn.commit()
