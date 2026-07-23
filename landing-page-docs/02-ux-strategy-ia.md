# 02 · UX Strategy, Information Architecture & Wireframes

## Direction contract (the recorded decision, per impeccable new-work §5)

**THESIS:** The page is itself a ledger: scroll is time, sections are entries, and the story of the category is told as a chain of recorded facts. It refuses the category default (dark AI-infra page, glowing gradient, floating product screenshot).
**OWN-WORLD:** Kernl's established system (frontend/DESIGN.md): ink `#171717`-family on near-white paper, Geist Sans display with negative tracking, Geist Mono as the semantic voice of data (hashes, policy IDs, facts), hairline rules, the mesh-gradient aurora spent once at the hero. New landing-scale display steps added to the documented ramp. With all copy removed, the hairline ledger spine + mono entry rows + ink-on-paper restraint remain recognizable.
**STORY:** A VP of Support (or CFO, or CTO) arrives mid-decision about AI agents. Within one viewport they understand: decisions need a system of record, this is it. By the end they believe determinism + replay + an append-only ledger is the obvious shape of the answer, and they email us to become a design partner.
**FIRST VIEWPORT:** Bottom-weighted hero. Top 60%: quiet air with a faint aurora wash and the category eyebrow. Bottom 40%: H1 "Every decision, on the record." (2 lines max), 20-word sub, two CTAs left-aligned, and beneath them the page's live detail: a mono ledger strip where entries append and seal. The spine begins under the hero and runs the rest of the page.
**FORM:** Ledger-spine narrative page; ranked #1 of the derived structures (below). Brief-pinned narrative arc; no concept roll needed (user's brief pins story, positioning, CTAs, audience).

### Structures considered (derivation, ranked)
1. **Ledger-spine narrative** (chosen): a continuous left-rail hairline that fills with scroll; sections attach as entries. Product metaphor = page structure. ✅
2. Split manifesto (sticky left thesis, scrolling right proof) — strong but worse on mobile and weaker storytelling inevitability.
3. Terminal-first (whole page as one session transcript) — high technical charisma, alienates the VP/CFO half of the audience.
4. Vertical chapters with full-bleed alternating tints — generic pacing, no product identity.
5. Single-screen interactive demo with deep-dive anchors — demo-first buries the category story; wrong for a first-touch page.

## Information architecture / page flow (12 sections mapped to the user's arc)

| # | Section | Arc stage | One idea | Height target |
|---|---|---|---|---|
| 0 | Nav | — | Kernl + anchors + Sign in + CTA | 64px sticky |
| 1 | Hero | Introduction | Every decision, on the record | 100dvh |
| 2 | The $4,000 question | Problem + Industry shift | Agents act; nobody can prove authorization | ~90vh |
| 3 | Testimony, not evidence | Why current solutions fail | Self-attestation, prompts, lineage-less logs | ~80vh |
| 4 | The system of record | Introducing Kernl | Policy=code, decisions=entries, changes=replays (+flow diagram) | ~90vh |
| 5 | Three primitives | How Kernl works | Write policy · decide deterministically · record forever | ~110vh |
| 6 | Same answer, every time | Why determinism matters | Zero LLM on the decision path (terminal proof) | ~85vh |
| 7 | Ship policy like code | Replay | Diff → blast radius → acknowledge (replay artifact) | ~85vh |
| 8 | The chain | Decision Ledger | Append-only, hash-chained, signed (chain visual) | ~90vh |
| 9 | Built like infrastructure | Enterprise readiness | Six true engineering facts | ~70vh |
| 10 | The program | Design partner program | 5 partners · 90 days · zero workflow change | ~85vh |
| 11 | Questions | Objection handling + AEO | 4 real FAQs as disclosure rows | ~60vh |
| 12 | Close + footer | CTA | "The ledger starts when you do." | ~80vh |

Total ≈ 9,500–11,000px at 1440 — Ship-class pacing, one idea per thought.

