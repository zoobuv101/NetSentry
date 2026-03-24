"""
US0016-US0018 — TDD tests for pfSense integration.
Covers: SSH client, ARP table fetch, DHCP lease enrichment.
All SSH calls mocked — no real pfSense required.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

# ── pfSense SSH client ────────────────────────────────────────────────────────


class TestPfSenseClient:
    def test_client_instantiates(self) -> None:
        """PfSenseClient can be created with host/user/key."""
        from netsentry.integrations.pfsense.client import PfSenseClient

        client = PfSenseClient(host="192.168.1.1", username="admin", key_path="/root/.ssh/id_rsa")
        assert client is not None

    def test_from_settings_reads_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """from_settings() reads PFSENSE_ env vars."""
        monkeypatch.setenv("PFSENSE_HOST", "10.0.0.1")
        monkeypatch.setenv("PFSENSE_USERNAME", "root")
        monkeypatch.setenv("PFSENSE_KEY_PATH", "/root/.ssh/id_rsa")
        from netsentry.integrations.pfsense.client import PfSenseClient

        client = PfSenseClient.from_settings()
        assert client._host == "10.0.0.1"
        assert client._username == "root"

    def test_from_settings_missing_host_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """from_settings() raises ValueError when PFSENSE_HOST not set."""
        monkeypatch.delenv("PFSENSE_HOST", raising=False)
        from netsentry.integrations.pfsense.client import PfSenseClient

        with pytest.raises(ValueError, match="PFSENSE_HOST"):
            PfSenseClient.from_settings()

    @pytest.mark.asyncio
    async def test_run_command_returns_stdout(self) -> None:
        """run_command() returns stdout from SSH execution."""
        from netsentry.integrations.pfsense.client import PfSenseClient

        client = PfSenseClient(host="192.168.1.1", username="admin", key_path="/key")
        with patch.object(client, "_execute", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = ("output text\n", "")
            stdout, _ = await client.run_command("arp -an")

        assert stdout == "output text\n"
        mock_exec.assert_called_once_with("arp -an")

    @pytest.mark.asyncio
    async def test_connection_error_raises(self) -> None:
        """SSH connection failure raises PfSenseConnectionError."""
        from netsentry.integrations.pfsense.client import PfSenseClient
        from netsentry.integrations.pfsense.exceptions import PfSenseConnectionError

        client = PfSenseClient(host="192.168.1.1", username="admin", key_path="/key")
        with patch.object(client, "_execute", side_effect=Exception("SSH refused")):
            with pytest.raises(PfSenseConnectionError):
                await client.run_command("arp -an")


# ── ARP table ─────────────────────────────────────────────────────────────────


class TestPfSenseArpTable:
    @pytest.mark.asyncio
    async def test_fetch_arp_table_parses_output(self) -> None:
        """fetch_arp_table() parses pfSense arp -an output."""
        from netsentry.integrations.pfsense.arp import fetch_arp_table

        arp_output = (
            "? (192.168.1.1) at aa:bb:cc:dd:ee:01 on em0 expires in 1199 seconds [ethernet]\n"
            "? (192.168.1.10) at aa:bb:cc:dd:ee:02 on em0 expires in 800 seconds [ethernet]\n"
            "? (192.168.1.100) at (incomplete) on em0 [ethernet]\n"
        )
        mock_client = AsyncMock()
        mock_client.run_command = AsyncMock(return_value=(arp_output, ""))

        entries = await fetch_arp_table(mock_client)

        assert len(entries) == 2  # incomplete entry excluded
        assert entries[0].ip == "192.168.1.1"
        assert entries[0].mac == "aa:bb:cc:dd:ee:01"
        assert entries[0].interface == "em0"

    @pytest.mark.asyncio
    async def test_fetch_arp_table_normalises_mac(self) -> None:
        """MACs in ARP output are normalised to lowercase colon format."""
        from netsentry.integrations.pfsense.arp import fetch_arp_table

        arp_output = (
            "? (192.168.1.5) at AA:BB:CC:DD:EE:FF on igb0 expires in 100 seconds [ethernet]\n"
        )
        mock_client = AsyncMock()
        mock_client.run_command = AsyncMock(return_value=(arp_output, ""))

        entries = await fetch_arp_table(mock_client)
        assert entries[0].mac == "aa:bb:cc:dd:ee:ff"

    @pytest.mark.asyncio
    async def test_fetch_arp_table_empty_output(self) -> None:
        """Empty ARP output returns empty list."""
        from netsentry.integrations.pfsense.arp import fetch_arp_table

        mock_client = AsyncMock()
        mock_client.run_command = AsyncMock(return_value=("", ""))
        entries = await fetch_arp_table(mock_client)
        assert entries == []

    @pytest.mark.asyncio
    async def test_fetch_arp_table_connection_error_returns_empty(self) -> None:
        """Connection error returns empty list gracefully."""
        from netsentry.integrations.pfsense.arp import fetch_arp_table
        from netsentry.integrations.pfsense.exceptions import PfSenseConnectionError

        mock_client = AsyncMock()
        mock_client.run_command = AsyncMock(side_effect=PfSenseConnectionError("down"))

        entries = await fetch_arp_table(mock_client)
        assert entries == []


# ── DHCP leases ───────────────────────────────────────────────────────────────


class TestPfSenseDhcpLeases:
    @pytest.mark.asyncio
    async def test_fetch_dhcp_leases_parses_output(self) -> None:
        """fetch_dhcp_leases() parses pfSense dhcpd.leases output."""
        from netsentry.integrations.pfsense.dhcp import fetch_dhcp_leases

        # Simplified dhcpd.leases format
        leases_output = """
