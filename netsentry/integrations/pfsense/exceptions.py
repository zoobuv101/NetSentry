"""pfSense integration exceptions."""

from __future__ import annotations


class PfSenseError(Exception):
    """Base class for pfSense integration errors."""


class PfSenseConnectionError(PfSenseError):
    """Cannot connect to pfSense via SSH."""


class PfSenseCommandError(PfSenseError):
    """SSH command returned a non-zero exit code."""
