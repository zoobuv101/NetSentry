"""AdGuard Home integration exceptions."""

from __future__ import annotations


class AdGuardError(Exception):
    """Base class for AdGuard integration errors."""


class AdGuardConnectionError(AdGuardError):
    """Cannot connect to AdGuard Home."""


class AdGuardAuthError(AdGuardError):
    """AdGuard Home authentication failed."""
