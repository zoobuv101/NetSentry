"""
US0006 — TDD tests for TCP port scanning, mDNS/SSDP listeners, OS fingerprinting.
All subprocess/socket calls are mocked — no root or real network required.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

# ── TCP port scan ─────────────────────────────────────────────────────────────


class TestTcpPortScan:
    @pytest.mark.asyncio
    async def test_tcp_probe_parses_open_ports(self) -> None:
        """TCP SYN probe returns open ports from nmap XML output."""
        from netsentry.scanner.tcp import tcp_syn_probe

        # nmap -oX output with two open ports
        nmap_xml = """<?xml version="1.0"?>
<nmaprun>
  <host>
    <address addr="192.168.1.10" addrtype="ipv4"/>
    <ports>
      <port protocol="tcp" portid="22">
        <state state="open"/>
      </port>
      <port protocol="tcp" portid="80">
        <state state="open"/>
      </port>
      <port protocol="tcp" portid="443">
        <state state="closed"/>
      </port>
    </ports>
  </host>
</nmaprun>"""
        with patch("netsentry.scanner.tcp._run_subprocess", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = (nmap_xml, "")
            result = await tcp_syn_probe(["192.168.1.10"], ports=[22, 80, 443])

        assert len(result) == 1
        assert result[0].ip == "192.168.1.10"
        assert 22 in result[0].open_ports
        assert 80 in result[0].open_ports
        assert 443 not in result[0].open_ports

    @pytest.mark.asyncio
    async def test_tcp_probe_tool_failure_returns_empty(self) -> None:
        """nmap not found returns empty list."""
        from netsentry.scanner.tcp import tcp_syn_probe

        with patch("netsentry.scanner.tcp._run_subprocess", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = FileNotFoundError("nmap not found")
            result = await tcp_syn_probe(["192.168.1.10"])

        assert result == []

    @pytest.mark.asyncio
    async def test_tcp_probe_empty_host_list_returns_empty(self) -> None:
        """Empty host list returns empty without calling subprocess."""
        from netsentry.scanner.tcp import tcp_syn_probe

        with patch("netsentry.scanner.tcp._run_subprocess", new_callable=AsyncMock) as mock_run:
            result = await tcp_syn_probe([])

        mock_run.assert_not_called()
        assert result == []

    @pytest.mark.asyncio
    async def test_tcp_probe_host_with_no_open_ports(self) -> None:
        """Host with no open ports returns result with empty port list."""
        from netsentry.scanner.tcp import tcp_syn_probe

        nmap_xml = """<?xml version="1.0"?>
<nmaprun>
  <host>
    <address addr="192.168.1.10" addrtype="ipv4"/>
    <ports>
      <port protocol="tcp" portid="22"><state state="closed"/></port>
    </ports>
  </host>
</nmaprun>"""
        with patch("netsentry.scanner.tcp._run_subprocess", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = (nmap_xml, "")
            result = await tcp_syn_probe(["192.168.1.10"])

        assert len(result) == 1
        assert result[0].open_ports == []


# ── Service detection ─────────────────────────────────────────────────────────


class TestServiceDetection:
    @pytest.mark.asyncio
    async def test_service_detect_returns_version_strings(self) -> None:
        """Service detection extracts service name and version."""
        from netsentry.scanner.tcp import service_detect

        nmap_xml = """<?xml version="1.0"?>
<nmaprun>
  <host>
    <address addr="192.168.1.10" addrtype="ipv4"/>
    <ports>
      <port protocol="tcp" portid="22">
        <state state="open"/>
        <service name="ssh" product="OpenSSH" version="8.9p1"/>
      </port>
      <port protocol="tcp" portid="80">
        <state state="open"/>
        <service name="http" product="nginx" version="1.24.0"/>
      </port>
    </ports>
  </host>
</nmaprun>"""
        with patch("netsentry.scanner.tcp._run_subprocess", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = (nmap_xml, "")
            services = await service_detect("192.168.1.10", ports=[22, 80])

        assert len(services) == 2
        ssh = next(s for s in services if s.port == 22)
        assert ssh.service == "ssh"
        assert "OpenSSH" in (ssh.version or "")

    @pytest.mark.asyncio
    async def test_service_detect_tool_failure_returns_empty(self) -> None:
        """nmap not found returns empty list."""
        from netsentry.scanner.tcp import service_detect

        with patch("netsentry.scanner.tcp._run_subprocess", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = FileNotFoundError("nmap not found")
            services = await service_detect("192.168.1.10", ports=[22])

        assert services == []


# ── OS fingerprinting ─────────────────────────────────────────────────────────


class TestOsFingerprinting:
    @pytest.mark.asyncio
    async def test_os_fingerprint_returns_os_family(self) -> None:
        """OS fingerprinting extracts OS family and confidence."""
        from netsentry.scanner.os_detect import os_fingerprint

        nmap_xml = """<?xml version="1.0"?>
