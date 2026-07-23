# 07 · Technical Architecture & Build Plan

## Stack decision (measured against the brief's menu)

The brief lists a maximal toolbox (Framer Motion, GSAP, R3F, Lenis, MDX, shadcn). A senior engineer's job is to pick the smallest stack that hits every goal; each addition is justified or refused on record.

| Candidate | Verdict | Reason |
|---|---|---|
| **Next.js 16 App Router** | ✅ use | already the project framework; landing = server components |
| **React 19 + TypeScript 5** | ✅ use | project standard |
| **Tailwind v4** | ✅ use | inherits the whole token system in `globals.css`; zero new config |
| **Server Components (default) + tiny client islands** | ✅ use | landing SSRs; only 3 leaves are `"use client"` (reveal hook, counter, strip pause) |
| `next/font` Geist | ✅ use | already wired; self-hosted, swap, preloaded |
| `next/og` | ✅ use | edge OG image, zero asset pipeline |
| shadcn/ui | ❌ refuse | would import a foreign component idiom into a committed design system (impeccable: "a stock component inside a committed form is a lapse"). Kernl's own `ui/` primitives are the vocabulary. |
| Framer Motion | ❌ refuse | ~35KB for what CSS transitions + IO classes do identically here; hurts the 100-perf target (doc 05 rationale) |
| GSAP | ❌ refuse | no pinning/scrubbed timelines needed; nothing to justify it |
| Lenis (smooth scroll) | ❌ refuse | input lag + a11y cost for zero communicative gain on a narrative page |
| React Three Fiber / WebGL | ❌ refuse | a ledger is not clarified by 3D; violates perf budget |
| MDX | ❌ refuse | content is finite and design-coupled; JSX sections are clearer and lighter |
| Motion primitive: CSS `animation-timeline: scroll()` + IntersectionObserver | ✅ use | native scroll-driven spine; ~60 lines of JS total for all motion |

**Net:** the landing adds **~0 new dependencies** and **<5KB client JS**. This is the strongest possible position for Lighthouse 100 and for a governance brand whose whole thesis is "no unnecessary machinery."

## File structure

```
frontend/src/
  app/
    (marketing)/                 ← new route group, its OWN minimal layout (no auth/toast providers)
      layout.tsx                 ← marketing shell: metadata base, JSON-LD, no client providers
      page.tsx                   ← the landing (server component; composes sections)
    opengraph-image.tsx          ← next/og 1200×630
    twitter-image.tsx            ← reuse OG
    sitemap.ts                   ← /, /login
    robots.ts                    ← allow /, disallow console routes
    page.tsx                     ← EXISTING root redirect → change to render landing OR redirect?
  components/landing/
    LandingNav.tsx  Hero.tsx  LedgerStrip.tsx  Spine.tsx  SectionShell.tsx
    FactRows.tsx  FailureRows.tsx  FlowDiagram.tsx  PolicyCard.tsx  Terminal.tsx
    ReplayArtifact.tsx  ChainVisual.tsx  SpecRows.tsx  ProgramPanel.tsx
    Faq.tsx  CloseCta.tsx  LandingFooter.tsx
    useReveal.ts               ← shared IntersectionObserver hook (client)
    CountUp.tsx                ← client counter island
  app/globals.css              ← append landing keyframes + display-land steps
frontend/DESIGN.md             ← append landing display ramp rows
```

**Routing decision:** the existing `app/page.tsx` redirects `/` → `/login` or `/evaluate`. The landing must own `/` for SEO. Resolution: **`/` becomes the landing** (public marketing home); authenticated users are NOT force-redirected away from it (they use nav "Sign in" / their bookmark). The console keeps its own routes. The old redirect logic is removed from `/`; `(console)/layout.tsx` already guards auth. A route group `(marketing)` gives the landing a provider-free layout (perf) while keeping `/` as its path.

**Providers caveat:** root `app/layout.tsx` currently wraps everything in Auth+Toast providers. The landing doesn't need them. We keep the root layout minimal (html/body/fonts) and move Auth/Toast providers down into `(console)` and `/login` layouts, so the marketing route ships zero provider JS. This is a net a11y/perf win and doesn't change console behavior (those routes get the providers via their own group layout). Verified against Next 16 layout nesting before implementing.

## Build order (dependency-aware)

1. **Tokens & ramp** — append `display-land-*` + landing keyframes to `globals.css`; document rows in `DESIGN.md` (satisfies impeccable "DESIGN.md before first build edit").
2. **Layout & routing** — `(marketing)/layout.tsx`, move providers to console/login layouts, repoint `/`.
3. **Primitives** — `useReveal`, `SectionShell`, `Spine` (structure the page can hang on).
4. **Hero + LedgerStrip** — the thesis viewport first (impeccable: "first viewport is a thesis").
5. **Narrative sections 2→12** in story order, each with its authored artifact.
6. **SEO/OG/sitemap/robots + JSON-LD**.
7. **Verify loop:** `tsc` → `eslint` → `next build` → Playwright screenshots @1440/768/375 → read pixels → fix → repeat.
8. **Quality gates:** taste-skill pre-flight checklist + impeccable detector; `npx lighthouse` recommendation noted (CLI not installed here).

## Risks & mitigations

| Risk | Mitigation |
|---|---|
| Moving providers breaks console auth | Test `/login` + one console route after the move; keep providers identical, only relocate |
| `animation-timeline: scroll()` unsupported in some engines | Progressive enhancement: spine defaults to full/static; scroll-fill is the enhancement; IO handles node activation universally |
| Landing display step flagged by design hook | Documented in DESIGN.md ramp = hook-valid (the hook reads the documented ramp) |
| Next 16 API drift (AGENTS.md warning) | Read `node_modules/next/dist/docs` for metadata/OG/route-group APIs before writing them |
| Perf regression from providers-in-root | The provider relocation is itself the mitigation; measure build output |

## Definition of done

- Builds clean (tsc 0, eslint 0, next build success), all routes generate.
- Renders correctly at 1440/768/375 verified on real screenshots.
- One `<h1>`, ordered h2s, JSON-LD validates shape, sitemap/robots present.
- Reduced-motion branch verified; keyboard path walks the page; contrast AA.
- Taste-skill pre-flight: zero em-dashes, one accent system, one type ramp, CTAs single-line, no fabricated logos/claims, one theme.
- impeccable detector: zero real findings (defensible false-positives documented).
- The one-viewport memory test passes: a visitor who left after the hero could tell you "it's the system of record for AI decisions."
