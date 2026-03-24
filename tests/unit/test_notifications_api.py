"""
US0015 — TDD tests for notification config API, Deco topology endpoint,
and notification test endpoints.
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


# ── Notification config API ───────────────────────────────────────────────────


class TestNotificationConfigApi:
    def test_get_config_returns_200(self, client: TestClient) -> None:
        """GET /api/v1/notifications/config returns 200."""
        resp = client.get("/api/v1/notifications/config")
        assert resp.status_code == 200

    def test_get_config_has_required_fields(self, client: TestClient) -> None:
        """Config response has ntfy and telegram sections."""
        resp = client.get("/api/v1/notifications/config")
        body = resp.json()
        assert "ntfy" in body
        assert "telegram" in body
        assert "quiet_hours" in body

    def test_ntfy_config_shows_enabled_status(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """ntfy section shows enabled=True when NTFY_URL is set."""
        monkeypatch.setenv("NTFY_URL", "http://ntfy.local/netsentry")
        from netsentry.core.config import get_settings

        get_settings.cache_clear()
        resp = client.get("/api/v1/notifications/config")
        assert resp.json()["ntfy"]["enabled"] is True

    def test_telegram_config_shows_disabled(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """telegram section shows enabled=False when token not set."""
        monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
        from netsentry.core.config import get_settings

        get_settings.cache_clear()
        resp = client.get("/api/v1/notifications/config")
        assert resp.json()["telegram"]["enabled"] is False

    def test_test_ntfy_returns_200(self, client: TestClient) -> None:
        """POST /api/v1/notifications/test/ntfy returns 200."""
        from unittest.mock import AsyncMock, patch

        with patch("netsentry.api.v1.notifications.NtfyChannel") as mock_cls:
            mock_ch = AsyncMock()
            mock_cls.from_settings.return_value = mock_ch
            mock_ch.send = AsyncMock(return_value=True)
            resp = client.post("/api/v1/notifications/test/ntfy")
        assert resp.status_code == 200

    def test_test_ntfy_not_configured_returns_400(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """POST /test/ntfy returns 400 when ntfy not configured."""
        monkeypatch.delenv("NTFY_URL", raising=False)
        from unittest.mock import patch

        from netsentry.notifications.ntfy import NtfyChannel

        with patch.object(NtfyChannel, "from_settings", return_value=None):
            resp = client.post("/api/v1/notifications/test/ntfy")
        assert resp.status_code == 400

    def test_test_telegram_returns_200(self, client: TestClient) -> None:
        """POST /api/v1/notifications/test/telegram returns 200."""
        from unittest.mock import AsyncMock, patch

        with patch("netsentry.api.v1.notifications.TelegramChannel") as mock_cls:
            mock_ch = AsyncMock()
            mock_cls.from_settings.return_value = mock_ch
            mock_ch.send = AsyncMock(return_value=True)
            resp = client.post("/api/v1/notifications/test/telegram")
        assert resp.status_code == 200


# ── Deco topology endpoint ────────────────────────────────────────────────────


class TestDecoTopologyApi:
    def test_topology_returns_200(self, client: TestClient) -> None:
        """GET /api/v1/deco/topology returns 200."""
        resp = client.get("/api/v1/deco/topology")
        assert resp.status_code == 200

    def test_topology_has_nodes_and_clients(self, client: TestClient) -> None:
        """Topology response has nodes and clients arrays."""
        resp = client.get("/api/v1/deco/topology")
        body = resp.json()
        assert "nodes" in body
        assert "clients" in body
        assert isinstance(body["nodes"], list)
        assert isinstance(body["clients"], list)

    def test_topology_with_seeded_data(self, tmp_path: pytest.TempPathFactory) -> None:
        """Topology returns Deco node data when records exist in DB."""
        import sqlite3

        db_path = str(tmp_path / "topo.db")  # type: ignore[operator]
        os.environ["DB_PATH"] = db_path
        from netsentry.core.config import get_settings

        get_settings.cache_clear()
        from netsentry.db.connection import run_migrations

        run_migrations(db_path)

        from netsentry.db.utils import to_iso8601, utc_now

        now = to_iso8601(utc_now())
        conn = sqlite3.connect(db_path)
        conn.execute(
            "INSERT INTO deco_nodes (mac_address, model, role, is_online, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            ("aa:bb:cc:dd:ee:01", "Deco M9 Plus", "main", 1, now),
        )
        conn.execute(
            "INSERT INTO mesh_assignments "
            "(mac_address, deco_node_mac, band, connection_type, connected_at) "
            "VALUES (?, ?, ?, ?, ?)",
            ("11:22:33:44:55:66", "aa:bb:cc:dd:ee:01", "5GHz", "wireless", now),
        )
        conn.commit()
        conn.close()

        from netsentry.api.main import create_app

        with TestClient(create_app()) as c:
            resp = c.get("/api/v1/deco/topology")

        body = resp.json()
        assert len(body["nodes"]) == 1
        assert body["nodes"][0]["mac_address"] == "aa:bb:cc:dd:ee:01"
        assert body["nodes"][0]["model"] == "Deco M9 Plus"
        assert len(body["clients"]) == 1
