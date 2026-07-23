# 04 · Visual Direction & Design System (landing surface)

The landing inherits `frontend/DESIGN.md` (the committed Kernl world) and extends it with landing-scale steps. Nothing here contradicts the incumbent system; the console and the landing are one brand seen at two distances.

## Visual direction (one paragraph)

Ink on paper, at poster scale. The page reads like the first page of an institution's ledger: enormous quiet Geist display in near-black on near-white, one atmospheric aurora wash at the top (the existing brand gradient, heavily restrained), and then the product's own voice takes over: mono entries, hairline rules, hash chips, a spine that fills as you read. Color appears only where it means something (approve green, escalate amber, in chip-sized doses). Everything else is structure, air, and type.

## Color (tokens from globals.css, no new hues)

- Canvas `--color-canvas` #fff / soft #fcfcfc · Ink `--color-ink` (oklch 0.20) · Body (0.42) · Mute (0.55, AA-fixed)
- Hairline (0.94) / strong (0.71)
- Semantic chips only: `--color-approve` (green), `--color-escalate` (amber), `--color-route` (violet). Never decorative.
- Aurora: the login page's conic mesh (`#007cf0 → #00dfd8 → #7928ca → #ff0080 → #ff4d4d → #f9cb28`) at ~10-14% opacity, blur-3xl, hero only, `aria-hidden`. This is the single permitted atmospheric moment (research doc: "one atmospheric moment per page").
- Strategy: **Restrained** (neutrals + semantic accents), per impeccable §4; correct for an Operate-adjacent Persuade surface about trust.

## Typography (documented ramp + landing extension)

- Display: Geist Sans 600, tracking −0.03em to −0.04em (craft-floor cap), sentence case, period-terminated.
  - `display-land-xl` 88px/0.98 (hero, close) → 56/1.02 @768 → 40/1.05 @375
  - `display-land-lg` 56px/1.05 (section H2) → 40 → 30
  - (added to DESIGN.md ramp table as part of this build)
- Body: 16px/1.6, max 65ch, color body. Lead-body 18px where a section has one paragraph only.
- Mono (Geist Mono): 13px data rows, 12px captions, 11px chips (documented caption steps). Uppercase+tracked ONLY for the ≤3 eyebrows and mono labels.
- Scale contrast target ≈ 5.5× (88/16), Ship-class.

## Spacing & layout

- Container: max-w-[1200px], px-6/8/10 responsive. Content column beside spine: pl-10 at lg.
- Section rhythm: py-28 (112px) desktop / py-16 mobile; hero 100dvh; more space above headings than below (craft floor).
- Grid: single column narrative; two-column only where meaning demands (program you-get/we-need, determinism text/terminal).
- Spine: 1px hairline at container-left (lg+ only), progress-filled ink; nodes 6px, activate per section.

## Elevation & shape

- Elevation declared once: the existing `--shadow-*` ladder. Artifacts (terminal, policy card, replay verdict) use shadow-2; no borders+shadow ghosts.
- Radius: existing system (6px controls, 8-12px surfaces). CTAs = existing Button idiom (6px). No pills except tiny chips.

## Component inventory (all new components under `components/landing/`)

| Component | Role |
|---|---|
| `LandingNav` | sticky, 64px, wordmark + anchors + Sign in + CTA; mobile: wordmark + CTA |
| `Hero` | bottom-weighted composition + aurora + `LedgerStrip` |
| `LedgerStrip` | the live detail: 3 mono entries appending/sealing on load, loops slowly |
| `Spine` | scroll-progress line + section nodes (lg+, aria-hidden) |
| `SectionShell` | rhythm wrapper: node registration + reveal-once |
| `FactRows` | mono-label fact list (problem section) |
| `FailureRows` | dim/activate rows (rows-as-interface pattern) |
| `FlowDiagram` | SVG FACTS→BUNDLE→DECISION→LEDGER w/ traveling pulse |
| `PolicyCard` (landing) | typed condition + citation chip artifact |
| `Terminal` | determinism proof block, types once on reveal |
| `ReplayArtifact` | diff + verdict counters (count-up once) |
| `ChainVisual` | 4 linked entries + verify stamp |
| `SpecRows` | infrastructure facts, 2-col grid of hairline rows |
| `ProgramPanel` | offer spec + honesty line + CTA |
| `Faq` | native `<details>` disclosure rows |
| `CloseCta` | display-scale close + CTAs |
| `LandingFooter` | minimal |

## Asset / illustration / photography / 3D plan

- **Photography: none.** The subject's world is documents, terminals, ledgers; people-photos would import stock-trust falseness.
- **Illustration: none hand-drawn.** All visuals are the product's own artifacts (real report formats, real terminal grammar, real chain semantics) rendered as designed HTML/SVG. This satisfies "prove, don't claim" and avoids fake-screenshot slop; data values are illustrative and labeled `sample`.
- **3D/WebGL: rejected.** Nothing about a ledger is clarified by 3D; cost violates the perf budget. (User brief permits Three.js "only if it improves understanding". It doesn't.)
- **Iconography: near-zero.** The system's existing minimal line icons only where semantics demand (none anticipated beyond chevrons/arrows). No icon-tile grids.
- **OG image:** generated at build via `next/og`: ink canvas, wordmark, H1, one ledger row. 1200×630.
