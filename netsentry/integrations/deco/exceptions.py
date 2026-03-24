"""TP-Link Deco integration exceptions."""

from __future__ import annotations


class DecoError(Exception):
    """Base class for all Deco integration errors."""


class DecoAuthError(DecoError):
    """Authentication failed or session invalidated (403)."""


class DecoConnectionError(DecoError):
    """Cannot connect to the Deco main node."""


class DecoProtocolError(DecoError):
    """Unexpected response format or decryption failure."""
