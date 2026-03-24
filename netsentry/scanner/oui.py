"""NetSentry OUI vendor database."""

from __future__ import annotations

import logging
import re
from pathlib import Path

from netsentry.db.utils import normalise_mac

logger = logging.getLogger(__name__)

# Bundled minimal database ships with the package
_BUNDLED_MANUF = Path(__file__).parent.parent / "data" / "manuf"
# Full database downloaded at build time (Wireshark format)
_SYSTEM_MANUF = Path("/app/data/manuf")

# OUI line: "AA:BB:CC  ShortName  Long Name"  (tabs or 2+ spaces)
_OUI_LINE_RE = re.compile(
    r"^([0-9A-Fa-f]{2}[:\-][0-9A-Fa-f]{2}[:\-][0-9A-Fa-f]{2})"  # OUI
    r"[ \t]+"  # separator
    r"(\S+)"  # short name
    r"(?:[ \t]+(.+))?$"  # optional long name
)


class OuiDatabase:
    """
    In-memory OUI lookup table.

    Loads from (in order of preference):
    1. /app/data/manuf  — full Wireshark database downloaded at Docker build time
    2. Bundled netsentry/data/manuf — minimal database shipped with the package
    """

    def __init__(self, manuf_path: str | None = None) -> None:
        self._table: dict[str, str] = {}

        if manuf_path:
            self._load(Path(manuf_path))
        elif _SYSTEM_MANUF.exists():
            self._load(_SYSTEM_MANUF)
        elif _BUNDLED_MANUF.exists():
            self._load(_BUNDLED_MANUF)
        else:
            logger.warning("No OUI manuf file found — vendor lookup disabled")

    def _load(self, path: Path) -> None:
        """Parse a Wireshark manuf file (tab or space separated)."""
        if not path.exists():
            logger.warning("OUI manuf file not found at %s", path)
            return

        count = 0
        with path.open(encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                match = _OUI_LINE_RE.match(line)
                if not match:
                    continue

                oui_raw = match.group(1)
                short_name = match.group(2)
                long_name = match.group(3)

                vendor = (long_name or short_name).strip()
                if not vendor:
                    continue

                # Normalise to lowercase colon-separated
                oui_clean = oui_raw.lower().replace("-", ":").replace(".", ":")
                self._table[oui_clean] = vendor
                count += 1

        logger.info("Loaded %d OUI entries from %s", count, path)

    def lookup(self, mac: str) -> str | None:
        """Look up vendor for a MAC address. Returns None if unknown."""
        try:
            norm = normalise_mac(mac)
        except ValueError:
            return None
        return self._table.get(norm[:8])

    def reload(self) -> None:
        self._table.clear()
        if _SYSTEM_MANUF.exists():
            self._load(_SYSTEM_MANUF)
        elif _BUNDLED_MANUF.exists():
            self._load(_BUNDLED_MANUF)

    def __len__(self) -> int:
        return len(self._table)
