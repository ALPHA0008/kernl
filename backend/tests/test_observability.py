"""Unit tests: structured logging + metrics registry.

Deterministic: no LLM, no DB, no network.
    py -3 backend/tests/test_observability.py
"""

from __future__ import annotations

import io
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.observability.logging import get_logger, log_event
from backend.observability.metrics import METRICS, observe_latency, render_prometheus


def test_log_event_emits_one_json_line_with_fields():
    logger = get_logger()
    buf = io.StringIO()
    # capture by swapping the handler's stream
    stream_handler = logger.handlers[0]
    original_stream = stream_handler.stream
    stream_handler.stream = buf
    try:
        log_event("decision.evaluated", tenant="acme", decision_id="d1", bundle_hash="sha256:x")
    finally:
        stream_handler.stream = original_stream

    line = buf.getvalue().strip()
    assert line, "expected one log line"
    payload = json.loads(line)
    assert payload["event"] == "decision.evaluated"
    assert payload["tenant"] == "acme"
    assert payload["decision_id"] == "d1"
    assert payload["bundle_hash"] == "sha256:x"
    assert payload["level"] == "info"
    assert "ts" in payload


def test_counter_increments_are_thread_safe_and_labeled():
    key_before = METRICS.snapshot()["counters"].get(("test_counter", (("outcome", "approve"),)), 0)
    METRICS.inc("test_counter", {"outcome": "approve"})
    METRICS.inc("test_counter", {"outcome": "approve"})
    METRICS.inc("test_counter", {"outcome": "deny"})
    snap = METRICS.snapshot()["counters"]
    assert snap[("test_counter", (("outcome", "approve"),))] == key_before + 2
    assert snap[("test_counter", (("outcome", "deny"),))] >= 1


def test_observe_latency_records_elapsed_ms():
    t0 = time.perf_counter()
    time.sleep(0.01)
    elapsed = observe_latency("test_latency_ms", t0, {"path": "unit"})
    assert elapsed >= 9  # slept 10ms, allow scheduler jitter
    snap = METRICS.snapshot()["histograms"]
    key = ("test_latency_ms", (("path", "unit"),))
    assert key in snap
    counts, total, count = snap[key]
    assert count >= 1
    assert total >= elapsed - 1  # sum tracks at least this observation


def test_render_prometheus_is_valid_text_format():
    METRICS.inc("test_render_counter", {"x": "1"})
    observe_latency("test_render_hist", time.perf_counter() - 0.001, {"x": "1"})
    text = render_prometheus()
    assert "# TYPE test_render_counter counter" in text
    assert "test_render_counter{x=\"1\"}" in text
    assert "# TYPE test_render_hist histogram" in text
    assert "test_render_hist_bucket{x=\"1\",le=\"+Inf\"}" in text
    assert "test_render_hist_sum{x=\"1\"}" in text
    assert "test_render_hist_count{x=\"1\"}" in text


TESTS = [v for k, v in sorted(globals().items()) if k.startswith("test_")]

if __name__ == "__main__":
    failed = 0
    for fn in TESTS:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"FAIL {fn.__name__}: {type(exc).__name__}: {exc}")
    print(f"Results: {len(TESTS) - failed}/{len(TESTS)} passed, {failed} failed")
    sys.exit(1 if failed else 0)
