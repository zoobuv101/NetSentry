"""NetSentry Telegram Bot notification channel."""

from __future__ import annotations

import logging
import os

import httpx

logger = logging.getLogger(__name__)

_TELEGRAM_API = "https://api.telegram.org"

# Telegram message length limit
_MAX_LENGTH = 4096

# Map internal severity to Telegram message prefix emoji
_SEVERITY_EMOJI = {
    "urgent": "🚨",
    "high": "⚠️",
    "default": "📡",
    "info": "ℹ️",
    "low": "💤",
}


class TelegramChannel:
    """
    Sends notifications via Telegram Bot API.

    Uses plain Markdown formatting (not MarkdownV2) for simplicity.
    Messages are trimmed to Telegram's 4096 character limit.
    """

    def __init__(self, bot_token: str, chat_id: str) -> None:
        self._bot_token = bot_token
        self._chat_id = chat_id

    @classmethod
    def from_settings(cls) -> TelegramChannel | None:
        """
        Create a TelegramChannel from environment variables.
        Returns None if TELEGRAM_BOT_TOKEN is not configured.
        """
        token = os.environ.get("TELEGRAM_BOT_TOKEN")
        chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
        if not token:
            return None
        return cls(bot_token=token, chat_id=chat_id)

    def _format_message(self, title: str, body: str, priority: str) -> str:
        """Format the Telegram message with Markdown."""
        emoji = _SEVERITY_EMOJI.get(priority, "📡")
        text = f"{emoji} *{title}*\n\n{body}"
        return text[:_MAX_LENGTH]

    async def send(
        self,
        title: str,
        body: str,
        priority: str = "default",
        tags: list[str] | None = None,
    ) -> bool:
        """
        Send a notification via Telegram sendMessage API.

        Args:
            title: Message title (bolded)
            body: Message body
            priority: Severity level (affects emoji prefix)
            tags: Unused for Telegram (kept for interface parity)

        Returns:
            True on success, False on any error.
        """
        text = self._format_message(title, body, priority)
        url = f"{_TELEGRAM_API}/bot{self._bot_token}/sendMessage"
        payload = {
            "chat_id": self._chat_id,
            "text": text,
            "parse_mode": "Markdown",
        }

        try:
            async with httpx.AsyncClient() as http:
                resp = await http.post(url, json=payload)
                data = resp.json()
                if not data.get("ok"):
                    logger.warning("Telegram sendMessage failed: %s", data)
                    return False
                return True
        except Exception as e:
            logger.warning("Telegram send failed: %s", e)
            return False
