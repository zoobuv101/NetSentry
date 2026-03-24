"""NetSentry Event Engine — quiet hours, rate limiting, severity routing."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

logger = logging.getLogger(__name__)

# Canonical severity per event type
EVENT_SEVERITIES: dict[str, str] = {
    "device.new": "urgent",
    "device.offline": "high",
    "device.online": "info",
    "deco.device_roamed": "info",
    "system.startup": "info",
    "system.scan_failed": "high",
    "availability.down": "urgent",
    "availability.up": "info",
    "speed.slow": "high",
}

# Severities that bypass quiet hours
_BYPASS_QUIET = {"urgent"}


class EventEngine:
    """
    Decides whether an event should trigger a notification.

    Checks:
    1. Quiet hours — suppress non-urgent events during configured window
    2. Rate limiting — suppress repeated events for the same device within cooldown
    """

    def __init__(
        self,
        quiet_hours_start: int = 23,
        quiet_hours_end: int = 7,
        rate_limit_seconds: int = 300,
    ) -> None:
        self._quiet_start = quiet_hours_start
        self._quiet_end = quiet_hours_end
        self._rate_limit_seconds = rate_limit_seconds
        # {(mac, event_type): last_sent_timestamp}
        self._last_sent: dict[tuple[str, str], datetime] = {}

    def should_notify(
        self,
        event_type: str,
        severity: str,
        hour: int | None = None,
    ) -> bool:
        """
        Return True if this event should trigger a notification now.

        Args:
            event_type: The event type string
            severity: Event severity level
            hour: Hour override (0-23) for testing; defaults to current UTC hour
        """
        if severity in _BYPASS_QUIET:
            return True

        current_hour = hour if hour is not None else datetime.now(UTC).hour

        if self._is_quiet_hour(current_hour):
            logger.debug("Suppressing %s (severity=%s) during quiet hours", event_type, severity)
            return False

        return True

    def _is_quiet_hour(self, hour: int) -> bool:
        """Return True if the given hour falls in the quiet window."""
        start, end = self._quiet_start, self._quiet_end
        if start <= end:
            # e.g. 02:00–06:00 — simple range
            return start <= hour < end
        else:
            # e.g. 23:00–07:00 — wraps midnight
            return hour >= start or hour < end

    def check_rate_limit(self, mac: str, event_type: str) -> bool:
        """
        Return True if the event is allowed (not rate-limited).
        Records the event timestamp if allowed.

        The rate limit is per (mac, event_type) pair.
        """
        key = (mac, event_type)
        now = datetime.now(UTC)
        last = self._last_sent.get(key)

        if last is not None:
            elapsed = (now - last).total_seconds()
            if elapsed < self._rate_limit_seconds:
                logger.debug(
                    "Rate-limited %s for %s (%.0fs < %ds cooldown)",
                    event_type,
                    mac,
                    elapsed,
                    self._rate_limit_seconds,
                )
                return False

        self._last_sent[key] = now
        return True
