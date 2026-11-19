from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TelemetryRegistry:
    """Lightweight operational counters supplemented by Prometheus/OpenTelemetry."""

    http_requests_total: int = 0
    aqi_cache_hits_total: int = 0
    aqi_cache_misses_total: int = 0
    llm_requests_total: int = 0
    llm_fallback_total: int = 0
    provider_errors_by_name: dict[str, int] = field(default_factory=dict)


telemetry_registry = TelemetryRegistry()
