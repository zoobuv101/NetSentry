"""AdGuard Home HTTP API client."""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from netsentry.integrations.adguard.exceptions import (
    AdGuardAuthError,
    AdGuardConnectionError,
)

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 10.0


class AdGuardClient:
    """HTTP client for the AdGuard Home REST API."""

    def __init__(
        self,
        url: str,
        username: str = "",
        password: str = "",
        timeout: float = _DEFAULT_TIMEOUT,
    ) -> None:
        self._url = url.rstrip("/")
        self._auth = (username, password) if username else None
        self._timeout = timeout

    @classmethod
    def from_settings(cls) -> AdGuardClient:
        url = os.environ.get("ADGUARD_URL")
        if not url:
            raise ValueError("ADGUARD_URL environment variable not set")
        username = os.environ.get("ADGUARD_USERNAME", "")
        password = os.environ.get("ADGUARD_PASSWORD", "")
        return cls(url=url, username=username, password=password)

    async def _get(self, path: str) -> Any:
        """Internal: GET request returning parsed JSON."""
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as http:
                resp = await http.get(
                    f"{self._url}{path}",
                    auth=self._auth,
                )
                if resp.status_code == 401:
                    raise AdGuardAuthError("AdGuard authentication failed")
                resp.raise_for_status()
                return resp.json()
        except (AdGuardAuthError, AdGuardConnectionError):
            raise
        except httpx.ConnectError as e:
            raise AdGuardConnectionError(f"Cannot connect to AdGuard at {self._url}: {e}") from e
        except httpx.TimeoutException as e:
            raise AdGuardConnectionError(f"AdGuard request timed out: {e}") from e
        except Exception as e:
            raise AdGuardConnectionError(f"AdGuard request failed: {e}") from e

    async def get_stats(self) -> dict[str, Any]:
        """GET /control/stats — query/block counts."""
        result: dict[str, Any] = await self._get("/control/stats")
        return result

    async def get_clients(self) -> list[dict[str, Any]]:
        """GET /control/clients — named client list."""
        data = await self._get("/control/clients")
        clients: list[dict[str, Any]] = data.get("clients", [])
        return clients
