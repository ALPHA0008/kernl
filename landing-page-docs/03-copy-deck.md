# 03 · Complete Copy Deck (final strings)

Rules enforced: sentence-case, period-terminated headlines (DESIGN.md voice). Zero em-dashes anywhere. Body blocks ≤ 25 words. Mono strings are semantic (data, IDs, hashes). Banned words absent (revolutionize, next-generation, powerful, unleash, seamless). Every claim true per PRODUCT.md; illustrative data labeled.

## Nav
- Wordmark: **Kernl**
- Anchors: `How it works` · `Replay` · `The ledger` · `Partner program`
- Quiet: `Sign in`
- CTA: `Become a design partner`

## 1 · Hero
- Eyebrow (mono-caps): `THE DECISION LEDGER FOR ENTERPRISE AI`
- H1: **Every decision, on the record.**
- Sub (20 words): Kernl turns operating policy into deterministic code. Every decision a human or AI agent makes is authorized, signed, and replayable.
- CTA primary: `Become a design partner` · CTA secondary: `Request a demo`
- Ledger strip (live detail, mono, illustrative):
  - `#4819  refund.annual_full_14d   approve   e5f2…b1  sealed`
  - `#4820  discount.startup_20      approve   77ac…04  sealed`
  - `#4821  refund.high_value        escalate  human review  → adjudicated`
  - Caption: `sample entries` (tiny, mono)

## 2 · The problem
- H2: **An AI agent just refunded $4,000. Which policy authorized it?**
- Body: For most companies the honest answer is nobody knows. Policy lives in macros, spreadsheets, and someone's memory. Agents act in milliseconds.
- Fact rows (mono label + sentence):
  - `AGENTS ACT` — AI agents already resolve most support conversations at leading companies. Refunds included.
  - `ADOPTION COMPOUNDS` — Gartner expects 40% of enterprise apps to embed task-specific agents by the end of 2026.
  - `THE LAW ARRIVED` — EU AI Act high-risk enforcement began August 2, 2026. Regulators now ask for decision trails, not intentions.

## 3 · Why current answers fail
- H2: **Logs tell you what happened. Not what was allowed.**
- Rows (title + body):
  1. **Vendor self-attestation.** Your agent platform grades its own homework. A trail signed by the party being audited is testimony, not evidence.
  2. **Prompts as policy.** A system prompt cannot be versioned, diffed, tested, or cited when finance asks why.
  3. **Logs without lineage.** A log line records an outcome. It cannot prove which rule, which version, which authority produced it.

## 4 · Introducing Kernl
- H2: **Kernl is the system of record for decisions.**
- Body: Policy becomes code: typed, versioned, cited to its source. Decisions become ledger entries: signed and append-only. Changes become replays: tested against history first.
- Diagram node labels (mono): `FACTS` → `POLICY BUNDLE` → `DECISION` → `LEDGER`
- Diagram sublabels: `typed input` · `versioned, cited` · `deterministic` · `signed, chained`

## 5 · How it works
- H2: **Three primitives. No magic.**
- Step 1 title: **Write policy as code.** Body: Typed conditions, priorities, and override rules. Every policy cites its source document, byte for byte. No citation, no publish.
  - Artifact: policy card. `refund.annual_full_14d` / `IF plan_type = annual AND days_since_purchase <= 14` / `THEN approve full_refund` / citation chip: `refund-policy.md · bytes 214–312 · verified`
- Step 2 title: **Decide deterministically.** Body: Same facts, same policy, same answer. Zero LLM calls on the decision path. Ambiguity escalates to a human instead of guessing.
  - Artifact: terminal (see section 6 block, shortened to one run + outcome line).
- Step 3 title: **Record it forever.** Body: Every decision becomes a signed, hash-chained entry in an append-only ledger. Change one byte and every hash after it breaks.
  - Artifact: 3 chained entries with prev→hash linkage.

