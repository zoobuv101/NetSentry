"""NetSentry device categorisation engine."""

from __future__ import annotations

import logging
from typing import Protocol

import aiosqlite

from netsentry.db.repositories.devices import DeviceRepository
from netsentry.identification.rules import IdentificationResult, identify_by_rules


class _AiIdentifierProtocol(Protocol):
    async def identify(
        self,
        mac: str,
        vendor: str | None,
        hostname: str | None,
        open_ports: list[int],
        os_family: str | None = None,
    ) -> IdentificationResult: ...


logger = logging.getLogger(__name__)

# Minimum confidence to apply a rule-based result
_MIN_CONFIDENCE = 0.5


class DeviceCategoriser:
    """
    Applies identification results to the device inventory.

    Workflow per device:
    1. Run rule-based identification
    2. If confidence ≥ threshold → apply result
    3. If AI is enabled and confidence < 0.7 → call AI identifier
    4. Apply whichever result is better
    """

    def __init__(
        self,
        conn: aiosqlite.Connection,
        ai_identifier: _AiIdentifierProtocol | None = None,
        overwrite_manual: bool = False,
    ) -> None:
        self._conn = conn
        self._ai = ai_identifier
        self._overwrite_manual = overwrite_manual
        self._devices = DeviceRepository(conn)

    async def categorise(self, mac: str) -> IdentificationResult | None:
        """
        Identify and categorise a single device by MAC address.

        Args:
            mac: Normalised MAC address

        Returns:
            Applied IdentificationResult, or None if device not found.
        """
        device = await self._devices.get(mac)
        if device is None:
            return None

        # Respect manually set categories
        if device.category and not self._overwrite_manual:
            logger.debug("Skipping categorisation for %s — category already set", mac)
            return None

        # Rule-based identification
        result = identify_by_rules(
            vendor=device.vendor,
            hostname=device.hostname,
            open_ports=[],  # TCP scan results wired in US0029+
        )

        # AI fallback (if enabled and confidence is low)
        if self._ai is not None and result.confidence < 0.7:
            try:
                ai_result = await self._ai.identify(
                    mac=mac,
                    vendor=device.vendor,
                    hostname=device.hostname,
                    open_ports=[],
                    os_family=device.os_family,
                )
                if ai_result.confidence > result.confidence:
                    result = ai_result
                    logger.debug("AI improved identification for %s: %s", mac, result.category)
            except Exception as e:
                logger.warning("AI identification error for %s: %s", mac, e)

        if result.confidence < _MIN_CONFIDENCE:
            logger.debug("Confidence too low for %s (%.2f) — skipping", mac, result.confidence)
            return result

        # Apply to device
        await self._devices.patch(
            mac=mac,
            category=result.category,
            device_type=result.device_type,
        )
        logger.info(
            "Categorised %s → %s/%s (conf=%.2f, src=%s)",
            mac,
            result.category,
            result.device_type,
            result.confidence,
            result.source,
        )
        return result

    async def categorise_all(self, limit: int = 200) -> int:
        """
        Run categorisation across all active devices.

        Returns count of devices updated.
        """
        devices = await self._devices.list(lifecycle="active", limit=limit)
        updated = 0
        for device in devices:
            result = await self.categorise(device.mac_address)
            if result and result.category:
                updated += 1
        logger.info("Categorisation run complete: %d/%d devices updated", updated, len(devices))
        return updated
