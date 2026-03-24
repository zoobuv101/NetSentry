"""NetSentry notification configuration and test endpoints."""

from __future__ import annotations

import logging
import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from netsentry.notifications.ntfy import NtfyChannel
from netsentry.notifications.telegram import TelegramChannel

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Response schemas ──────────────────────────────────────────────────────────


class NtfyConfig(BaseModel):
    enabled: bool
    url: str | None


class TelegramConfig(BaseModel):
    enabled: bool
    chat_id: str | None


class QuietHoursConfig(BaseModel):
    enabled: bool
    start_hour: int
    end_hour: int


class NotificationConfigResponse(BaseModel):
    ntfy: NtfyConfig
    telegram: TelegramConfig
    quiet_hours: QuietHoursConfig


class TestNotificationResponse(BaseModel):
    sent: bool
    channel: str
    message: str


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.get("/notifications/config", response_model=NotificationConfigResponse)
async def get_notification_config() -> NotificationConfigResponse:
    """Return the current notification channel configuration."""
    ntfy_url = os.environ.get("NTFY_URL")
    telegram_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    telegram_chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    quiet_start = int(os.environ.get("QUIET_HOURS_START", "23"))
    quiet_end = int(os.environ.get("QUIET_HOURS_END", "7"))
    quiet_enabled = os.environ.get("ENABLE_QUIET_HOURS", "true").lower() == "true"

    return NotificationConfigResponse(
        ntfy=NtfyConfig(enabled=bool(ntfy_url), url=ntfy_url),
        telegram=TelegramConfig(
            enabled=bool(telegram_token),
            chat_id=telegram_chat_id if telegram_token else None,
        ),
        quiet_hours=QuietHoursConfig(
            enabled=quiet_enabled,
            start_hour=quiet_start,
            end_hour=quiet_end,
        ),
    )


@router.post("/notifications/test/ntfy", response_model=TestNotificationResponse)
async def test_ntfy() -> TestNotificationResponse:
    """Send a test notification via ntfy."""
    channel = NtfyChannel.from_settings()
    if channel is None:
        raise HTTPException(
            status_code=400,
            detail={"code": "NTFY_NOT_CONFIGURED", "message": "NTFY_URL is not set"},
        )

    sent = await channel.send(
        title="NetSentry Test",
        body="✅ ntfy is configured correctly.",
        priority="default",
        tags=["white_check_mark"],
    )
    return TestNotificationResponse(
        sent=sent,
        channel="ntfy",
        message="Test notification sent" if sent else "Failed to send — check logs",
    )


@router.post("/notifications/test/telegram", response_model=TestNotificationResponse)
async def test_telegram() -> TestNotificationResponse:
    """Send a test notification via Telegram."""
    channel = TelegramChannel.from_settings()
    if channel is None:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "TELEGRAM_NOT_CONFIGURED",
                "message": "TELEGRAM_BOT_TOKEN is not set",
            },
        )

    sent = await channel.send(
        title="NetSentry Test",
        body="✅ Telegram is configured correctly.",
        priority="default",
    )
    return TestNotificationResponse(
        sent=sent,
        channel="telegram",
        message="Test notification sent" if sent else "Failed to send — check logs",
    )
