# PRODUCT.md — Kernl

Product truth for design work. Sources: `docs/Product_summit.md` (vision), `docs/Kernel_arc.md` (build plan), `docs/MARKET_VALIDATION.md`, `docs/FOUNDER_PLAYBOOK.md`, `docs/DESIGN_PARTNER_PLAYBOOK.md`. Visual decisions live in `frontend/DESIGN.md`, never here.

## What Kernl is

Kernl is the decision ledger for enterprise AI: infrastructure that turns an organization's operating policy (refunds, credits, discounts, and eventually every consequential decision) into deterministic, versioned, evidence-cited code, executes it for humans and AI agents, and records every decision as a signed entry in an append-only, hash-chained ledger. Policy changes are replay-tested against decision history before they ship. Category language: **the Decision Ledger** (product), **the audit layer for the AI agent economy** (position), **Institutional Computing** (long-run discipline). Positioning is NOT "AI governance."

## The mechanism (unique, true, demonstrable)

1. **Policy as code:** typed conditions, priorities, override edges; every policy carries a byte-verified citation to its source document ("no uncited norm").
2. **Deterministic evaluation:** zero LLM calls on the decision path. Same facts + same bundle = same answer, every time. Proven by property tests and a differential-tested Rust port.
3. **The ledger:** every decision is a write-ahead, append-only, hash-chained, Ed25519-signed event. Append-only is enforced at the database. Adjudications (human rulings on escalations) link back and become precedent.
4. **Replay:** any policy change runs against golden cases and history first; publishing is blocked until the blast radius is acknowledged. "CI for your refund policy."
5. **Escalation as a first-class outcome:** missing facts or conflicts never guess; they route to humans, and resolutions harden into precedent.

## Who it is for

Primary buyer: VP Support / Head of CX / VP RevOps at 200–2,000-person B2B companies, especially those deploying AI support agents (Decagon/Fin/Sierra class). Economic buyer for the audit story: CFO/finance. Technical audience: CTOs, platform and AI teams. Secondary: investors, engineers, press.

## Why now (true, sourced claims)

- AI agents already execute money-touching decisions (refunds) autonomously at scale.
- Gartner: 40% of enterprise apps will embed task-specific agents by end of 2026, from under 5% in 2025.
- EU AI Act high-risk obligations became enforceable August 2, 2026 (decision traceability, log retention). Refund decisions are not Annex III high-risk; the pull is adjacent, not direct — never overclaim.
- Agent vendors attest to their own actions; no neutral system of record exists.

## Commercial stage (truth for any public surface)

Pre-seed. Product live in production. Zero named customers yet; taking **5 design partners** (90-day shadow-mode program: read-only, zero workflow change, white-glove policy encoding, free Leakage Report). Primary CTA everywhere: **Become a design partner**. Secondary: **Request a demo**. No waitlists. Must never claim: SOC 2 certification (in progress only), named customers, revenue, "first/only" superlatives.

## Voice

Rigorous, calm, specific, honest. Sentence-case headlines, period-terminated. Mono voice is semantic: hashes, policy IDs, facts, measurements — never decoration. The brand never hypes; it proves. Banned copy: "revolutionize", "next-generation", "powerful platform", "unleash", em-dashes in visible copy.
