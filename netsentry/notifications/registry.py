"""
NetSentry notification registry — module-level dispatcher singleton.

Set once at startup via set_dispatcher(), then called from anywhere via notify().
Avoids threading the dispatcher through every constructor.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class _DispatcherProtocol(Protocol):
    async def dispatch(
        self,
        event_type: str,
        severity: str,
        mac: str | None = None,
        hostname: str | None = None,
        ip: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> bool: ...


_dispatcher: _DispatcherProtocol | None = None


def set_dispatcher(dispatcher: _DispatcherProtocol) -> None:
    """Register the global notification dispatcher. Called once at startup."""
    global _dispatcher
    _dispatcher = dispatcher
    logger.info("Notification dispatcher registered")


async def notify(
    event_type: str,
    severity: str,
    mac: str | None = None,
    hostname: str | None = None,
    ip: str | None = None,
    details: dict[str, Any] | None = None,
) -> bool:
    """
    Fire a notification for an event. Safe to call even if no dispatcher
    is registered (returns False silently).
    """
    if _dispatcher is None:
        return False
    try:
        return await _dispatcher.dispatch(
            event_type=event_type,
            severity=severity,
            mac=mac,
            hostname=hostname,
            ip=ip,
            details=details or {},
        )
    except Exception as e:
        logger.warning("Notification dispatch error: %s", e)
        return False
