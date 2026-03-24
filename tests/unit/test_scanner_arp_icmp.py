"""
US0005 — TDD tests for the Scanner Engine (ARP, ICMP, NetBIOS).
All subprocess calls are mocked — no root or real network required in CI.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from netsentry.scanner.models import DiscoveredHost

# ── DiscoveredHost model ──────────────────────────────────────────────────────


class TestDiscoveredHost:
    def test_mac_normalised_on_creation(self) -> None:
        host = DiscoveredHost(mac="AA:BB:CC:DD:EE:FF", ip="192.168.1.1")
        assert host.mac == "aa:bb:cc:dd:ee:ff"

    def test_mac_none_allowed(self) -> None:
        host = DiscoveredHost(mac=None, ip="192.168.1.1")
        assert host.mac is None

    def test_hostname_defaults_none(self) -> None:
        host = DiscoveredHost(mac="aa:bb:cc:dd:ee:ff", ip="192.168.1.1")
        assert host.hostname is None


# ── Subnet detection ──────────────────────────────────────────────────────────


class TestSubnetDetection:
    def test_detect_subnets_excludes_loopback(self) -> None:
        from netsentry.scanner.subnets import detect_subnets

        with patch("netsentry.scanner.subnets.netifaces") as mock_ni:
            mock_ni.interfaces.return_value = ["lo", "eth0"]
            mock_ni.ifaddresses.side_effect = lambda iface: (
                {mock_ni.AF_INET: [{"addr": "127.0.0.1", "netmask": "255.0.0.0"}]}
                if iface == "lo"
                else {mock_ni.AF_INET: [{"addr": "192.168.1.100", "netmask": "255.255.255.0"}]}
            )
            mock_ni.AF_INET = 2
            subnets = detect_subnets()

        assert "127.0.0.0/8" not in subnets
        assert "192.168.1.0/24" in subnets

    def test_detect_subnets_excludes_docker_bridges(self) -> None:
        from netsentry.scanner.subnets import detect_subnets

        with patch("netsentry.scanner.subnets.netifaces") as mock_ni:
            mock_ni.interfaces.return_value = ["docker0", "eth0"]
            mock_ni.ifaddresses.side_effect = lambda iface: (
                {mock_ni.AF_INET: [{"addr": "172.17.0.1", "netmask": "255.255.0.0"}]}
                if iface == "docker0"
                else {mock_ni.AF_INET: [{"addr": "192.168.1.100", "netmask": "255.255.255.0"}]}
            )
            mock_ni.AF_INET = 2
            subnets = detect_subnets()

        assert not any("172.17" in s for s in subnets)
        assert "192.168.1.0/24" in subnets

    def test_detect_subnets_returns_empty_when_netifaces_none(self) -> None:
        """Returns empty list when netifaces is not available."""
        from netsentry.scanner import subnets as subnets_mod

        original = subnets_mod.netifaces
        subnets_mod.netifaces = None  # type: ignore[assignment]
        try:
            result = subnets_mod.detect_subnets()
            assert result == []
        finally:
            subnets_mod.netifaces = original

    def test_detect_subnets_skips_interface_with_no_ipv4(self) -> None:
        """Interfaces with no IPv4 address are skipped."""
        from netsentry.scanner.subnets import detect_subnets

        with patch("netsentry.scanner.subnets.netifaces") as mock_ni:
            mock_ni.interfaces.return_value = ["eth0", "eth1"]
            mock_ni.ifaddresses.side_effect = lambda iface: (
                {}  # no AF_INET for eth0
                if iface == "eth0"
                else {mock_ni.AF_INET: [{"addr": "192.168.1.100", "netmask": "255.255.255.0"}]}
            )
            mock_ni.AF_INET = 2
            subnets = detect_subnets()

        assert len(subnets) == 1
        assert "192.168.1.0/24" in subnets

    def test_get_subnets_uses_config_when_provided(self) -> None:
        """get_subnets() uses config value over auto-detection."""
        from netsentry.scanner.subnets import get_subnets

        result = get_subnets("10.0.0.0/8")
        assert result == ["10.0.0.0/8"]

    def test_get_subnets_falls_back_to_detection(self) -> None:
        """get_subnets() calls detect_subnets() when no config provided."""
        from netsentry.scanner import subnets as subnets_mod

        with patch.object(subnets_mod, "detect_subnets", return_value=["192.168.1.0/24"]):
            result = subnets_mod.get_subnets(None)
        assert result == ["192.168.1.0/24"]

    def test_detect_subnets_from_config_overrides_detection(self) -> None:
        from netsentry.scanner.subnets import subnets_from_config

        result = subnets_from_config("192.168.1.0/24,10.0.0.0/8")
        assert result == ["192.168.1.0/24", "10.0.0.0/8"]

    def test_invalid_cidr_raises(self) -> None:
        from netsentry.scanner.subnets import subnets_from_config

        with pytest.raises(ValueError, match="Invalid subnet"):
            subnets_from_config("not-a-cidr")


# ── ARP sweep ─────────────────────────────────────────────────────────────────


class TestArpSweep:
    @pytest.mark.asyncio
    async def test_arp_sweep_parses_output(self) -> None:
        """ARP sweep returns DiscoveredHost list from arp-scan output."""
        from netsentry.scanner.arp import arp_sweep

        fake_output = (
            "192.168.1.1\taa:bb:cc:dd:ee:01\tVendorA\n"
            "192.168.1.2\taa:bb:cc:dd:ee:02\tVendorB\n"
            "3 packets received by filter, 2 hosts found\n"
        )
        with patch("netsentry.scanner.arp._run_subprocess", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = (fake_output, "")
            hosts = await arp_sweep("192.168.1.0/24")

        assert len(hosts) == 2
        assert hosts[0].ip == "192.168.1.1"
        assert hosts[0].mac == "aa:bb:cc:dd:ee:01"
        assert hosts[1].ip == "192.168.1.2"

    @pytest.mark.asyncio
    async def test_arp_sweep_tool_failure_returns_empty(self) -> None:
        """If arp-scan fails, return empty list and log warning."""
        from netsentry.scanner.arp import arp_sweep

        with patch("netsentry.scanner.arp._run_subprocess", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = FileNotFoundError("arp-scan not found")
            hosts = await arp_sweep("192.168.1.0/24")

        assert hosts == []

    @pytest.mark.asyncio
    async def test_arp_sweep_respects_exclusion_list(self) -> None:
        """Hosts in exclusion list are filtered from results."""
        from netsentry.scanner.arp import arp_sweep

        fake_output = (
            "192.168.1.1\taa:bb:cc:dd:ee:01\tVendorA\n192.168.1.2\taa:bb:cc:dd:ee:02\tVendorB\n"
        )
        with patch("netsentry.scanner.arp._run_subprocess", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = (fake_output, "")
            hosts = await arp_sweep("192.168.1.0/24", exclusions={"192.168.1.1"})

        assert len(hosts) == 1
        assert hosts[0].ip == "192.168.1.2"

    @pytest.mark.asyncio
    async def test_arp_sweep_deduplicates_by_mac(self) -> None:
        """Duplicate MACs (same host, multiple IPs) are deduplicated."""
        from netsentry.scanner.arp import arp_sweep

        fake_output = (
            "192.168.1.1\taa:bb:cc:dd:ee:01\tVendorA\n"
            "192.168.1.2\taa:bb:cc:dd:ee:01\tVendorA\n"  # same MAC
        )
        with patch("netsentry.scanner.arp._run_subprocess", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = (fake_output, "")
            hosts = await arp_sweep("192.168.1.0/24")

        assert len(hosts) == 1

    @pytest.mark.asyncio
    async def test_arp_sweep_invalid_subnet_raises(self) -> None:
        """Invalid CIDR raises ValueError before any subprocess call."""
        from netsentry.scanner.arp import arp_sweep

        with pytest.raises(ValueError, match="Invalid subnet"):
            await arp_sweep("not-a-subnet")

    @pytest.mark.asyncio
    async def test_arp_sweep_empty_network_returns_empty(self) -> None:
        """Empty arp-scan output returns empty list."""
        from netsentry.scanner.arp import arp_sweep

        with patch("netsentry.scanner.arp._run_subprocess", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = ("0 hosts found\n", "")
            hosts = await arp_sweep("192.168.1.0/24")

        assert hosts == []


# ── ICMP sweep ────────────────────────────────────────────────────────────────


class TestIcmpSweep:
    @pytest.mark.asyncio
    async def test_icmp_sweep_parses_fping_output(self) -> None:
        """ICMP sweep parses fping alive output."""
        from netsentry.scanner.icmp import icmp_sweep

        # fping -a output: one IP per line for alive hosts
        fake_output = "192.168.1.1\n192.168.1.5\n192.168.1.10\n"
        with patch("netsentry.scanner.icmp._run_subprocess", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = (fake_output, "")
            hosts = await icmp_sweep("192.168.1.0/24")

        assert len(hosts) == 3
        assert hosts[0].ip == "192.168.1.1"
        assert hosts[0].mac is None  # ICMP doesn't give us MAC

    @pytest.mark.asyncio
    async def test_icmp_sweep_tool_failure_returns_empty(self) -> None:
        """fping not found returns empty list."""
        from netsentry.scanner.icmp import icmp_sweep

        with patch("netsentry.scanner.icmp._run_subprocess", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = FileNotFoundError("fping not found")
            hosts = await icmp_sweep("192.168.1.0/24")

        assert hosts == []

    @pytest.mark.asyncio
    async def test_icmp_sweep_respects_exclusions(self) -> None:
        """Exclusion list filters ICMP results."""
        from netsentry.scanner.icmp import icmp_sweep

        fake_output = "192.168.1.1\n192.168.1.2\n"
        with patch("netsentry.scanner.icmp._run_subprocess", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = (fake_output, "")
            hosts = await icmp_sweep("192.168.1.0/24", exclusions={"192.168.1.1"})

        assert len(hosts) == 1
        assert hosts[0].ip == "192.168.1.2"

    @pytest.mark.asyncio
    async def test_icmp_sweep_empty_returns_empty(self) -> None:
        """No alive hosts returns empty list."""
        from netsentry.scanner.icmp import icmp_sweep

        with patch("netsentry.scanner.icmp._run_subprocess", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = ("", "")
            hosts = await icmp_sweep("192.168.1.0/24")

        assert hosts == []


# ── NetBIOS scan ──────────────────────────────────────────────────────────────


class TestNetBiosScan:
    @pytest.mark.asyncio
    async def test_netbios_parses_nbtscan_output(self) -> None:
        """NetBIOS scan returns hostname from nbtscan output."""
        from netsentry.scanner.netbios import netbios_scan

        # nbtscan output format: IP  NetBIOS_Name  Server  User  MAC
        fake_output = (
            "192.168.1.50  DESKTOP-ABC  <server>  <unknown>  aa:bb:cc:dd:ee:ff\n"
            "192.168.1.51  LAPTOP-XYZ   <server>  <unknown>  11:22:33:44:55:66\n"
        )
        with patch("netsentry.scanner.netbios._run_subprocess", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = (fake_output, "")
            hosts = await netbios_scan(["192.168.1.50", "192.168.1.51"])

        assert len(hosts) == 2
        assert hosts[0].ip == "192.168.1.50"
        assert hosts[0].hostname == "DESKTOP-ABC"
        assert hosts[0].mac == "aa:bb:cc:dd:ee:ff"

    @pytest.mark.asyncio
    async def test_netbios_tool_failure_returns_empty(self) -> None:
        """nbtscan not found returns empty list."""
        from netsentry.scanner.netbios import netbios_scan

        with patch("netsentry.scanner.netbios._run_subprocess", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = FileNotFoundError("nbtscan not found")
            hosts = await netbios_scan(["192.168.1.50"])

        assert hosts == []

    @pytest.mark.asyncio
    async def test_netbios_empty_host_list_returns_empty(self) -> None:
        """Empty host list returns empty list without calling subprocess."""
        from netsentry.scanner.netbios import netbios_scan

        with patch("netsentry.scanner.netbios._run_subprocess", new_callable=AsyncMock) as mock_run:
            hosts = await netbios_scan([])

        mock_run.assert_not_called()
        assert hosts == []

    @pytest.mark.asyncio
    async def test_netbios_no_response_returns_empty(self) -> None:
        """Hosts that don't respond to NetBIOS return empty list."""
        from netsentry.scanner.netbios import netbios_scan

        with patch("netsentry.scanner.netbios._run_subprocess", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = ("", "")
            hosts = await netbios_scan(["192.168.1.50"])

        assert hosts == []


# ── Subprocess utility ────────────────────────────────────────────────────────


class TestSubprocessRunner:
    @pytest.mark.asyncio
    async def test_run_subprocess_returns_stdout(self) -> None:
        """_run_subprocess returns (stdout, stderr) tuple."""
        from netsentry.scanner.utils import run_subprocess

        stdout, stderr = await run_subprocess(["echo", "hello"])
        assert "hello" in stdout

    @pytest.mark.asyncio
    async def test_run_subprocess_raises_on_missing_binary(self) -> None:
        """Missing binary raises FileNotFoundError."""
        from netsentry.scanner.utils import run_subprocess

        with pytest.raises(FileNotFoundError):
            await run_subprocess(["this-binary-does-not-exist-xyz"])

    @pytest.mark.asyncio
    async def test_run_subprocess_timeout(self) -> None:
        """Slow command raises asyncio.TimeoutError."""
        import asyncio

        from netsentry.scanner.utils import run_subprocess

        with pytest.raises(asyncio.TimeoutError):
            await run_subprocess(["sleep", "10"], timeout=0.1)
