# 001 — Animate `<details>` height on expand (Policies + Trace)

**Commit stamped:** 39db919
**Severity:** LOW (polish) · **Category:** Missed opportunity (§8)
**Status:** DEFERRED — carries cross-browser implementation risk; feel-check required on a real device before shipping. Not implemented in the motion pass because the payoff is low and a half-working height animation is worse than the current clean snap.

## Finding

`PolicyCard.tsx:8` and `TraceView.tsx:118` use native `<details>`. The disclosure chevron rotates smoothly (`transition-transform group-open:rotate-90`), but the content **height snaps** open — no height transition. On expand, the surrounding layout jumps.

## Why it's deferred, not done

Native `<details>` toggles `display` on its content, which defeats a plain `height`/`max-height` transition. The reliable options each have a caveat:

1. **`grid-template-rows: 0fr → 1fr`** on an always-rendered inner wrapper. Works, but requires restructuring the details body into `<div class="grid">` `<div class="overflow-hidden">…`, and interacts awkwardly with the native open/close (content must stay in the DOM). Medium implementation risk across two components.
2. **`interpolate-size: allow-keywords` + `transition: height`** (modern CSS). Clean, but Baseline-newly-available — needs a graceful fallback for older Safari/Firefox.

Both need a **real-device feel-check** (frame-by-frame on expand/collapse, and verify no layout thrash in the long Policies list where many rows expand). That judgment can't be made from code alone.

## Target values (when implemented)

- Duration: `var(--duration-panel)` (200ms) · Easing: `var(--ease-out)`
- Reduced-motion: opacity-only, no height movement.
- Approach 1 skeleton:
  ```css
  .details-body { display: grid; grid-template-rows: 0fr; transition: grid-template-rows var(--duration-panel) var(--ease-out); }
  details[open] .details-body { grid-template-rows: 1fr; }
  .details-body > div { overflow: hidden; }
  @media (prefers-reduced-motion: reduce) { .details-body { transition: none; } }
  ```

## Verification

- Expand/collapse a Policy card and a Trace policy row; the body should ease open, not snap.
- Slow-motion (DevTools 4× slowdown) — no double-paint, no sibling jump.
- Long Policies list: expand 3 rows rapidly — no janky reflow.
- Reduced-motion on: content still appears, just without the height slide.
