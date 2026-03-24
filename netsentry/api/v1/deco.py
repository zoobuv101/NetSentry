"""NetSentry Deco mesh topology endpoint."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()


class DecoNodeResponse(BaseModel):
    mac_address: str
    model: str | None
    role: str | None
    is_online: bool
    cpu_usage: float | None
    mem_usage: float | None


class MeshClientResponse(BaseModel):
    mac_address: str
    deco_node_mac: str | None
    band: str | None
    connection_type: str | None
    up_speed_bps: int | None
    down_speed_bps: int | None
    last_known_ip: str | None


class TopologyResponse(BaseModel):
    nodes: list[DecoNodeResponse]
    clients: list[MeshClientResponse]


@router.get("/deco/topology", response_model=TopologyResponse)
async def get_deco_topology(request: Request) -> TopologyResponse:
    """
    Return the current Deco mesh topology.

    Includes all known Deco nodes and their connected clients,
    with band, speeds, and connection type.
    """
    conn = request.app.state.db

    # Fetch deco nodes
    async with conn.execute(
        "SELECT mac_address, model, role, is_online, cpu_usage, mem_usage "
        "FROM deco_nodes ORDER BY role, mac_address"
    ) as cur:
        node_rows = await cur.fetchall()

    # Fetch current mesh assignments (active only — no disconnected_at)
    async with conn.execute(
        "SELECT mac_address, deco_node_mac, band, connection_type, "
        "up_speed_bps, down_speed_bps, last_known_ip "
        "FROM mesh_assignments WHERE disconnected_at IS NULL "
        "ORDER BY mac_address"
    ) as cur:
        client_rows = await cur.fetchall()

    nodes = [
        DecoNodeResponse(
            mac_address=row["mac_address"],
            model=row["model"],
            role=row["role"],
            is_online=bool(row["is_online"]),
            cpu_usage=row["cpu_usage"],
            mem_usage=row["mem_usage"],
        )
        for row in node_rows
    ]

    clients = [
        MeshClientResponse(
            mac_address=row["mac_address"],
            deco_node_mac=row["deco_node_mac"],
            band=row["band"],
            connection_type=row["connection_type"],
            up_speed_bps=row["up_speed_bps"],
            down_speed_bps=row["down_speed_bps"],
            last_known_ip=row["last_known_ip"],
        )
        for row in client_rows
    ]

    return TopologyResponse(nodes=nodes, clients=clients)
