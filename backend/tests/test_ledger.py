"""Unit tests: Decision Ledger -- write-ahead, idempotency, hash chain.

Deterministic: no LLM, no DB, no network. Run directly or via pytest:
    py -3 backend/tests/test_ledger.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.bundle.canonical import bundle_content_hash
from backend.bundle.schema import (
    Bundle,
    Condition,
    Effect,
    Evidence,
    FactSpec,
    OutcomeKind,
    Policy,
    WorkflowSpec,
)
import threading

from backend.ledger.events import Actor, ChainConflict
from backend.ledger.service import DecisionService, LedgerUnavailableError
from backend.ledger.store import InMemoryLedgerStore


def _bundle() -> Bundle:
    wf = WorkflowSpec(
        name="refund",
        facts=(
            FactSpec(name="plan_type", value_type="string"),
            FactSpec(name="days_since_purchase", value_type="number"),
        ),
    )
    pol = Policy(
        id="refund.annual_14d",
        workflow="refund",
        effect=Effect(kind=OutcomeKind.APPROVE, action="approve_full_refund"),
        priority=70,
        conditions=(
            Condition(field="plan_type", operator="eq", value="annual", value_type="string"),
            Condition(field="days_since_purchase", operator="lte", value=14, value_type="number"),
        ),
        evidence=(
            Evidence(
                source_id="notion_refund_sop.md",
                source_version="sha256:x",
                span_start=0,
                span_end=5,
                excerpt="rule",
            ),
        ),
    )
    return Bundle(company_id="acme", workflows=(wf,), policies=(pol,))


BUNDLE = _bundle()
BUNDLE_HASH = bundle_content_hash(BUNDLE)
ACTOR = Actor(type="agent", id="test_agent", api_key_id="key_1")


def _svc() -> tuple[DecisionService, InMemoryLedgerStore]:
    store = InMemoryLedgerStore()
    return DecisionService(store), store


def _decide(svc, key="k1", facts=None):
    return svc.decide(
        company_id="acme",
        workflow="refund",
        facts=facts or {"plan_type": "annual", "days_since_purchase": 9},
        actor=ACTOR,
        idempotency_key=key,
        bundle=BUNDLE,
        bundle_hash=BUNDLE_HASH,
    )


def test_decision_is_ledgered_before_return():
    svc, store = _svc()
    event, created = _decide(svc)
    assert created is True
    assert store.get("acme", event.event_id) is not None
    assert event.outcome["kind"] == "approve"
    assert event.bundle_hash == BUNDLE_HASH
    assert event.trace["outcome"]["policy_id"] == "refund.annual_14d"


def test_idempotency_returns_original():
    svc, _ = _svc()
    first, created1 = _decide(svc, key="same")
    second, created2 = _decide(svc, key="same", facts={"plan_type": "annual",
                                                       "days_since_purchase": 99})
    assert created1 is True and created2 is False
    assert second.event_id == first.event_id
    assert second.outcome == first.outcome  # original preserved, not re-evaluated


def test_hash_chain_links_and_verifies():
    svc, store = _svc()
    e1, _ = _decide(svc, key="a")
    e2, _ = _decide(svc, key="b")
    e3, _ = _decide(svc, key="c")
    assert e1.prev_event_hash is None
    assert e2.prev_event_hash == e1.event_hash
    assert e3.prev_event_hash == e2.event_hash
    assert store.verify_chain("acme") is True


def test_tampering_detected():
    svc, store = _svc()
    _decide(svc, key="a")
    _decide(svc, key="b")
    stream = store._events["acme"]  # test-only reach-in
    tampered = stream[0].model_copy(update={"outcome": {"kind": "deny"}})
    stream[0] = tampered
    assert store.verify_chain("acme") is False


def test_unsealed_event_rejected():
    _, store = _svc()
    svc = DecisionService(store)
    event, _ = _decide(svc, key="a")
    unsealed = event.model_copy(update={"event_hash": "", "idempotency_key": "z"})
    try:
        store.append(unsealed)
        assert False, "unsealed event must be rejected"
    except ValueError:
        pass


def test_ledger_failure_aborts_decision_no_fallback():
    class DeadStore(InMemoryLedgerStore):
        def append(self, event):  # noqa: ANN001
            raise ConnectionError("db down")

    svc = DecisionService(DeadStore())
    try:
        _decide(svc)
        assert False, "ledger failure must abort the decision"
    except LedgerUnavailableError:
        pass


def test_adjudication_links_to_original():
    svc, store = _svc()
    original, _ = _decide(svc, key="esc",
                          facts={"days_since_purchase": 9})  # missing plan_type -> escalate
    assert original.outcome["kind"] == "escalate"
    adj, created = svc.record_adjudication(
        company_id="acme",
        original_event=original,
        actor=Actor(type="human", id="jane"),
        chosen_action="approve_full_refund",
        outcome_kind="approve",
        rationale="Verified annual plan in billing system.",
        idempotency_key="esc-adj",
    )
    assert created is True
    assert adj.linked_event_id == original.event_id
    assert adj.outcome["adjudicated"] is True
    assert store.verify_chain("acme") is True


def test_adjudication_requires_rationale():
    svc, _ = _svc()
    original, _ = _decide(svc, key="e2", facts={"days_since_purchase": 9})
    try:
        svc.record_adjudication(
            company_id="acme",
            original_event=original,
            actor=Actor(type="human", id="jane"),
            chosen_action="approve_full_refund",
            outcome_kind="approve",
            rationale="   ",
            idempotency_key="e2-adj",
        )
        assert False, "empty rationale must be rejected"
    except ValueError:
        pass


def test_list_filters_and_orders_newest_first():
    svc, store = _svc()
    _decide(svc, key="a")
    _decide(svc, key="b", facts={"days_since_purchase": 9})  # escalate
    rows = store.list("acme")
    assert len(rows) == 2 and rows[0].idempotency_key == "b"
    only_esc = store.list("acme", outcome_kind="escalate")
    assert len(only_esc) == 1 and only_esc[0].idempotency_key == "b"


def test_tenant_isolation():
    svc, store = _svc()
    _decide(svc, key="a")
    assert store.list("other-co") == []
    assert store.chain_head("other-co") is None


def test_chain_conflict_retried_transparently():
    """A concurrent writer wins the race once; the losing seal must be
    re-sealed against the new head and retried, not surfaced to the caller."""
    store = InMemoryLedgerStore()
    real_append = store.append
    calls = {"n": 0}

    def flaky_append(event):
        calls["n"] += 1
        if calls["n"] == 1:
            raise ChainConflict("simulated race: another writer won the head")
        return real_append(event)

    store.append = flaky_append
    svc = DecisionService(store)
    event, created = _decide(svc, key="a")
    assert created is True
    assert calls["n"] == 2
    assert store.verify_chain("acme") is True


def test_chain_conflict_exhausted_raises_ledger_unavailable_no_partial_write():
    store = InMemoryLedgerStore()

    def always_conflict(event):
        raise ChainConflict("simulated permanent contention")

    store.append = always_conflict
    svc = DecisionService(store)
    try:
        _decide(svc, key="a")
        assert False, "exhausted retries must abort the decision"
    except LedgerUnavailableError:
        pass
    assert store.list("acme") == []


def test_concurrent_decisions_same_tenant_never_corrupt_the_chain():
    """Regression test for a real race found under stress testing: sealing
    (which reads chain_head) happened outside the store's per-tenant lock,
    so concurrent decide() calls for the same company could both seal
    against the same head. One must retry, none may be lost or duplicated,
    and the chain must verify afterward."""
    svc, store = _svc()
    n = 12
    errors = []

    def worker(i):
        try:
            _decide(svc, key=f"conc-{i}", facts={"plan_type": "annual", "days_since_purchase": i})
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == [], f"unexpected failures under concurrency: {errors}"
    assert len(store.list("acme")) == n
    assert store.verify_chain("acme") is True


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
