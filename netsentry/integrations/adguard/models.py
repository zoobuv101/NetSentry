"""AdGuard Home data models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AdGuardStats:
    """Parsed AdGuard Home statistics."""

    total_queries: int
    blocked_queries: int
    block_rate: float
    avg_processing_ms: float = 0.0

    @classmethod
    def from_raw(cls, raw: dict) -> AdGuardStats:  # type: ignore[type-arg]
        total = int(raw.get("num_dns_queries", 0))
        blocked = int(raw.get("num_blocked_filtering", 0))
        block_rate = blocked / total if total > 0 else 0.0
        avg_ms = float(raw.get("avg_processing_time", 0.0)) * 1000
        return cls(
            total_queries=total,
            blocked_queries=blocked,
            block_rate=block_rate,
            avg_processing_ms=avg_ms,
        )
