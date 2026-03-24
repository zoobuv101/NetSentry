"""
NetSentry Notification Dispatcher.

Bridges event creation → EventEngine (quiet hours, rate limiting) →
notification channels (Telegram, ntfy).

Usage: instantiate once at startup, attach to app.state, then call
dispatcher.dispatch(event_type, severity, mac, details, hostname) from
any code that creates an event.
"""

from __future__ import annotations

import logging
from typing import Any

from netsentry.events.engine import EventEngine
from netsentry.notifications.telegram import TelegramChannel

logger = logging.getLogger(__name__)

# Human-readable titles for event types
_EVENT_TITLES: dict[str, str] = {
    "device.new": "New device on network",
    "device.offline": "Device went offline",
    "device.online": "Device came back online",
    "availability.down": "Device unreachable",
    "availability.up": "Device reachable again",
    "system.scan_failed": "Scan failed",
    "speed.slow": "Internet speed degraded",
    "deco.device_roamed": "Device roamed",
}

# Severities that trigger notifications (skip low-noise info events)
_NOTIFY_SEVERITIES = {"urgent", "high"}


def _format_body(
    event_type: str,
    mac: str | None,
    hostname: str | None,
    ip: str | None,
    details: dict[str, Any],
) -> str:
    """Build a concise notification body."""
    parts: list[str] = []

    # Device identifier — prefer hostname, fall back to MAC
    device_label = hostname or mac
    if device_label:
        parts.append(f"Device: *{device_label}*")
    if ip and ip != hostname:
        parts.append(f"IP: `{ip}`")
    if mac and mac != device_label:
        parts.append(f"MAC: `{mac}`")

    # Event-specific details
    if event_type == "device.offline" and details.get("last_ip"):
        parts.append(f"Last IP: `{details['last_ip']}`")
    elif event_type == "availability.down" and details.get("consecutive_failures"):
        parts.append(f"Missed probes: {details['consecutive_failures']}")
    elif event_type == "speed.slow":
        if details.get("download_mbps"):
            parts.append(f"Download: {details['download_mbps']:.1f} Mbps")
        if details.get("threshold_mbps"):
            parts.append(f"Threshold: {details['threshold_mbps']:.1f} Mbps")

    return "\n".join(parts) if parts else event_type


class NotificationDispatcher:
    """
    Dispatches notifications for significant events.

    Thread-safe: all state is in EventEngine (in-memory rate limit tracker).
    """

    def __init__(
        self,
        engine: EventEngine,
        telegram: TelegramChannel | None = None,
    ) -> None:
        self._engine = engine
        self._telegram = telegram

    @classmethod
    def from_environment(cls) -> NotificationDispatcher:
        """
        Create a dispatcher with channels configured from environment variables.
        """
        engine = EventEngine(
            quiet_hours_start=23,
            quiet_hours_end=7,
            rate_limit_seconds=300,
        )
        telegram = TelegramChannel.from_settings()
        if telegram:
            logger.info("Telegram notifications enabled")
        else:
            logger.info("Telegram not configured — notifications disabled")

        return cls(engine=engine, telegram=telegram)

    async def dispatch(
        self,
        event_type: str,
        severity: str,
        mac: str | None = None,
        hostname: str | None = None,
        ip: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> bool:
        """
        Evaluate and dispatch a notification for an event.

        Returns True if a notification was sent.
        """
        details = details or {}

        # Only notify for urgent/high severity
        if severity not in _NOTIFY_SEVERITIES:
            return False

        # Check quiet hours and global should_notify
        if not self._engine.should_notify(event_type, severity):
            return False

        # Check per-device rate limit
        rate_key = mac or "system"
        if not self._engine.check_rate_limit(rate_key, event_type):
            return False

        title = _EVENT_TITLES.get(event_type, event_type)
        body = _format_body(event_type, mac, hostname, ip, details)

        sent = False
        if self._telegram:
            ok = await self._telegram.send(
                title=title,
                body=body,
                priority=severity,
            )
            if ok:
                sent = True
                logger.info("Telegram notification sent: %s (%s)", event_type, mac or "system")
            else:
                logger.warning("Telegram notification failed: %s", event_type)

        return sent
