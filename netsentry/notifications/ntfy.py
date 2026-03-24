"""NetSentry ntfy push notification channel."""

from __future__ import annotations

import logging
import os

import httpx

logger = logging.getLogger(__name__)

# ntfy priority values
_PRIORITY_MAP = {
    "urgent": "urgent",
    "high": "high",
    "default": "default",
    "info": "low",
    "low": "min",
}


class NtfyChannel:
    """
    Sends push notifications via ntfy (https://ntfy.sh).

    Supports self-hosted ntfy instances — set NTFY_URL to your topic URL,
    e.g. http://ntfy.example.com/netsentry
    """

    def __init__(self, url: str) -> None:
        self._url = url

    @classmethod
    def from_settings(cls) -> NtfyChannel | None:
        """
        Create an NtfyChannel from environment variables.
        Returns None if NTFY_URL is not configured.
        """
        url = os.environ.get("NTFY_URL")
        if not url:
            return None
        return cls(url=url)

    async def send(
        self,
        title: str,
        body: str,
        priority: str = "default",
        tags: list[str] | None = None,
    ) -> bool:
        """
        Send a push notification via ntfy.

        Args:
            title: Notification title
            body: Notification body
            priority: One of urgent/high/default/info/low
            tags: Optional ntfy emoji tags e.g. ["warning"]

        Returns:
            True on success, False on any error.
        """
        ntfy_priority = _PRIORITY_MAP.get(priority, "default")
        headers = {
            "Title": title,
            "Priority": ntfy_priority,
        }
        if tags:
            headers["Tags"] = ",".join(tags)

        try:
            async with httpx.AsyncClient() as http:
                resp = await http.post(
                    self._url,
                    content=body.encode(),
                    headers=headers,
                )
                if resp.status_code >= 400:
                    logger.warning("ntfy returned %d: %s", resp.status_code, resp.text)
                    return False
                return True
        except Exception as e:
            logger.warning("ntfy send failed: %s", e)
            return False
