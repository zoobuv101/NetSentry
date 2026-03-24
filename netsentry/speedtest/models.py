"""NetSentry speed test data models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SpeedTestResult:
    """Result from a single internet speed test."""

    download_mbps: float
    upload_mbps: float
    ping_ms: float
    backend: str  # "librespeed" or "ookla"
    server: str | None = None
    tested_at: str | None = None

    @property
    def grade(self) -> str:
        """
        Grade the connection quality based on download speed and ping.

        excellent: ≥100 Mbps download, ≤20ms ping
        good:      ≥50 Mbps download
        fair:      ≥20 Mbps download
        poor:      <20 Mbps download or >100ms ping
        """
        if self.ping_ms > 100 or self.download_mbps < 20:
            return "poor"
        if self.download_mbps < 50:
            return "fair"
        if self.download_mbps < 100 or self.ping_ms > 20:
            return "good"
        return "excellent"