## Hierarchies

- **Content:** claim → proof → implication, in that order, every section. Body copy ≤ 25 words per block.
- **Visual:** display headline (48–88px) → product artifact (diagram/terminal/rows) → body (16px, 65ch) → mono captions (12–13px). Nothing competes with the artifact.
- **Interaction:** scroll (primary) → row hover states (dim/activate) → FAQ disclosure → CTA. No hijacking, no horizontal scroll, native scrollbar untouched.
- **Animation:** spine fill (continuous, scroll-driven) > hero ledger strip (live detail) > section artifacts (one entrance each, varied) > reveals (minimal fade-rise). Full inventory in doc 05.

## Conversion flow

Primary CTA **Become a design partner** appears: nav (persistent), hero, program section, close. Secondary **Request a demo**: hero + close. Both are `mailto:` with prefilled subjects (a solo founder optimizing for conversations, per the GTM playbooks; no forms, no waitlist). Tertiary quiet path: "Sign in" (console) in nav + footer for existing/technical visitors. Friction plan: the program section pre-answers the four objections (risk, effort, security, price) inline before the final ask; FAQ catches the rest.

## Mobile strategy (375–767px)

Spine hidden (content is the spine on mobile). Hero: 88→40px display step, strip condenses to 2 entries. Flow diagram rotates vertical. All rows stack; hover states become default-visible (no hover-only meaning). Touch targets ≥44px. Nav collapses to wordmark + CTA (anchors dropped; the page is one story, scrolling IS navigation).

## Analytics strategy

Phase 1 (now): zero third-party scripts (performance + trust posture). Measure via CTA `mailto:` subject lines as channel tags + "how did you find us" on every call (per Founder OS). Phase 2 (post-partner): one privacy-light script (Plausible-class) gated behind consent, events: cta_click(hero|program|close|nav), faq_open, scroll-depth 25/50/75/100.

## Wireframes (1440 desktop, compressed)

```
┌────────────────────────────────────────────────────────────┐
│ Kernl        How it works  Replay  Ledger  Program   Sign in  [Partner]│ 64
├────────────────────────────────────────────────────────────┤
│                                                            │
│              (air + faint aurora wash)                     │
│  THE DECISION LEDGER FOR ENTERPRISE AI                     │
│  Every decision,                                           │
│  on the record.                                            │ 100dvh
│  Kernl turns operating policy into deterministic code...   │
│  [Become a design partner]  [Request a demo]               │
│  ─ ledger strip ───────────────────────────────────────    │
│  #4821 refund.annual_14d  approve  a3f2…9c  ● sealed       │
├─┬──────────────────────────────────────────────────────────┤
│ ○ spine   An AI agent just refunded $4,000.                │
│ │         Which policy authorized it?                      │
│ │         body ....                                        │
│ │         AGENTS ACT      ──────────────── fact            │
│ │         ADOPTION        ──────────────── fact            │
│ │         ENFORCEMENT     ──────────────── fact            │
├─┼──────────────────────────────────────────────────────────┤
│ ○         Logs tell you what happened. Not what was        │
│ │         allowed.                                         │
│ │         ▍Vendor self-attestation ......... (row, dim)    │
│ │         ▍Prompts as policy ............... (row)         │
│ │         ▍Logs without lineage ............ (row)         │
├─┼──────────────────────────────────────────────────────────┤
│ ○         Kernl is the system of record for decisions.     │
│ │         [FACTS]→[POLICY BUNDLE]→[DECISION]→[LEDGER]      │
│ │              (SVG flow, pulse traveling)                 │
├─┼───── ... sections 5–11 attach to the spine likewise ... ─┤
│ ●         The ledger starts when you do.                   │
│           [Become a design partner] [Request a demo]       │
│ footer:  Kernl · The decision ledger for enterprise AI     │
└────────────────────────────────────────────────────────────┘
```
