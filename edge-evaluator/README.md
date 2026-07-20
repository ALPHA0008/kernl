# kernl-edge-evaluator

The Kernl reflexive evaluator as a stateless Rust binary — the first,
test-anchored incarnation of the arc's **edge-evaluator sidecar** (Part 11):

> because bundles are immutable content-addressed artifacts and evaluation is a
> pure function, the reflexive evaluator ships as a stateless sidecar/binary
> that runs inside the customer's infrastructure. Policy evaluates at the point
> of action in microseconds with zero Kernl-availability dependency.

## What it is (and is not)

This is an **outcome-exact port** of `backend/runtime/evaluator.py`. For the same
`(facts, bundle, workflow)` it produces the same decision — outcome kind, action,
policy id, escalation reason, sorted `missing_facts`/`conflict_between` — plus the
enforce-critical precedence facts (winner, applied rules, ties, dominance).

It is **not** the authority on its own. The Python evaluator remains the V1
reference. This crate is trusted only because a differential-test harness proves
it agrees with the reference on every input (see below). That mirrors the arc's
endgame (V6): a verified reference evaluator with *continuous differential
testing against the production Rust evaluator*. This crate is where that
production evaluator begins.

Scope today matches the V1 evaluator exactly: strict condition evaluation
(a condition on a missing fact is never a silent pass), winner selection
(overrides → specificity → priority, ties escalate), and the dominance rule
(an undeterminable policy with strictly higher priority than the winner blocks
the decision).

## Build

On Windows this crate uses the GNU host toolchain (pinned in
`rust-toolchain.toml`) because it bundles its own linker — no Visual C++ Build
Tools required. On Linux/macOS the default toolchain works unchanged.

```
cargo build --release
```

## Use

Reads one JSON request on stdin, writes one JSON decision on stdout:

```
echo '{"facts":{"plan_type":"annual","days_since_purchase":9},
       "bundle":{...},"workflow":"refund"}' | ./target/release/kernl-eval
```

Unknown workflow / invalid facts print `{"error":{...}}` and exit non-zero —
the same request-error-vs-decision distinction the Python `/v1` API makes.

## The proof: differential conformance

`backend/tests/test_rust_conformance.py` runs BOTH evaluators on the same inputs
and asserts identical outcomes:

- every golden case in both seed corpora (86 real authored cases), and
- Hypothesis-generated bundles + facts (adversarial shapes: ties, dominance,
  overrides, boundary comparisons).

Verified: 86/86 corpus cases and 1000 generated examples agree, zero divergence.
The harness **skips cleanly** if the binary isn't built — it never fakes a pass.
It runs in CI (the `rust-conformance` job) so the two evaluators can't silently
drift.
