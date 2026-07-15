"""In-process metrics registry: counters + latency histograms, thread-safe,
exposed as Prometheus text exposition format at GET /v1/metrics.

No exotic dependency -- a plain dict behind a lock. This is enough for a
single-cell V1 deployment (arc Part 11: ~115 decisions/sec is the design
envelope); a real time-series backend is a V3+ concern once there's a fleet
to aggregate across.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field

# latency histogram buckets in milliseconds -- tuned around the arc's P50<10ms
# reflexive-path target, with headroom for live Postgres round-trips in V1
_BUCKETS_MS = (5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000)


@dataclass
class _Registry:
    lock: threading.Lock = field(default_factory=threading.Lock)
    counters: dict[tuple[str, tuple[tuple[str, str], ...]], int] = field(default_factory=dict)
    # histogram: metric -> labelset -> (bucket_counts_list, sum, count)
    histograms: dict[tuple[str, tuple[tuple[str, str], ...]], list] = field(default_factory=dict)

    def inc(self, name: str, labels: dict[str, str] | None = None, by: int = 1) -> None:
        key = (name, tuple(sorted((labels or {}).items())))
        with self.lock:
            self.counters[key] = self.counters.get(key, 0) + by

    def observe(self, name: str, value_ms: float, labels: dict[str, str] | None = None) -> None:
        key = (name, tuple(sorted((labels or {}).items())))
        with self.lock:
            row = self.histograms.setdefault(key, [[0] * len(_BUCKETS_MS), 0.0, 0])
            counts, total, count = row
            for i, bound in enumerate(_BUCKETS_MS):
                if value_ms <= bound:
                    counts[i] += 1
            row[1] = total + value_ms
            row[2] = count + 1

    def snapshot(self) -> dict:
        with self.lock:
            return {
                "counters": dict(self.counters),
                "histograms": {k: list(v) for k, v in self.histograms.items()},
            }


METRICS = _Registry()


def observe_latency(name: str, started_at: float, labels: dict[str, str] | None = None) -> float:
    """started_at from time.perf_counter(); returns elapsed ms and records it."""
    import time

    elapsed_ms = (time.perf_counter() - started_at) * 1000
    METRICS.observe(name, elapsed_ms, labels)
    return elapsed_ms


def _fmt_labels(labels: tuple[tuple[str, str], ...]) -> str:
    if not labels:
        return ""
    body = ",".join(f'{k}="{v}"' for k, v in labels)
    return "{" + body + "}"


def render_prometheus() -> str:
    """Render the current snapshot as Prometheus text exposition format."""
    snap = METRICS.snapshot()
    lines: list[str] = []

    for (name, labels), value in sorted(snap["counters"].items()):
        lines.append(f"# TYPE {name} counter")
        lines.append(f"{name}{_fmt_labels(labels)} {value}")

    for (name, labels), (counts, total, count) in sorted(snap["histograms"].items()):
        lines.append(f"# TYPE {name} histogram")
        # each bucket count is already "observations <= bound" (accumulated in
        # observe()), which is exactly Prometheus's cumulative bucket semantics
        for bound, bucket_count in zip(_BUCKETS_MS, counts):
            bucket_labels = labels + (("le", str(bound)),)
            lines.append(f"{name}_bucket{_fmt_labels(bucket_labels)} {bucket_count}")
        inf_labels = labels + (("le", "+Inf"),)
        lines.append(f"{name}_bucket{_fmt_labels(inf_labels)} {count}")
        lines.append(f"{name}_sum{_fmt_labels(labels)} {total}")
        lines.append(f"{name}_count{_fmt_labels(labels)} {count}")

    return "\n".join(lines) + "\n"
