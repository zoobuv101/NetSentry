"""
NetSentry configuration — all settings loaded from environment variables.
Missing optional integration credentials log a WARNING but do not prevent startup.
"""

from __future__ import annotations

import logging
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ────────────────────────────────────────────────────────────
    app_version: str = "0.1.0"
    log_level: str = "INFO"
    db_path: str = "/data/netsentry.db"

    # ── API ────────────────────────────────────────────────────────────────────
    api_host: str = "0.0.0.0"
    api_port: int = 8282
    api_key: str | None = None  # Optional: enable X-API-Key header auth

    # ── HTTPS ──────────────────────────────────────────────────────────────────
    https: bool = False
    tls_cert_path: str | None = None
    tls_key_path: str | None = None

    # ── Scanner ────────────────────────────────────────────────────────────────
    scan_subnets: str | None = None  # Comma-separated; None = auto-detect
    scan_interval_arp: int = 300  # seconds
    scan_interval_ports: int = 900
    scan_rate_limit: int = 1000  # packets per second
    scan_offline_threshold: int = 2  # missed cycles before marking offline

    # ── Integrations ───────────────────────────────────────────────────────────
    enable_deco_integration: bool = True
    enable_pfsense_integration: bool = True
    enable_adguard_integration: bool = True
    enable_full_port_scan: bool = True
    enable_os_fingerprinting: bool = True
    enable_snmp: bool = False

    deco_host: str | None = None
    deco_username: str | None = None
    deco_password: str | None = None
    deco_poll_interval: int = 30

    pfsense_api_url: str | None = None
    pfsense_api_key: str | None = None
    pfsense_verify_ssl: bool = False
    # SSH-based pfSense integration (used by default — no REST package needed)
    pfsense_host: str | None = None
    pfsense_ssh_port: int = 22
    pfsense_username: str = "admin"
    pfsense_key_path: str = "/config/id_rsa"

    adguard_url: str | None = None
    adguard_username: str | None = None
    adguard_password: str | None = None

    # ── Notifications ──────────────────────────────────────────────────────────
    ntfy_url: str = "http://ntfy:80"
    ntfy_topic: str = "netsentry"
    ntfy_token: str | None = None
    ntfy_upstream_base_url: str | None = None

    enable_telegram: bool = False
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None

    # ── AI Identification ──────────────────────────────────────────────────────
    enable_ai_identification: bool = False
    anthropic_api_key: str | None = None
    ai_identification_model: str = "claude-haiku-4-5-20251001"
    ai_identification_confidence_threshold: float = 0.6
    ai_max_calls_per_cycle: int = 10

    # ── Speed Testing ──────────────────────────────────────────────────────────
    enable_speedtest: bool = True
    enable_librespeed: bool = False
    speedtest_backend: str = "librespeed"
    speedtest_interval: int = 21600  # 6 hours
    speedtest_download_threshold_mbps: float = 0.0  # 0 = disabled
    speedtest_latency_threshold_ms: float = 0.0  # 0 = disabled

    # ── Availability Monitoring ────────────────────────────────────────────────
    enable_availability_monitoring: bool = True
    availability_max_monitored: int = 50

    # ── Cache ──────────────────────────────────────────────────────────────────
    enable_redis_cache: bool = False

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        valid = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in valid:
            raise ValueError(f"log_level must be one of {valid}")
        return upper

    @field_validator("speedtest_backend")
    @classmethod
    def validate_speedtest_backend(cls, v: str) -> str:
        valid = {"librespeed", "ookla", "fast"}
        if v.lower() not in valid:
            raise ValueError(f"speedtest_backend must be one of {valid}")
        return v.lower()

    def warn_missing_optional(self) -> None:
        """Log warnings for unconfigured optional integrations at startup."""
        if self.enable_deco_integration and not self.deco_host:
            logger.warning(
                "DECO_HOST not set — Deco integration disabled. "
                "Set ENABLE_DECO_INTEGRATION=false to suppress this warning."
            )
        if self.enable_pfsense_integration and not self.pfsense_api_url:
            logger.warning("PFSENSE_API_URL not set — pfSense integration disabled.")
        if self.enable_adguard_integration and not self.adguard_url:
            logger.warning("ADGUARD_URL not set — AdGuard integration disabled.")
        if self.enable_telegram and not self.telegram_bot_token:
            logger.warning("TELEGRAM_BOT_TOKEN not set — Telegram notifications disabled.")
        if self.enable_ai_identification and not self.anthropic_api_key:
            logger.warning(
                "ANTHROPIC_API_KEY not set — AI identification disabled. "
                "Set ENABLE_AI_IDENTIFICATION=false to suppress this warning."
            )


@lru_cache
def get_settings() -> Settings:
    """Return cached Settings instance. Use dependency injection in FastAPI."""
    return Settings()
