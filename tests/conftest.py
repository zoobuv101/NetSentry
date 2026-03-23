"""
Shared pytest fixtures for NetSentry test suite.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def safe_test_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set safe defaults for all tests. Individual tests can override via monkeypatch."""
    monkeypatch.setenv("DB_PATH", ":memory:")
    monkeypatch.setenv("LOG_LEVEL", "WARNING")
    monkeypatch.setenv("ENABLE_DECO_INTEGRATION", "false")
    monkeypatch.setenv("ENABLE_PFSENSE_INTEGRATION", "false")
    monkeypatch.setenv("ENABLE_ADGUARD_INTEGRATION", "false")
    monkeypatch.setenv("ENABLE_AI_IDENTIFICATION", "false")
    monkeypatch.setenv("ENABLE_SPEEDTEST", "false")
    monkeypatch.setenv("ENABLE_TELEGRAM", "false")


@pytest.fixture(autouse=True)
def reset_settings_cache() -> None:
    """Clear the lru_cache on Settings before and after each test."""
    from netsentry.core.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
