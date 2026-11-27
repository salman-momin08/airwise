"""In-process request latency percentiles and operational Prometheus counter registry."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field


@dataclass
class TelemetryRegistry:
    """Lightweight operational counters & latency ring buffer exposed to Prometheus/OTel."""

    http_requests_total: int = 0
    http_errors_total: int = 0
    aqi_cache_hits_total: int = 0
    aqi_cache_misses_total: int = 0
    llm_requests_total: int = 0
    llm_fallback_total: int = 0
    provider_errors_by_name: dict[str, int] = field(default_factory=dict)
    recent_latencies_ms: deque[float] = field(default_factory=lambda: deque(maxlen=512))

    def record_request(self, *, duration_ms: float, status_code: int) -> None:
        self.http_requests_total += 1
        if status_code >= 500:
            self.http_errors_total += 1
        self.recent_latencies_ms.append(round(duration_ms, 2))

    def percentile_latency_ms(self, percentile: float) -> float:
        if not self.recent_latencies_ms:
            return 0.0
        ordered = sorted(self.recent_latencies_ms)
        idx = min(len(ordered) - 1, max(0, round((percentile / 100.0) * (len(ordered) - 1))))
        return round(ordered[idx], 2)


telemetry_registry = TelemetryRegistry()
