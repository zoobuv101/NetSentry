"""NetSentry dashboard summary endpoint."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()


class DeviceSummary(BaseModel):
    total: int
    online: int
    offline: int
    new_today: int


class ScanSummary(BaseModel):
    last_scan_at: str | None
    last_scan_devices: int | None
    is_scanning: bool


class SpeedSummary(BaseModel):
    download_mbps: float | None
    upload_mbps: float | None
    ping_ms: float | None
    grade: str | None
    server: str | None
    tested_at: str | None


class NotificationSummary(BaseModel):
    ntfy_enabled: bool
    telegram_enabled: bool


class AdGuardSummary(BaseModel):
    total_queries: int | None
    blocked_queries: int | None
    block_rate_pct: float | None


class EventSummary(BaseModel):
    id: int
    event_type: str
    severity: str
    mac_address: str | None
    hostname: str | None
    ip_address: str | None
    details: dict[str, Any]
    timestamp: str


class DashboardSummaryResponse(BaseModel):
    devices: DeviceSummary
    last_scan: ScanSummary
    latest_speed_test: SpeedSummary
    notifications: NotificationSummary
    adguard: AdGuardSummary
    recent_events: list[EventSummary]


@router.get("/dashboard/summary", response_model=DashboardSummaryResponse)
async def get_dashboard_summary(request: Request) -> DashboardSummaryResponse:
    """
    Single endpoint that feeds all dashboard widgets.
    Aggregates device counts, last scan, speed test, notification status,
    AdGuard stats, and recent events.
    """
    conn = request.app.state.db

    # ── Device counts ─────────────────────────────────────────────────────
    async with conn.execute(
        "SELECT COUNT(*) as total, SUM(is_online) as online_count "
        "FROM devices WHERE lifecycle = 'active'"
    ) as cur:
        row = await cur.fetchone()

    total = int(row["total"]) if row else 0
    online = int(row["online_count"] or 0) if row else 0

    # New today
    from datetime import UTC, datetime

    from netsentry.db.utils import to_iso8601

    today_start = to_iso8601(datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0))
    async with conn.execute(
        "SELECT COUNT(*) FROM devices WHERE created_at >= ? AND lifecycle = 'active'",
        (today_start,),
    ) as cur:
        new_row = await cur.fetchone()
    new_today = int(new_row[0]) if new_row else 0

    # ── Last scan ─────────────────────────────────────────────────────────
    async with conn.execute(
        "SELECT started_at, completed_at, devices_found FROM scan_runs "
        "ORDER BY started_at DESC LIMIT 1"
    ) as cur:
        scan_row = await cur.fetchone()

    last_scan = ScanSummary(
        last_scan_at=scan_row["started_at"] if scan_row else None,
        last_scan_devices=scan_row["devices_found"] if scan_row else None,
        is_scanning=False,
    )

    # ── Latest speed test ─────────────────────────────────────────────────
    async with conn.execute(
        "SELECT download_mbps, upload_mbps, ping_ms, grade, server, tested_at "
        "FROM speed_tests ORDER BY tested_at DESC LIMIT 1"
    ) as cur:
        speed_row = await cur.fetchone()

    speed = SpeedSummary(
        download_mbps=float(speed_row["download_mbps"]) if speed_row else None,
        upload_mbps=float(speed_row["upload_mbps"]) if speed_row else None,
        ping_ms=float(speed_row["ping_ms"]) if speed_row else None,
        grade=speed_row["grade"] if speed_row else None,
        server=speed_row["server"] if speed_row else None,
        tested_at=speed_row["tested_at"] if speed_row else None,
    )

    # ── Notification status ───────────────────────────────────────────────
    notifications = NotificationSummary(
        ntfy_enabled=bool(os.environ.get("NTFY_URL")),
        telegram_enabled=bool(os.environ.get("TELEGRAM_BOT_TOKEN")),
    )

    # ── AdGuard stats ─────────────────────────────────────────────────────
    async with conn.execute(
        "SELECT value FROM system_config WHERE key = 'adguard.last_stats'"
    ) as cur:
        ag_row = await cur.fetchone()

    adguard = AdGuardSummary(total_queries=None, blocked_queries=None, block_rate_pct=None)
    if ag_row:
        try:
            ag_data = json.loads(ag_row["value"])
            adguard = AdGuardSummary(
                total_queries=ag_data.get("total_queries"),
                blocked_queries=ag_data.get("blocked_queries"),
                block_rate_pct=round(ag_data.get("block_rate", 0) * 100, 1),
            )
        except (json.JSONDecodeError, KeyError):
            pass

    # ── Recent events (joined with devices for hostname/IP) ──────────────
    async with conn.execute(
        "SELECT e.id, e.event_type, e.severity, e.mac_address, e.details, e.timestamp, "
        "       d.hostname, d.friendly_name, d.current_ip "
        "FROM events e "
        "LEFT JOIN devices d ON e.mac_address = d.mac_address "
        "ORDER BY e.timestamp DESC LIMIT 10"
    ) as cur:
        event_rows = await cur.fetchall()

    recent_events = []
    for row in event_rows:
        try:
            details = json.loads(row["details"] or "{}")
        except (json.JSONDecodeError, TypeError):
            details = {}
        recent_events.append(
            EventSummary(
                id=row["id"],
                event_type=row["event_type"],
                severity=row["severity"],
                mac_address=row["mac_address"],
                hostname=row["friendly_name"] or row["hostname"],
                ip_address=row["current_ip"],
                details=details,
                timestamp=row["timestamp"],
            )
        )

    return DashboardSummaryResponse(
        devices=DeviceSummary(
            total=total,
            online=online,
            offline=total - online,
            new_today=new_today,
        ),
        last_scan=last_scan,
        latest_speed_test=speed,
        notifications=notifications,
        adguard=adguard,
        recent_events=recent_events,
    )
