"""
NetSentry database utilities.

MAC address normalisation, timestamp helpers, and other shared DB utilities.
All repository classes use these functions — never raw string manipulation.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

_MAC_STRIP = re.compile(r"[:\-\. ]")
_MAC_HEX = re.compile(r"^[0-9a-f]{12}$")


def normalise_mac(mac: str) -> str:
    """
    Normalise a MAC address to lowercase colon-separated format.

    Accepts: AA:BB:CC:DD:EE:FF, AA-BB-CC-DD-EE-FF, AABBCCDDEEFF (any case)

    Returns: aa:bb:cc:dd:ee:ff

    Raises:
        ValueError: If the input is not a valid 48-bit MAC address.
    """
    stripped = _MAC_STRIP.sub("", mac).lower()
    if not _MAC_HEX.match(stripped):
        raise ValueError(
            f"Invalid MAC address: '{mac}'. "
            "Expected 6 hex bytes separated by colons, dashes, or no separator."
        )
    return ":".join(stripped[i : i + 2] for i in range(0, 12, 2))


def utc_now() -> datetime:
    """Return the current UTC datetime (timezone-aware)."""
    return datetime.now(UTC)


def to_iso8601(dt: datetime) -> str:
    """Serialise a datetime to ISO-8601 UTC string for SQLite TEXT storage."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.isoformat()


def from_iso8601(s: str) -> datetime:
    """Deserialise an ISO-8601 string from SQLite to a timezone-aware datetime."""
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


VALID_LIFECYCLES = {"active", "historic", "deleted"}


def validate_lifecycle(value: str) -> str:
    """
    Validate a lifecycle value.

    Raises:
        ValueError: If the value is not a valid lifecycle state.
    """
    if value not in VALID_LIFECYCLES:
        raise ValueError(
            f"Invalid lifecycle value: '{value}'. "
            f"Must be one of: {', '.join(sorted(VALID_LIFECYCLES))}"
        )
    return value
