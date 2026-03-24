"""
US0008 — TDD tests for FastAPI device endpoints.
Tests the REST API surface: GET /devices, GET /devices/{mac},
response schema, lifecycle filtering, MAC normalisation in URL.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client_with_devices(tmp_path: pytest.TempPathFactory):  # type: ignore[no-untyped-def]
    """TestClient with a migrated DB containing test devices."""
    import os

    db_path = str(tmp_path / "test.db")  # type: ignore[operator]

    os.environ["DB_PATH"] = db_path

    # Clear settings cache so the app picks up the new DB_PATH
    from netsentry.core.config import get_settings

    get_settings.cache_clear()

    from netsentry.db.connection import run_migrations

    run_migrations(db_path)

    # Seed some devices synchronously via sqlite3
    import sqlite3

    from netsentry.db.utils import to_iso8601, utc_now

    now = to_iso8601(utc_now())
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO devices (mac_address, current_ip, hostname, vendor, lifecycle, "
        "is_online, is_monitored, first_seen, last_seen, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "aa:bb:cc:dd:ee:01",
            "192.168.1.10",
            "laptop-one",
            "Apple",
            "active",
            1,
            0,
            now,
            now,
            now,
            now,
        ),
    )
    conn.execute(
        "INSERT INTO devices (mac_address, current_ip, hostname, vendor, lifecycle, "
        "is_online, is_monitored, first_seen, last_seen, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "aa:bb:cc:dd:ee:02",
            "192.168.1.11",
            "phone-two",
            "Samsung",
            "active",
            0,
            0,
            now,
            now,
            now,
            now,
        ),
    )
    conn.execute(
        "INSERT INTO devices (mac_address, current_ip, hostname, vendor, lifecycle, "
        "is_online, is_monitored, first_seen, last_seen, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "aa:bb:cc:dd:ee:03",
            "192.168.1.12",
            "old-device",
            "Generic",
            "historic",
            0,
            0,
            now,
            now,
            now,
            now,
        ),
    )
    conn.commit()
    conn.close()

    from netsentry.api.main import create_app

    with TestClient(create_app()) as client:
        yield client  # type: ignore[misc]


class TestGetDevices:
    def test_returns_200(self, client_with_devices: TestClient) -> None:
        """GET /api/v1/devices returns 200."""
        response = client_with_devices.get("/api/v1/devices")
        assert response.status_code == 200

    def test_returns_list(self, client_with_devices: TestClient) -> None:
        """Response body is a JSON array."""
        response = client_with_devices.get("/api/v1/devices")
        assert isinstance(response.json(), list)

    def test_returns_only_active_by_default(self, client_with_devices: TestClient) -> None:
        """Default response excludes historic/deleted devices."""
        response = client_with_devices.get("/api/v1/devices")
        macs = [d["mac_address"] for d in response.json()]
        assert "aa:bb:cc:dd:ee:01" in macs
        assert "aa:bb:cc:dd:ee:02" in macs
        assert "aa:bb:cc:dd:ee:03" not in macs  # historic

    def test_lifecycle_filter_historic(self, client_with_devices: TestClient) -> None:
        """?lifecycle=historic returns only historic devices."""
        response = client_with_devices.get("/api/v1/devices?lifecycle=historic")
        assert response.status_code == 200
        macs = [d["mac_address"] for d in response.json()]
        assert "aa:bb:cc:dd:ee:03" in macs
        assert "aa:bb:cc:dd:ee:01" not in macs

    def test_empty_inventory_returns_empty_list(self, tmp_path: pytest.TempPathFactory) -> None:
        """Empty inventory returns [] not 404."""
        import os

        db_path = str(tmp_path / "empty.db")  # type: ignore[operator]
        os.environ["DB_PATH"] = db_path
        from netsentry.core.config import get_settings

        get_settings.cache_clear()
        from netsentry.db.connection import run_migrations

        run_migrations(db_path)
        from netsentry.api.main import create_app

        with TestClient(create_app()) as client:
            response = client.get("/api/v1/devices")
        assert response.status_code == 200
        assert response.json() == []

    def test_device_response_has_required_fields(self, client_with_devices: TestClient) -> None:
        """Each device object has all required API fields."""
        response = client_with_devices.get("/api/v1/devices")
        device = response.json()[0]
        required = {
            "mac_address",
            "current_ip",
            "hostname",
            "vendor",
            "is_online",
            "lifecycle",
            "last_seen",
            "first_seen",
            "category",
            "owner",
            "friendly_name",
        }
        assert required.issubset(device.keys())


class TestGetDeviceDetail:
    def test_returns_200_for_known_mac(self, client_with_devices: TestClient) -> None:
        """GET /api/v1/devices/{mac} returns 200 for known device."""
        response = client_with_devices.get("/api/v1/devices/aa:bb:cc:dd:ee:01")
        assert response.status_code == 200

    def test_returns_404_for_unknown_mac(self, client_with_devices: TestClient) -> None:
        """Returns 404 with correct error code for unknown MAC."""
        response = client_with_devices.get("/api/v1/devices/ff:ff:ff:ff:ff:ff")
        assert response.status_code == 404
        body = response.json()
        # FastAPI wraps HTTPException.detail under "detail" key
        assert body["detail"]["code"] == "DEVICE_NOT_FOUND"

    def test_mac_normalised_in_url_colons(self, client_with_devices: TestClient) -> None:
        """Uppercase MAC in URL is normalised before lookup."""
        response = client_with_devices.get("/api/v1/devices/AA:BB:CC:DD:EE:01")
        assert response.status_code == 200
        assert response.json()["mac_address"] == "aa:bb:cc:dd:ee:01"

    def test_mac_normalised_in_url_dashes(self, client_with_devices: TestClient) -> None:
        """Dash-separated MAC in URL is normalised."""
        response = client_with_devices.get("/api/v1/devices/AA-BB-CC-DD-EE-01")
        assert response.status_code == 200

    def test_detail_includes_ip_history(self, client_with_devices: TestClient) -> None:
        """Detail response includes ip_history array."""
        response = client_with_devices.get("/api/v1/devices/aa:bb:cc:dd:ee:01")
        assert "ip_history" in response.json()
        assert isinstance(response.json()["ip_history"], list)

    def test_detail_includes_recent_events(self, client_with_devices: TestClient) -> None:
        """Detail response includes recent_events array."""
        response = client_with_devices.get("/api/v1/devices/aa:bb:cc:dd:ee:01")
        assert "recent_events" in response.json()
        assert isinstance(response.json()["recent_events"], list)


class TestScanTrigger:
    def test_scan_trigger_returns_202(self, client_with_devices: TestClient) -> None:
        """POST /api/v1/scan/trigger returns 202 Accepted."""
        response = client_with_devices.post("/api/v1/scan/trigger", json={"profile": "quick"})
        assert response.status_code == 202

    def test_scan_trigger_default_profile(self, client_with_devices: TestClient) -> None:
        """POST /api/v1/scan/trigger without body uses standard profile."""
        response = client_with_devices.post("/api/v1/scan/trigger", json={})
        assert response.status_code == 202

    def test_scan_status_returns_200(self, client_with_devices: TestClient) -> None:
        """GET /api/v1/scan/status returns 200."""
        response = client_with_devices.get("/api/v1/scan/status")
        assert response.status_code == 200
        body = response.json()
        assert "is_scanning" in body
        assert "last_scan" in body
