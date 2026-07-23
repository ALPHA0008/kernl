# 05 · Motion Blueprint

Philosophy (from research + craft floor): motion is scarce so each moment lands; **one authored moment**, one live detail, varied minimal reveals. Every animation answers "what does this communicate?" All motion uses the existing tokens (`--ease-out`, `--ease-in-out`, `--duration-*`) and respects `prefers-reduced-motion` (movement removed, meaning preserved).

## Library decision: no GSAP, no Lenis, no Framer Motion, no R3F

The brief lists candidate libraries; the correct engineering answer here is **CSS + SVG + ~60 lines of IntersectionObserver**, because:
1. Nothing on the page needs pinning, scrubbed timelines, or physics (GSAP's justifications).
2. Native scroll is the accessibility/perf baseline; smoothing (Lenis) adds jank risk, input lag, and a11y cost for zero communicative gain on a narrative page.
3. Framer Motion costs ~30-40kb for what CSS transitions + IO classes do identically here.
4. Hitting the 100-Lighthouse budget is trivially easier with zero animation JS on the main thread.
This is "motion claimed, motion shown" with the smallest possible machine. (Documented so a future contributor doesn't "upgrade" it.)

## Inventory

| # | Moment | Communicates | Mechanism | Spec | Reduced-motion |
|---|---|---|---|---|---|
| 1 | **Ledger spine fill** (authored moment) | scroll = time; the page is an append-only record | CSS `animation-timeline: scroll()` on a scaleY line; static-fallback for non-supporting engines; nodes activate via IO `.in-view` | linear w/ scroll; nodes 200ms `--ease-out` | line static full, nodes static filled |
| 2 | **Hero ledger strip** (live detail) | the product is alive; decisions seal continuously | CSS keyframes loop: entry rows fade-rise in sequence, seal chip stamps; ~9s cycle, pauses on `:hover` | entry 300ms `--ease-out`, stagger 900ms | strip static, all rows visible sealed |
| 3 | Hero load | composition assembles calmly | 3-element stagger (eyebrow→H1→sub/CTAs) fade-rise 12px | 400ms `--ease-out`, 80ms stagger | opacity-only 200ms |
| 4 | Flow diagram | facts travel through policy into the ledger | SVG path draw (dashoffset) on reveal + a 3px pulse dot traveling the path, loops 6s | draw 900ms `--ease-in-out` once | full path shown, no pulse |
| 5 | Terminal | determinism = repetition | 3 run lines type in once on reveal (CSS steps() width), then hash line stamps | 350ms/line, 200ms gaps | all lines visible |
| 6 | Replay counters | blast radius is measured, not guessed | count-up 0→1284 / 0→3 once on reveal (rAF, ~800ms, `--ease-out` curve) | 800ms | final values rendered |
| 7 | Chain visual | links are cryptographic, sequential | connecting strokes draw entry-to-entry, verify stamp scales 0.96→1 | 500ms/link sequential | fully drawn |
| 8 | Section reveals | pacing only | fade-rise 12px once per section via shared IO; **artifact sections skip this** (their own entrance is the reveal) so no identical-everywhere entrance | 350ms `--ease-out` | none |
| 9 | Rows hover (failures/facts) | rows are the interface | dim-others pattern: sibling rows to 45% ink, active to 100% | 150ms `--ease-out` colors | n/a (hover) |
| 10 | CTA/button states | existing Button idiom | inherited from design system | 150ms | inherited |

Explicitly rejected: parallax (communicates nothing here), cursor effects (banned by taste skill), scroll-hijack, page transitions (single page), animated typography beyond the terminal (gimmick risk), physics.

## Performance budget for motion

Compositor-only properties (transform/opacity) except the spine's scaleY (transform ✓) and terminal width steps (contained, small area, once). No `will-change` except the traveling pulse. Total added JS for motion: one IO hook + one counter ≈ <2KB. All loops ≤ 1 concurrent animating element outside the hero strip.
