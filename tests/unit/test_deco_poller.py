"""
US0010 + US0011 — TDD tests for Deco poller DB persistence and roaming detection.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest


@pytest.fixture
async def repos(tmp_path: pytest.TempPathFactory):  # type: ignore[no-untyped-def]
    from netsentry.db.connection import get_connection, run_migrations
    from netsentry.db.repositories.devices import DeviceRepository
    from netsentry.db.repositories.events import EventRepository

    db_path = str(tmp_path / "test.db")  # type: ignore[operator]
    run_migrations(db_path)
    conn = await get_connection(db_path)
    yield {"devices": DeviceRepository(conn), "events": EventRepository(conn), "conn": conn}
    await conn.close()


# ── Deco models ───────────────────────────────────────────────────────────────


class TestDecoModels:
    def test_deco_client_data_parses(self) -> None:
        """DecoClientData parses a raw Deco client_list entry."""
        from netsentry.integrations.deco.models import DecoClientData

        raw = {
            "mac": "AA-BB-CC-DD-EE-FF",
            "ip": "192.168.68.10",
            "name": "Ian's Phone",
            "online": True,
            "type": "Phone",
            "connection_type": "wireless",
            "access_host": "11-22-33-44-55-66",
            "band": "5GHz",
            "up_speed": 1024,
            "down_speed": 4096,
        }
        data = DecoClientData.from_raw(raw)
        assert data.mac == "aa:bb:cc:dd:ee:ff"
        assert data.ip == "192.168.68.10"
        assert data.name == "Ian's Phone"
        assert data.band == "5GHz"
        assert data.deco_mac == "11:22:33:44:55:66"

    def test_deco_node_data_parses(self) -> None:
        """DecoNodeData parses a raw device_list entry."""
        from netsentry.integrations.deco.models import DecoNodeData

        raw = {
            "mac": "11-22-33-44-55-66",
            "device_model": "M9 Plus",
            "inet_status": "online",
            "role": "main",
        }
        node = DecoNodeData.from_raw(raw)
        assert node.mac == "11:22:33:44:55:66"
        assert node.is_online is True
        assert node.role == "main"


# ── Deco poller ───────────────────────────────────────────────────────────────


class TestDecoPoller:
    @pytest.mark.asyncio
    async def test_poller_writes_mesh_assignment(self, repos) -> None:  # type: ignore[no-untyped-def]
        """Poller creates mesh_assignment row for connected client."""
        from netsentry.integrations.deco.poller import DecoPoller

        # Pre-create the device
        await repos["devices"].upsert(mac="aa:bb:cc:dd:ee:ff", ip="192.168.68.10")

        mock_client = AsyncMock()
        mock_client.request.side_effect = [
            # client_list response
            {
                "data": {
                    "client_list": [
                        {
                            "mac": "AA-BB-CC-DD-EE-FF",
                            "ip": "192.168.68.10",
                            "name": "Laptop",
                            "online": True,
                            "type": "Laptop",
                            "connection_type": "wireless",
                            "access_host": "11-22-33-44-55-66",
                            "band": "5GHz",
                            "up_speed": 512,
                            "down_speed": 2048,
                        }
                    ]
                }
            },
            # device_list response
            {
                "data": {
                    "device_list": [
                        {
                            "mac": "11-22-33-44-55-66",
                            "device_model": "Deco M9",
                            "inet_status": "online",
                            "role": "main",
                        }
                    ]
                }
            },
        ]

        poller = DecoPoller(client=mock_client, conn=repos["conn"])
        await poller.poll()

        # Check mesh_assignments table was written
        async with repos["conn"].execute(
            "SELECT * FROM mesh_assignments WHERE mac_address = ?", ("aa:bb:cc:dd:ee:ff",)
        ) as cur:
            row = await cur.fetchone()
        assert row is not None
        assert row["band"] == "5GHz"

    @pytest.mark.asyncio
    async def test_poller_writes_deco_nodes(self, repos) -> None:  # type: ignore[no-untyped-def]
        """Poller creates deco_nodes rows for each mesh node."""
        from netsentry.integrations.deco.poller import DecoPoller

        mock_client = AsyncMock()
        mock_client.request.side_effect = [
            {"data": {"client_list": []}},
            {
                "data": {
                    "device_list": [
                        {
                            "mac": "11-22-33-44-55-66",
                            "device_model": "Deco M9",
                            "inet_status": "online",
                            "role": "main",
                        },
                        {
                            "mac": "AA-BB-CC-11-22-33",
                            "device_model": "Deco M9",
                            "inet_status": "online",
                            "role": "slave",
                        },
                    ]
                }
            },
        ]

        poller = DecoPoller(client=mock_client, conn=repos["conn"])
        await poller.poll()

        async with repos["conn"].execute("SELECT COUNT(*) FROM deco_nodes") as cur:
            row = await cur.fetchone()
        assert row[0] == 2

    @pytest.mark.asyncio
    async def test_poller_enriches_device_connection_type(self, repos) -> None:  # type: ignore[no-untyped-def]
        """Poller updates device.connection_type from Deco data."""
        from netsentry.integrations.deco.poller import DecoPoller

        await repos["devices"].upsert(mac="aa:bb:cc:dd:ee:ff", ip="192.168.68.10")

        mock_client = AsyncMock()
        mock_client.request.side_effect = [
            {
                "data": {
                    "client_list": [
                        {
                            "mac": "AA-BB-CC-DD-EE-FF",
                            "ip": "192.168.68.10",
                            "name": "Phone",
                            "online": True,
                            "type": "Phone",
                            "connection_type": "wireless",
                            "access_host": "11-22-33-44-55-66",
                            "band": "2.4GHz",
                            "up_speed": 100,
                            "down_speed": 500,
                        }
                    ]
                }
            },
            {"data": {"device_list": []}},
        ]

        poller = DecoPoller(client=mock_client, conn=repos["conn"])
        await poller.poll()

        device = await repos["devices"].get("aa:bb:cc:dd:ee:ff")
        assert device is not None
        assert device.connection_type == "wireless"

    @pytest.mark.asyncio
    async def test_poller_graceful_on_connection_error(self, repos) -> None:  # type: ignore[no-untyped-def]
        """Poller logs warning and continues on Deco connection error."""
        from netsentry.integrations.deco.exceptions import DecoConnectionError
        from netsentry.integrations.deco.poller import DecoPoller

        mock_client = AsyncMock()
        mock_client.request.side_effect = DecoConnectionError("Deco unreachable")

        poller = DecoPoller(client=mock_client, conn=repos["conn"])
        # Should not raise
        await poller.poll()

    @pytest.mark.asyncio
    async def test_new_device_from_deco_added_to_inventory(self, repos) -> None:  # type: ignore[no-untyped-def]
        """Device seen in Deco but not in inventory is added."""
        from netsentry.integrations.deco.poller import DecoPoller

        mock_client = AsyncMock()
        mock_client.request.side_effect = [
            {
                "data": {
                    "client_list": [
                        {
                            "mac": "FF-EE-DD-CC-BB-AA",
                            "ip": "192.168.68.50",
                            "name": "Smart TV",
                            "online": True,
                            "type": "Other",
                            "connection_type": "wireless",
                            "access_host": "11-22-33-44-55-66",
                            "band": "5GHz",
                            "up_speed": 200,
                            "down_speed": 8000,
                        }
                    ]
                }
            },
            {"data": {"device_list": []}},
        ]

        poller = DecoPoller(client=mock_client, conn=repos["conn"])
        await poller.poll()

        device = await repos["devices"].get("ff:ee:dd:cc:bb:aa")
        assert device is not None
        assert device.current_ip == "192.168.68.50"


# ── Roaming detection ─────────────────────────────────────────────────────────


class TestRoamingDetection:
    @pytest.mark.asyncio
    async def test_roaming_event_on_node_change(self, repos) -> None:  # type: ignore[no-untyped-def]
        """Roaming event emitted when device moves between Deco nodes."""
        from netsentry.integrations.deco.poller import DecoPoller

        await repos["devices"].upsert(mac="aa:bb:cc:dd:ee:ff", ip="192.168.68.10")

        def make_client_response(access_host: str) -> dict:  # type: ignore[type-arg]
            return {
                "data": {
                    "client_list": [
                        {
                            "mac": "AA-BB-CC-DD-EE-FF",
                            "ip": "192.168.68.10",
                            "name": "Laptop",
                            "online": True,
                            "type": "Laptop",
                            "connection_type": "wireless",
                            "access_host": access_host,
                            "band": "5GHz",
                            "up_speed": 500,
                            "down_speed": 2000,
                        }
                    ]
                }
            }

        mock_client = AsyncMock()
        mock_client.request.side_effect = [
            make_client_response("11-22-33-44-55-66"),  # poll 1: node A
            {"data": {"device_list": []}},
            make_client_response("AA-BB-CC-11-22-33"),  # poll 2: node B
            {"data": {"device_list": []}},
        ]

        poller = DecoPoller(client=mock_client, conn=repos["conn"])
        await poller.poll()  # First poll — no previous node
        await poller.poll()  # Second poll — node changed → roaming event

        events = await repos["events"].list_for_device("aa:bb:cc:dd:ee:ff")
        assert any(e.event_type == "deco.device_roamed" for e in events)

    @pytest.mark.asyncio
    async def test_no_roaming_event_on_same_node(self, repos) -> None:  # type: ignore[no-untyped-def]
        """No roaming event when device stays on same Deco node."""
        from netsentry.integrations.deco.poller import DecoPoller

        await repos["devices"].upsert(mac="aa:bb:cc:dd:ee:ff", ip="192.168.68.10")

        def same_node_response() -> dict:  # type: ignore[type-arg]
            return {
                "data": {
                    "client_list": [
                        {
                            "mac": "AA-BB-CC-DD-EE-FF",
                            "ip": "192.168.68.10",
                            "name": "Laptop",
                            "online": True,
                            "type": "Laptop",
                            "connection_type": "wireless",
                            "access_host": "11-22-33-44-55-66",
                            "band": "5GHz",
                            "up_speed": 500,
                            "down_speed": 2000,
                        }
                    ]
                }
            }

        mock_client = AsyncMock()
        mock_client.request.side_effect = [
            same_node_response(),
            {"data": {"device_list": []}},
            same_node_response(),
            {"data": {"device_list": []}},
        ]

        poller = DecoPoller(client=mock_client, conn=repos["conn"])
        await poller.poll()
        await poller.poll()

        events = await repos["events"].list_for_device("aa:bb:cc:dd:ee:ff")
        assert not any(e.event_type == "deco.device_roamed" for e in events)
