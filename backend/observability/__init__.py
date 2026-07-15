"""Structured logging + in-process metrics for the /v1 decision path.

Step 8 (hardening) per docs/V1_EXECUTION_PLAN.md: every decision, escalation,
and publish carries tenant + decision + bundle identifiers in its log line,
and increments latency/outcome/escalation counters. Boring on purpose — plain
stdlib logging with a JSON formatter, a hand-rolled thread-safe registry
exposed as Prometheus text at GET /v1/metrics. No vendor SDK, no exotic dep;
matches the arc's "Postgres, not a platform" posture for V1.
"""

from backend.observability.logging import get_logger, log_event
from backend.observability.metrics import METRICS, observe_latency, render_prometheus

__all__ = ["get_logger", "log_event", "METRICS", "observe_latency", "render_prometheus"]
