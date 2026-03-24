"""NetSentry OUI vendor database (Wireshark manuf file format)."""

from __future__ import annotations

import logging
from pathlib import Path

from netsentry.db.utils import normalise_mac

logger = logging.getLogger(__name__)

# Default bundled manuf file path inside the container
DEFAULT_MANUF_PATH = "/app/data/manuf"


class OuiDatabase:
    """
    In-memory OUI lookup table loaded from a Wireshark manuf file.

    Format: OUI<tab>ShortName<tab>LongName
    Example: AA:BB:CC  VendorCorp  Vendor Corporation
    """

    def __init__(self, manuf_path: str = DEFAULT_MANUF_PATH) -> None:
        self._path = manuf_path
        self._table: dict[str, str] = {}
        self._load()

    def _load(self) -> None:
        """Load and parse the manuf file into an in-memory dict."""
        path = Path(self._path)
        if not path.exists():
            logger.warning("OUI manuf file not found at %s — vendor lookup disabled", self._path)
            return

        count = 0
        with path.open(encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split("\t")
                if len(parts) < 2:
                    continue
                oui_raw = parts[0].strip()
                # Long name preferred; fall back to short name
                long_name = parts[2].strip() if len(parts) >= 3 else parts[1].strip()
                # Normalise OUI to lowercase colon-separated (3 bytes)
                oui_clean = oui_raw.lower().replace("-", ":").replace(".", ":")
                self._table[oui_clean] = long_name
                count += 1

        logger.info("Loaded %d OUI entries from %s", count, self._path)

    def lookup(self, mac: str) -> str | None:
        """
        Look up the vendor for a MAC address.

        Args:
            mac: MAC address in any format (normalised internally)

        Returns:
            Vendor string, or None if not found.
        """
        try:
            norm = normalise_mac(mac)
        except ValueError:
            return None
        oui = norm[:8]  # aa:bb:cc
        return self._table.get(oui)

    def reload(self) -> None:
        """Reload the manuf file (called by weekly refresh job)."""
        self._table.clear()
        self._load()

    def __len__(self) -> int:
        return len(self._table)
