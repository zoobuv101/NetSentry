"""
NetSentry AI-assisted device identification via Claude API.

Disabled by default — enabled by setting ENABLE_AI_IDENTIFICATION=true
and providing an ANTHROPIC_API_KEY. Falls back to rule-based results
when disabled or on API error.
"""

from __future__ import annotations

import json
import logging
import re

try:
    import anthropic
except ImportError:
    anthropic = None  # type: ignore[assignment]

from netsentry.identification.rules import IdentificationResult

logger = logging.getLogger(__name__)

_MODEL = "claude-haiku-4-5-20251001"
_MAX_TOKENS = 256

_SYSTEM_PROMPT = """\
You are a network device classifier. Given device fingerprint data, respond ONLY
with a JSON object containing:
- "category": one of: Personal Device, Network Infrastructure, Printer, NAS / Storage,
  Smart TV, Smart Speaker, Smart Home, Camera, Games Console, Server, Media Server,
  IoT Device, or null if unknown
- "device_type": specific device type string, or null
- "confidence": float 0.0-1.0

Respond with ONLY the JSON object, no preamble or explanation."""


class AiIdentifier:
    """
    Identifies devices using the Claude API.

    Only called when:
    1. ENABLE_AI_IDENTIFICATION=true
    2. Rule-based identification returned low confidence (< 0.7)
    3. An Anthropic API key is configured
    """

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    @classmethod
    def from_settings(cls, api_key: str | None = None) -> AiIdentifier | None:
        """
        Create an AiIdentifier from settings.
        Returns None if AI identification is not configured.
        """
        if not api_key:
            return None
        return cls(api_key=api_key)

    async def identify(
        self,
        mac: str,
        vendor: str | None,
        hostname: str | None,
        open_ports: list[int],
        os_family: str | None = None,
    ) -> IdentificationResult:
        """
        Ask Claude to classify the device based on its fingerprint.

        Returns IdentificationResult. Falls back to empty result on any error.
        """
        prompt = self._build_prompt(mac, vendor, hostname, open_ports, os_family)
        try:
            if anthropic is None:
                raise ImportError("anthropic not installed")
            client = anthropic.Anthropic(api_key=self._api_key)
            response = client.messages.create(
                model=_MODEL,
                max_tokens=_MAX_TOKENS,
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            from anthropic.types import TextBlock

            text_block = next(
                (b for b in response.content if isinstance(b, TextBlock) or hasattr(b, "text")),
                None,
            )
            if text_block is None:
                return IdentificationResult(source="ai:no_text")
            text = str(text_block.text).strip()
            return self._parse_response(text)
        except Exception as e:
            logger.warning("AI identification failed: %s", e)
            return IdentificationResult(source="ai:error")

    def _build_prompt(
        self,
        mac: str,
        vendor: str | None,
        hostname: str | None,
        open_ports: list[int],
        os_family: str | None,
    ) -> str:
        parts = [f"MAC OUI prefix: {mac[:8]}"]
        if vendor:
            parts.append(f"Vendor: {vendor}")
        if hostname:
            parts.append(f"Hostname: {hostname}")
        if open_ports:
            parts.append(f"Open ports: {', '.join(str(p) for p in sorted(open_ports))}")
        if os_family:
            parts.append(f"OS family: {os_family}")
        return "\n".join(parts)

    def _parse_response(self, text: str) -> IdentificationResult:
        """Parse Claude's JSON response into an IdentificationResult."""
        # Strip markdown code fences if present
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE).strip()
        try:
            data = json.loads(text)
            return IdentificationResult(
                category=data.get("category"),
                device_type=data.get("device_type"),
                confidence=float(data.get("confidence", 0.0)),
                source="ai",
            )
        except (json.JSONDecodeError, ValueError, TypeError):
            logger.debug("Could not parse AI response as JSON: %r", text)
            return IdentificationResult(source="ai:parse_error")
