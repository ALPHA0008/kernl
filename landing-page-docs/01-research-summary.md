# 01 · Research Summary

**Date:** 2026-07-24. Method: live Playwright inspection (computed styles, measurements, screenshots at 4 scroll depths) of the two requested references, plus knowledge synthesis of the wider premium set. Live-measured facts are marked **[measured]**; the rest is established design knowledge of stable, well-documented sites.

## Live findings: vercel.com/ship/sf and /ship/sydney [measured 2026-07-24]

| Property | Value | Lesson |
|---|---|---|
| Canvas | Pure black `rgb(0,0,0)`, text `rgb(237,237,237)` (off-white, never pure) | Two colors carry the whole identity. Restraint reads as confidence. |
| H1 | 96px, weight 500, tracking −5.76px (−6%), line-height 1.0, custom pixel font (GeistPixelCircle) | One display face, one enormous scale, hard negative tracking. Identity lives in typography, not decoration. |
| Chrome voice | Mono-caps everywhere: nav (SPEAKERS · SCHEDULE · FAQ), metadata (PALACE OF FINE ARTS), live countdown (83D.17H.25M.13S) | A single "technical voice" unifies every non-display string. Kernl's console already speaks this language. |
| Hero composition | **Bottom-anchored** H1 + metadata; pixel space-invader formation descends through the empty upper 2/3 | The empty space above the headline is the drama. Bottom-anchoring is a distinctive alternative to the centered-hero cliché. |
| CTA | White block, **0px radius**, huge padding (0 112px), pixel-jagged border matching the display font | The button carries the identity system into interaction. Sharp corners = event identity (product pages use 6px). |
| Sections | 800–1,400px each, ~7,300–9,000px total; one idea per section | A section is a full thought with air, not a strip. |
| Speakers list | Hairline rows; active row lights to full white while others dim to ~35%; portrait swaps at right | **Rows as interface.** List + selection state + one large visual. The single most transferable pattern for Kernl (ledger rows ARE the product). |
| Motion | Only 10 animated elements, 74 with transitions [measured] | Premium ≠ animated. Motion is scarce, so each moment lands. |
| Live element | Countdown timer ticking in mono | One continuously-alive detail makes the whole page feel operating, not printed. |

## Synthesis of the wider set (established knowledge)

- **Stripe:** the gradient is earned by everything else being ruthlessly plain; diagrams are real product architecture, not clip-art; body copy is short declarative sentences. Lesson: one atmospheric moment per page, spend it at the hero.
- **Linear:** dark, type-led, sections breathe 160–240px; motion = restrained fade-rise with strong ease-out; product shown as truthful UI fragments, not full screenshots. Lesson: fragments > screenshots.
- **Anthropic:** warm light canvas, serif-free, research-paper calm; trust through tone, not badges. Lesson: light can be the premium choice when the subject is trust.
- **Apple:** one idea per viewport; scroll pace controlled by section height; captions do the explaining. Lesson: pacing is a design material.
- **Raycast/Warp/Clerk/Resend:** mono as semantic voice for technical products; keyboard-dense UI shown as proof; small true claims beat large vague ones.
- **Notion/Figma:** friendly ≠ premium for infrastructure; rejected as direction inputs for Kernl (wrong register for an audit product).
- **Perplexity/Cursor/Arc:** category-defining pages lead with the *mechanism demonstrated*, not the benefit stated. Arc: personality through motion; rejected for Kernl (audit products must feel inevitable, not playful).

## Why premium feels premium (the transferable physics)

1. **Subtraction:** 1–2 colors, 1 display size jump, 1 atmospheric moment. Everything else is structure.
2. **A single identity anchor** repeated everywhere (Ship: pixel font; Stripe: gradient; Kernl: **the ledger row**).
3. **Type does the work:** enormous scale contrast (96px display vs 16px body ≈ 6×), negative tracking on display only, mono reserved for data.
4. **One authored motion moment** plus a live detail; everything else is a calm reveal.
5. **Proof over claim:** the product's real artifacts (diagrams, terminal output, report formats) beat marketing illustrations.
6. **Sections are thoughts:** ~1 viewport each, one idea, generous exit whitespace before the next thought begins.
7. **The page ends with an anchor**, not a fade-out: a full-scale closing statement + the CTA repeated.

## What Kernl will NOT copy

The pixel font, the black canvas, invaders motif, countdown, event-page FAQ chrome. Kernl synthesizes the *physics* (restraint, rows-as-interface, mono chrome, bottom-weighted hero, scarce motion) into its own committed world: **ink on paper, the ledger as the page's spine, decisions as the recurring visual grammar.**