lease 192.168.1.10 {
  starts 3 2026/01/01 10:00:00;
  ends 3 2026/01/01 22:00:00;
  hardware ethernet aa:bb:cc:dd:ee:02;
  client-hostname "my-laptop";
}
lease 192.168.1.20 {
  starts 3 2026/01/01 11:00:00;
  ends 3 2026/01/01 23:00:00;
  hardware ethernet 11:22:33:44:55:66;
}
"""
        mock_client = AsyncMock()
        mock_client.run_command = AsyncMock(return_value=(leases_output, ""))

        leases = await fetch_dhcp_leases(mock_client)

        assert len(leases) == 2
        laptop = next(item for item in leases if item.ip == "192.168.1.10")
        assert laptop.mac == "aa:bb:cc:dd:ee:02"
        assert laptop.hostname == "my-laptop"

    @pytest.mark.asyncio
    async def test_fetch_dhcp_leases_deduplicates_by_mac(self) -> None:
        """Duplicate leases (same MAC) returns only most recent."""
        from netsentry.integrations.pfsense.dhcp import fetch_dhcp_leases

        leases_output = """
lease 192.168.1.10 {
  starts 3 2026/01/01 10:00:00;
  ends 3 2026/01/01 22:00:00;
  hardware ethernet aa:bb:cc:dd:ee:01;
  client-hostname "device";
}
lease 192.168.1.11 {
  starts 3 2026/01/02 10:00:00;
  ends 3 2026/01/02 22:00:00;
  hardware ethernet aa:bb:cc:dd:ee:01;
  client-hostname "device";
}
"""
        mock_client = AsyncMock()
        mock_client.run_command = AsyncMock(return_value=(leases_output, ""))

        leases = await fetch_dhcp_leases(mock_client)
        assert len(leases) == 1
        assert leases[0].ip == "192.168.1.11"  # most recent IP

    @pytest.mark.asyncio
    async def test_fetch_dhcp_leases_graceful_on_error(self) -> None:
        """Connection error returns empty list."""
        from netsentry.integrations.pfsense.dhcp import fetch_dhcp_leases
        from netsentry.integrations.pfsense.exceptions import PfSenseConnectionError

        mock_client = AsyncMock()
        mock_client.run_command = AsyncMock(side_effect=PfSenseConnectionError("down"))

        leases = await fetch_dhcp_leases(mock_client)
        assert leases == []


# ── pfSense poller ────────────────────────────────────────────────────────────


class TestPfSensePoller:
    @pytest.fixture
    async def db_conn(self, tmp_path: pytest.TempPathFactory):  # type: ignore[no-untyped-def]
        from netsentry.db.connection import get_connection, run_migrations

        db_path = str(tmp_path / "test.db")  # type: ignore[operator]
        run_migrations(db_path)
        conn = await get_connection(db_path)
        yield conn
        await conn.close()

    @pytest.mark.asyncio
    async def test_poller_enriches_device_hostname(self, db_conn) -> None:  # type: ignore[no-untyped-def]
        """Poller updates hostname from DHCP lease data."""
        from netsentry.db.repositories.devices import DeviceRepository
        from netsentry.integrations.pfsense.models import DhcpLease
        from netsentry.integrations.pfsense.poller import PfSensePoller

        repo = DeviceRepository(db_conn)
        await repo.upsert(mac="aa:bb:cc:dd:ee:ff", ip="192.168.1.10")

        mock_client = AsyncMock()
        poller = PfSensePoller(client=mock_client, conn=db_conn)

        with (
            patch.object(poller, "_fetch_arp", new_callable=AsyncMock, return_value=[]),
            patch.object(poller, "_fetch_dhcp", new_callable=AsyncMock) as mock_dhcp,
        ):
            mock_dhcp.return_value = [
                DhcpLease(mac="aa:bb:cc:dd:ee:ff", ip="192.168.1.10", hostname="my-pc")
            ]
            await poller.poll()

        device = await repo.get("aa:bb:cc:dd:ee:ff")
        assert device is not None
        assert device.hostname == "my-pc"

    @pytest.mark.asyncio
    async def test_poller_creates_new_device_from_arp(self, db_conn) -> None:  # type: ignore[no-untyped-def]
        """Device in ARP table but not inventory is added."""
        from netsentry.db.repositories.devices import DeviceRepository
        from netsentry.integrations.pfsense.models import ArpEntry
        from netsentry.integrations.pfsense.poller import PfSensePoller

        repo = DeviceRepository(db_conn)
        mock_client = AsyncMock()
        poller = PfSensePoller(client=mock_client, conn=db_conn)

        with (
            patch.object(poller, "_fetch_arp", new_callable=AsyncMock) as mock_arp,
            patch.object(poller, "_fetch_dhcp", new_callable=AsyncMock, return_value=[]),
        ):
            mock_arp.return_value = [
                ArpEntry(ip="192.168.1.50", mac="ff:ee:dd:cc:bb:aa", interface="em0")
            ]
            await poller.poll()

        device = await repo.get("ff:ee:dd:cc:bb:aa")
        assert device is not None
        assert device.current_ip == "192.168.1.50"