<nmaprun>
  <host>
    <address addr="192.168.1.10" addrtype="ipv4"/>
    <os>
      <osmatch name="Linux 5.4" accuracy="95">
        <osclass type="general purpose" vendor="Linux" osfamily="Linux"
                 osgen="5.X" accuracy="95"/>
      </osmatch>
    </os>
  </host>
</nmaprun>"""
        with patch(  # noqa: E501
            "netsentry.scanner.os_detect._run_subprocess", new_callable=AsyncMock
        ) as mock_run:
            mock_run.return_value = (nmap_xml, "")
            result = await os_fingerprint("192.168.1.10")

        assert result is not None
        assert result.os_family == "Linux"
        assert result.confidence >= 0.9

    @pytest.mark.asyncio
    async def test_os_fingerprint_returns_none_when_inconclusive(self) -> None:
        """Returns None when nmap can't determine OS."""
        from netsentry.scanner.os_detect import os_fingerprint

        nmap_xml = """<?xml version="1.0"?>
<nmaprun>
  <host>
    <address addr="192.168.1.10" addrtype="ipv4"/>
  </host>
</nmaprun>"""
        with patch(  # noqa: E501
            "netsentry.scanner.os_detect._run_subprocess", new_callable=AsyncMock
        ) as mock_run:
            mock_run.return_value = (nmap_xml, "")
            result = await os_fingerprint("192.168.1.10")

        assert result is None

    @pytest.mark.asyncio
    async def test_os_fingerprint_tool_failure_returns_none(self) -> None:
        """nmap not found returns None gracefully."""
        from netsentry.scanner.os_detect import os_fingerprint

        with patch(  # noqa: E501
            "netsentry.scanner.os_detect._run_subprocess", new_callable=AsyncMock
        ) as mock_run:
            mock_run.side_effect = FileNotFoundError("nmap not found")
            result = await os_fingerprint("192.168.1.10")

        assert result is None


# ── mDNS listener ─────────────────────────────────────────────────────────────


class TestMdnsListener:
    def test_mdns_parse_service_type(self) -> None:
        """mDNS parser extracts service type and IP from a mock packet."""
        from netsentry.scanner.mdns import parse_mdns_record

        record = parse_mdns_record(
            name="_airplay._tcp.local",
            ip="192.168.1.20",
            data="Living Room TV",
        )
        assert record is not None
        assert record.ip == "192.168.1.20"
        assert record.service_type == "_airplay._tcp"
        assert record.name == "Living Room TV"

    def test_mdns_parse_ignores_non_service_records(self) -> None:
        """Records without service type pattern return None."""
        from netsentry.scanner.mdns import parse_mdns_record

        record = parse_mdns_record(
            name="randomhostname.local",
            ip="192.168.1.20",
            data="",
        )
        assert record is None

    def test_mdns_parse_ipp_tcp(self) -> None:
        """_ipp._tcp (printer) service type parsed correctly."""
        from netsentry.scanner.mdns import parse_mdns_record

        record = parse_mdns_record(
            name="_ipp._tcp.local",
            ip="192.168.1.30",
            data="HP LaserJet",
        )
        assert record is not None
        assert record.service_type == "_ipp._tcp"


# ── SSDP listener ─────────────────────────────────────────────────────────────


class TestSsdpListener:
    def test_ssdp_parse_notify_packet(self) -> None:
        """SSDP NOTIFY packet is parsed into SsdpRecord."""
        from netsentry.scanner.ssdp import parse_ssdp_packet

        raw = (
            "NOTIFY * HTTP/1.1\r\n"
            "HOST: 239.255.255.250:1900\r\n"
            "NT: urn:schemas-upnp-org:device:MediaRenderer:1\r\n"
            "USN: uuid:abc123::urn:schemas-upnp-org:device:MediaRenderer:1\r\n"
            "NTS: ssdp:alive\r\n"
            "LOCATION: http://192.168.1.30:1234/device.xml\r\n"
            "\r\n"
        )
        record = parse_ssdp_packet(raw, source_ip="192.168.1.30")

        assert record is not None
        assert record.ip == "192.168.1.30"
        assert record.device_type == "MediaRenderer"
        assert record.usn is not None

    def test_ssdp_parse_non_device_nt_returns_none(self) -> None:
        """SSDP packets without device NT are ignored."""
        from netsentry.scanner.ssdp import parse_ssdp_packet

        raw = (
            "NOTIFY * HTTP/1.1\r\n"
            "HOST: 239.255.255.250:1900\r\n"
            "NT: upnp:rootdevice\r\n"
            "NTS: ssdp:alive\r\n"
            "\r\n"
        )
        record = parse_ssdp_packet(raw, source_ip="192.168.1.30")
        assert record is None

    def test_ssdp_parse_missing_nt_returns_none(self) -> None:
        """Malformed SSDP packet without NT header returns None."""
        from netsentry.scanner.ssdp import parse_ssdp_packet

        record = parse_ssdp_packet("GARBAGE\r\n\r\n", source_ip="192.168.1.30")
        assert record is None