## 6 · Determinism
- H2: **Same facts. Same policy. Same answer.**
- Body: Probabilistic systems are impressive and unaccountable. Kernl keeps the model where it belongs: proposing drafts and explaining outcomes. Never deciding.
- Terminal (mono, illustrative):
```
$ kernl evaluate refund --facts case_4821.json      × 3 runs
run 1  → approve · approve_full_refund · policy refund.annual_full_14d
run 2  → approve · approve_full_refund · policy refund.annual_full_14d
run 3  → approve · approve_full_refund · policy refund.annual_full_14d
outcome hash  9b12dcee…  identical · 3 of 3
```
- Kicker: The evaluator is differential-tested against an independent Rust implementation. Determinism here is not a promise. It is a test suite.

## 7 · Replay
- H2: **Ship policy like you ship code.**
- Body: Every change replays against your golden cases and decision history before it can publish. See which past decisions flip. Acknowledge the blast radius, or don't ship.
- Diff artifact (mono):
```
  refund.annual_full_14d
-   days_since_purchase <= 14
+   days_since_purchase <= 7
```
- Replay verdict artifact: `1,284 decisions replayed` · `3 flips` · `0 golden failures` · `publish unlocked on acknowledgment` · caption `sample replay`

## 8 · The ledger
- H2: **Append-only. Hash-chained. Signed.**
- Body: Append-only is enforced by the database, not by promise. Bundles are Ed25519-signed at publish. Anyone can verify the chain without trusting us. That is the point.
- Chain artifact rows (illustrative): four entries, each `#id · policy · outcome · prev ⟶ hash`, one an adjudication: `#4822 · adjudication · human ruling · links #4821`. Closing stamp: `chain verified`.

## 9 · Enterprise readiness
- Eyebrow (mono-caps): `INFRASTRUCTURE`
- H2: **Built like infrastructure, because it is.**
- Spec rows (term + one-liner, all true):
  - `Deterministic core` — zero LLM calls on the decision path.
  - `Append-only ledger` — enforced by a database trigger, not convention.
  - `Ed25519 signatures` — verify any bundle independently of Kernl.
  - `Replay-gated publishing` — no policy change ships untested.
  - `Evidence-cited policy` — every rule traces to its source document.
  - `API-first` — REST, tenant-isolated, role-scoped keys.

## 10 · Design partner program
- Eyebrow (mono-caps): `DESIGN PARTNER PROGRAM`
- H2: **Five partners. Ninety days. Zero workflow change.**
- Body: We shadow your existing refund and credit decisions, read-only. We encode your policies for you. You get the Leakage Report: what inconsistent decisions actually cost.
- Two-column spec:
  - **You get:** your policies encoded as cited, versioned code · the Leakage Report on your own history · a replay run on a real policy change · an audit-trail pack your finance team can hold.
  - **We need:** a read-only export from your help desk · one 45-minute call a week · honest feedback.
- Honesty line: Free for the ninety days. If the report doesn't find more than the year-one price, we'll tell you so ourselves.
- CTA: `Become a design partner`

## 11 · Questions
- H2: **Questions a careful buyer asks.**
- FAQ (rendered + JSON-LD):
  1. **Is Kernl another AI agent?** No. Kernl is the neutral layer that decides and records. Your agents, human or AI, ask Kernl what policy allows, then act. Kernl never executes anything.
  2. **Do we have to change our support workflow?** No. Design partnerships run in shadow mode: read-only ingestion of decisions you already make. Your team changes nothing while the ledger builds.
  3. **What does deterministic actually mean here?** Same facts plus same policy version always produce the same decision. No model on the decision path. Ambiguous cases escalate to humans instead of guessing.
  4. **Is our data safe with a young company?** Shadow mode is read-only. A data processing agreement comes standard, deletion on request, and every bundle is cryptographically verifiable without trusting us.

## 12 · Close
- Display: **The ledger starts when you do.**
- Sub: Every decision before Kernl is unprovable history. Every decision after is on the record.
- CTAs: `Become a design partner` · `Request a demo`

## Footer
- `Kernl` · The decision ledger for enterprise AI.
- Links: `Sign in` (console) · `hello@…` (email) 
- Legal line: `© 2026 Kernl`

## Metadata
- `<title>`: Kernl · The decision ledger for enterprise AI
- Description (155ch): Kernl turns operating policy into deterministic, versioned code. Every decision a human or AI agent makes: authorized, signed, replay-tested, on the record.
- OG title: Every decision, on the record. · OG description: same as meta.
