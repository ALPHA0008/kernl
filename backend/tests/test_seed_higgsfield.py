"""Seed verification: the authored higgsfield bundle [synthetic] must pass
its entire golden set through the replay engine, 100%.

Mirrors test_seed_rivanly.py's structure and guarantee for the second
seeded corpus. Deterministic: no LLM, no DB, no network.
    py -3 backend/tests/test_seed_higgsfield.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.bundle.canonical import bundle_content_hash
from backend.bundle.seed_higgsfield import build_bundle, build_golden_cases
from backend.replay.engine import InMemoryReplayRunStore, ReplayEngine


def test_bundle_builds_and_evidence_is_verified():
    bundle = build_bundle()
    assert len(bundle.policies) == 18
    assert len(bundle.workflows) == 3  # refund, bug_triage, expense
    for p in bundle.policies:
        assert p.evidence, p.id
        for ev in p.evidence:
            assert ev.span_end > ev.span_start
            assert ev.source_version.startswith("sha256:")


def test_bundle_hash_is_stable_across_builds():
    assert bundle_content_hash(build_bundle()) == bundle_content_hash(build_bundle())


def test_golden_set_shape():
    cases = build_golden_cases()
    assert len(cases) >= 28  # refund + bug_triage + expense coverage
    assert all(c.synthetic for c in cases)  # [synthetic] until real tenants exist
    # all three workflows are represented
    assert {c.workflow for c in cases} == {"refund", "bug_triage", "expense"}
    ids = [c.case_id for c in cases]
    assert len(ids) == len(set(ids)), "duplicate golden case ids"


def test_golden_cases_pass_100_percent():
    bundle = build_bundle()
    cases = build_golden_cases()
    engine = ReplayEngine(InMemoryReplayRunStore())
    run = engine.run(company_id="higgsfield", cases=cases, candidate=bundle)

    failures = [
        r for r in run.results
        if r.error is not None or r.golden_pass is not True
    ]
    for r in failures:
        print(
            f"FAIL {r.case_id}: expected {r.expected_kind}/{r.expected_action} "
            f"got {r.candidate_kind}/{r.candidate_action} "
            f"(policy={r.candidate_policy_id}, error={r.error})"
        )
    assert not failures, f"{len(failures)}/{run.summary.total} golden cases failed"
    assert run.summary.errors == 0


TESTS = [v for k, v in sorted(globals().items()) if k.startswith("test_")]

if __name__ == "__main__":
    failed = 0
    for fn in TESTS:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"FAIL {fn.__name__}: {exc}")
    print(f"Results: {len(TESTS) - failed}/{len(TESTS)} passed, {failed} failed")
    sys.exit(1 if failed else 0)
