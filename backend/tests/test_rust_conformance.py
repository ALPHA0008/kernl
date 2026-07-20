"""Differential conformance: the Rust edge evaluator vs the Python reference.

This is the load-bearing test for the Rust evaluator (edge-evaluator/). A second
enforce path is only safe if it provably agrees with the reference on every
input -- a Rust evaluator that silently diverges would violate the determinism
guarantee in the worst possible place. This harness runs BOTH evaluators on the
same (facts, bundle, workflow) triples and asserts identical OUTCOMES and the
enforce-critical precedence facts (winner, applied_rules, tie, dominance).

Inputs:
  1. Every golden case in BOTH seed corpora (real authored policy).
  2. Hypothesis-generated bundles + facts (shapes no author wrote), reusing the
     generators from test_evaluator_properties.

Skips cleanly (like the Postgres contract suite) if the Rust binary is not
built -- it never fakes a pass. Build it with:
    cd edge-evaluator && cargo build --release

    py -3 backend/tests/test_rust_conformance.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

# Locate the built Rust binary (release; .exe on Windows).
_BIN_CANDIDATES = [
    ROOT / "edge-evaluator" / "target" / "release" / "kernl-eval.exe",
    ROOT / "edge-evaluator" / "target" / "release" / "kernl-eval",
]
RUST_BIN = next((p for p in _BIN_CANDIDATES if p.exists()), None)

if RUST_BIN is None:
    print(
        "SKIPPED: the Rust edge evaluator is not built. "
        "Run `cd edge-evaluator && cargo build --release` to enable the "
        "differential conformance suite. (This is a skip, not a pass: the Rust "
        "evaluator is NOT verified against Python until this suite runs green.)"
    )
    sys.exit(0)

from backend.bundle import seed_higgsfield, seed_rivanly
from backend.runtime.evaluator import EvaluationResult, evaluate


def _rust_decide(facts: dict, bundle_json: dict, workflow: str) -> dict:
    """Drive the Rust binary: one JSON request on stdin -> one JSON decision."""
    req = json.dumps({"facts": facts, "bundle": bundle_json, "workflow": workflow})
    proc = subprocess.run(
        [str(RUST_BIN)], input=req, capture_output=True, text=True, timeout=30
    )
    out = proc.stdout.strip()
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        raise AssertionError(
            f"Rust binary did not return JSON (exit {proc.returncode}): "
            f"{out!r} / stderr {proc.stderr!r}"
        )


def _py_outcome_view(result: EvaluationResult) -> dict:
    """Reduce the Python decision to the enforce-critical fields the Rust side
    emits, so the two are comparable. The Python trace carries much more (every
    ConditionResult); the enforce decision is these fields."""
    o = result.outcome
    p = result.trace.precedence
    view = {
        "outcome": {
            "kind": o.kind.value,
            "action": o.action,
            "policy_id": o.policy_id,
            "approval_required": o.approval_required,
            "approver_role": o.approver_role,
            "escalation_reason": o.escalation_reason.value if o.escalation_reason else None,
            "missing_facts": list(o.missing_facts),
            "conflict_between": list(o.conflict_between),
        },
        "precedence": {
            "applied_rules": list(p.applied_rules),
            "winner": p.winner,
            "tie_between": list(p.tie_between),
            "dominance_blocked_by": list(p.dominance_blocked_by),
        },
    }
    return view


def _rust_outcome_view(decision: dict) -> dict:
    """Normalize the Rust JSON to the same view (fill omitted optional fields to
    match Python's explicit Nones/empties)."""
    o = decision.get("outcome", {})
    p = decision.get("precedence", {})
    return {
        "outcome": {
            "kind": o.get("kind"),
            "action": o.get("action"),
            "policy_id": o.get("policy_id"),
            "approval_required": o.get("approval_required", False),
            "approver_role": o.get("approver_role"),
            "escalation_reason": o.get("escalation_reason"),
            "missing_facts": o.get("missing_facts", []),
            "conflict_between": o.get("conflict_between", []),
        },
        "precedence": {
            "applied_rules": p.get("applied_rules", []),
            "winner": p.get("winner"),
            "tie_between": p.get("tie_between", []),
            "dominance_blocked_by": p.get("dominance_blocked_by", []),
        },
    }


def _assert_agree(facts: dict, bundle, workflow: str, label: str) -> None:
    bundle_json = json.loads(bundle.model_dump_json())
    py = _py_outcome_view(evaluate(facts, bundle, workflow))
    rs = _rust_outcome_view(_rust_decide(facts, bundle_json, workflow))
    assert py == rs, (
        f"DIVERGENCE [{label}] workflow={workflow} facts={facts}\n"
        f"  python: {json.dumps(py, sort_keys=True)}\n"
        f"  rust:   {json.dumps(rs, sort_keys=True)}"
    )


def test_conformance_on_both_seed_corpora():
    """Every golden case in both corpora: Rust and Python agree exactly."""
    for seed in (seed_rivanly, seed_higgsfield):
        bundle = seed.build_bundle()
        for case in seed.build_golden_cases():
            _assert_agree(case.facts, bundle, case.workflow, f"{seed.__name__}:{case.case_id}")


def test_conformance_on_generated_cases():
    """Hypothesis-generated bundles + facts: Rust and Python agree exactly on
    shapes no author wrote by hand -- the inputs most likely to expose a port
    bug (ties, dominance, overrides, boundary comparisons)."""
    from hypothesis import HealthCheck, given, settings
    from hypothesis import strategies as st

    from backend.tests.test_evaluator_properties import WORKFLOW, bundles, facts_for

    @settings(max_examples=200, deadline=None,
              suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    @given(b=bundles(), data=st.data())
    def _run(b, data):
        facts = data.draw(facts_for())
        _assert_agree(facts, b, WORKFLOW, "generated")

    _run()


TESTS = [v for k, v in sorted(globals().items()) if k.startswith("test_")]

if __name__ == "__main__":
    print(f"Rust binary: {RUST_BIN}")
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
