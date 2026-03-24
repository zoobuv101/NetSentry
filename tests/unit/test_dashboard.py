"""
US0038-US0045 — TDD tests for dashboard summary API and system overview.
The heavy lifting is in the React frontend — backend tests cover the
summary endpoint that feeds all the dashboard widgets.
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path: pytest.TempPathFactory) -> TestClient:
    db_path = str(tmp_path / "test.db")  # type: ignore[operator]
    os.environ["DB_PATH"] = db_path
    from netsentry.core.config import get_settings

    get_settings.cache_clear()
    from netsentry.db.connection import run_migrations

    run_migrations(db_path)
    from netsentry.api.main import create_app

    with TestClient(create_app()) as c:
        yield c  # type: ignore[misc]


# ── Dashboard summary endpoint ────────────────────────────────────────────────


class TestDashboardSummary:
    def test_summary_returns_200(self, client: TestClient) -> None:
        """GET /api/v1/dashboard/summary returns 200."""
        resp = client.get("/api/v1/dashboard/summary")
        assert resp.status_code == 200

    def test_summary_has_device_counts(self, client: TestClient) -> None:
        """Summary includes total, online, offline device counts."""
        resp = client.get("/api/v1/dashboard/summary")
        body = resp.json()
        assert "devices" in body
        assert "total" in body["devices"]
        assert "online" in body["devices"]
        assert "offline" in body["devices"]

    def test_summary_has_scan_info(self, client: TestClient) -> None:
        """Summary includes last scan metadata."""
        resp = client.get("/api/v1/dashboard/summary")
        body = resp.json()
        assert "last_scan" in body

    def test_summary_has_speed_test_info(self, client: TestClient) -> None:
        """Summary includes latest speed test result (or null)."""
        resp = client.get("/api/v1/dashboard/summary")
        body = resp.json()
        assert "latest_speed_test" in body

    def test_summary_has_notifications_status(self, client: TestClient) -> None:
        """Summary includes notification channel status."""
        resp = client.get("/api/v1/dashboard/summary")
        body = resp.json()
        assert "notifications" in body

    def test_summary_device_counts_accurate(self, tmp_path: pytest.TempPathFactory) -> None:
        """Device counts match seeded data."""
        import sqlite3

        db_path = str(tmp_path / "counted.db")  # type: ignore[operator]
        os.environ["DB_PATH"] = db_path
        from netsentry.core.config import get_settings

        get_settings.cache_clear()
        from netsentry.db.connection import run_migrations

        run_migrations(db_path)

        from netsentry.db.utils import to_iso8601, utc_now

        now = to_iso8601(utc_now())
        conn = sqlite3.connect(db_path)
        for i, online in enumerate([1, 1, 1, 0, 0]):
            conn.execute(
                "INSERT INTO devices (mac_address, current_ip, lifecycle, is_online, "
                "is_monitored, first_seen, last_seen, created_at, updated_at) "
                "VALUES (?, ?, 'active', ?, 0, ?, ?, ?, ?)",
                (f"aa:bb:cc:dd:ee:{i:02x}", f"192.168.1.{i + 1}", online, now, now, now, now),
            )
        conn.commit()
        conn.close()

        from netsentry.api.main import create_app

        with TestClient(create_app()) as c:
            resp = c.get("/api/v1/dashboard/summary")

        body = resp.json()
        assert body["devices"]["total"] == 5
        assert body["devices"]["online"] == 3
        assert body["devices"]["offline"] == 2

    def test_summary_has_adguard_stats(self, client: TestClient) -> None:
        """Summary includes AdGuard DNS stats (or null)."""
        resp = client.get("/api/v1/dashboard/summary")
        body = resp.json()
        assert "adguard" in body

    def test_summary_has_recent_events(self, client: TestClient) -> None:
        """Summary includes list of recent events."""
        resp = client.get("/api/v1/dashboard/summary")
        body = resp.json()
        assert "recent_events" in body
        assert isinstance(body["recent_events"], list)


# ── System info endpoint ──────────────────────────────────────────────────────


class TestSystemInfo:
    def test_health_endpoint_still_works(self, client: TestClient) -> None:
        """Original health endpoint unchanged."""
        resp = client.get("/api/v1/system/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_openapi_schema_valid(self, client: TestClient) -> None:
        """OpenAPI schema is valid JSON with all routers registered."""
        resp = client.get("/openapi.json")
        assert resp.status_code == 200
        schema = resp.json()
        paths = schema["paths"]
        # All major route groups present
        assert any("/devices" in p for p in paths)
        assert any("/scan" in p for p in paths)
        assert any("/notifications" in p for p in paths)
        assert any("/deco" in p for p in paths)
        assert any("/speedtest" in p for p in paths)
        assert any("/dashboard" in p for p in paths)
