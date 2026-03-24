"""NetSentry scan profile definitions."""

from __future__ import annotations

from enum import StrEnum


class ScanProfile(StrEnum):
    """
    Scan depth profiles controlling which scanner tools are invoked.

    QUICK    — ARP + ICMP only (fastest, ~30s for /24)
    STANDARD — + TCP common port scan (~60s)
    DEEP     — + OS fingerprinting + full port scan (minutes)
    """

    QUICK = "quick"
    STANDARD = "standard"
    DEEP = "deep"

    @classmethod
    def from_str(cls, value: str) -> ScanProfile:
        """Parse a profile from a string. Raises ValueError on invalid input."""
        try:
            return cls(value.lower())
        except ValueError:
            valid = [p.value for p in cls]
            raise ValueError(
                f"Invalid scan profile: '{value}'. Must be one of: {', '.join(valid)}"
            ) from None


# Tools enabled per profile
_PROFILE_TOOLS: dict[ScanProfile, set[str]] = {
    ScanProfile.QUICK: {"arp", "icmp"},
    ScanProfile.STANDARD: {"arp", "icmp", "tcp"},
    ScanProfile.DEEP: {"arp", "icmp", "tcp", "os", "full_ports"},
}


def get_profile_tools(profile: ScanProfile) -> set[str]:
    """Return the set of tool identifiers enabled for a given profile."""
    return _PROFILE_TOOLS[profile]
