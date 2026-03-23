"""
US0002 — TDD tests for the project scaffold and Settings configuration.
"""

from __future__ import annotations

import importlib
import re

import pytest


class TestSettings:
    """AC: Pydantic Settings loads correctly from environment."""

    def test_settings_loads_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Settings instantiates with all required defaults when env is clean."""
        # Clear all conftest overrides so we see the true class defaults
        for key in (
            "LOG_LEVEL",
            "DB_PATH",
            "ENABLE_DECO_INTEGRATION",
            "ENABLE_PFSENSE_INTEGRATION",
            "ENABLE_ADGUARD_INTEGRATION",
        ):
            monkeypatch.delenv(key, raising=False)

        from netsentry.core.config import Settings

        s = Settings()
        assert s.app_version == "0.1.0"
        assert s.log_level == "INFO"
        assert s.db_path == "/data/netsentry.db"
        assert s.scan_interval_arp == 300
        assert s.api_port == 8080
        assert s.enable_deco_integration is True

    def test_settings_overrides_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Env var overrides the default value."""
        monkeypatch.setenv("SCAN_INTERVAL_ARP", "120")
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")

        from netsentry.core.config import Settings

        s = Settings()
        assert s.scan_interval_arp == 120
        assert s.log_level == "DEBUG"

    def test_settings_invalid_log_level_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Invalid log level raises ValidationError."""
        from pydantic import ValidationError

        monkeypatch.setenv("LOG_LEVEL", "VERBOSE")

        from netsentry.core.config import Settings

        with pytest.raises(ValidationError, match="log_level"):
            Settings()

    def test_settings_invalid_speedtest_backend_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Invalid speedtest backend raises ValidationError."""
        from pydantic import ValidationError

        monkeypatch.setenv("SPEEDTEST_BACKEND", "banana")

        from netsentry.core.config import Settings

        with pytest.raises(ValidationError, match="speedtest_backend"):
            Settings()

    def test_settings_valid_speedtest_backends(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """All valid speedtest backends accepted."""
        from netsentry.core.config import Settings

        for backend in ("librespeed", "ookla", "fast"):
            monkeypatch.setenv("SPEEDTEST_BACKEND", backend)
            s = Settings()
            assert s.speedtest_backend == backend

    def test_settings_optional_fields_none_by_default(self) -> None:
        """Optional integration credentials are None when not set."""
        from netsentry.core.config import Settings

        s = Settings()
        assert s.deco_host is None
        assert s.pfsense_api_url is None
        assert s.adguard_url is None
        assert s.telegram_bot_token is None
        assert s.anthropic_api_key is None

    def test_settings_ai_disabled_by_default(self) -> None:
        """AI identification is off by default."""
        from netsentry.core.config import Settings

        s = Settings()
        assert s.enable_ai_identification is False

    def test_settings_telegram_disabled_by_default(self) -> None:
        """Telegram notifications are off by default."""
        from netsentry.core.config import Settings

        s = Settings()
        assert s.enable_telegram is False

    def test_get_settings_is_cached(self) -> None:
        """get_settings() returns same instance on repeated calls (lru_cache)."""
        from netsentry.core.config import get_settings

        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2

    def test_warn_missing_optional_logs_warning(self) -> None:
        """warn_missing_optional() logs a warning for each unconfigured integration."""
        import logging
        from unittest.mock import patch

        from netsentry.core.config import Settings

        s = Settings(
            enable_deco_integration=True,
            enable_pfsense_integration=True,
            enable_adguard_integration=False,
        )
        with patch.object(logging.getLogger("netsentry.core.config"), "warning") as mock_warn:
            s.warn_missing_optional()

        warned_messages = " ".join(str(call) for call in mock_warn.call_args_list)
        assert "DECO_HOST" in warned_messages
        assert "PFSENSE_API_URL" in warned_messages
        assert "ADGUARD_URL" not in warned_messages


class TestPackageStructure:
    """AC: All netsentry subpackages are importable."""

    @pytest.mark.parametrize(
        "module",
        [
            "netsentry",
            "netsentry.api",
            "netsentry.api.main",
            "netsentry.api.v1.router",
            "netsentry.api.v1.system",
            "netsentry.core",
            "netsentry.core.config",
            "netsentry.db",
            "netsentry.db.repositories",
            "netsentry.scanner",
            "netsentry.integrations",
            "netsentry.integrations.deco",
            "netsentry.integrations.pfsense",
            "netsentry.integrations.adguard",
            "netsentry.notifications",
            "netsentry.events",
            "netsentry.identification",
            "netsentry.monitor",
            "netsentry.speedtest",
        ],
    )
    def test_module_importable(self, module: str) -> None:
        """Every declared package is importable without error."""
        mod = importlib.import_module(module)
        assert mod is not None

    def test_version_is_semver(self) -> None:
        """Package __version__ is a valid semver string."""
        import netsentry

        assert re.match(r"^\d+\.\d+\.\d+$", netsentry.__version__)

    def test_create_app_returns_fastapi(self) -> None:
        """create_app() factory returns a FastAPI instance."""
        from fastapi import FastAPI

        from netsentry.api.main import create_app

        app = create_app()
        assert isinstance(app, FastAPI)

    def test_app_has_v1_prefix(self) -> None:
        """API router is mounted at /api/v1."""
        from fastapi.testclient import TestClient

        from netsentry.api.main import create_app

        client = TestClient(create_app())
        # Health is at /api/v1/system/health — confirms prefix is correct
        assert client.get("/api/v1/system/health").status_code == 200
        # Without prefix returns 404
        assert client.get("/system/health").status_code == 404
