"""
Shared pytest fixtures for NetSentry test suite.
"""

from __future__ import annotations

import os

import pytest

# Ensure tests always use an in-memory DB and safe defaults
os.environ.setdefault("DB_PATH", ":memory:")
os.environ.setdefault("LOG_LEVEL", "WARNING")
os.environ.setdefault("ENABLE_DECO_INTEGRATION", "false")
os.environ.setdefault("ENABLE_PFSENSE_INTEGRATION", "false")
os.environ.setdefault("ENABLE_ADGUARD_INTEGRATION", "false")
os.environ.setdefault("ENABLE_AI_IDENTIFICATION", "false")
os.environ.setdefault("ENABLE_SPEEDTEST", "false")
os.environ.setdefault("ENABLE_TELEGRAM", "false")


@pytest.fixture(autouse=True)
def reset_settings_cache() -> None:
    """Clear the lru_cache on Settings between tests."""
    from netsentry.core.config import get_settings

    get_settings.cache_clear()
