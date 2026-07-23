# 06 · SEO / AEO, Accessibility & Performance Plans

## SEO + Answer Engine Optimization

**Reality note:** the app currently deploys on a `*.vercel.app` domain; canonical URLs are configured via `metadataBase` from `NEXT_PUBLIC_SITE_URL` so the real domain drops in with one env var.

- **Metadata:** full `Metadata` export (title, description, canonical, robots, OG, Twitter `summary_large_image`), `metadataBase` env-driven.
- **OG image:** `opengraph-image.tsx` via `next/og` (edge-generated, zero asset pipeline).
- **Structured data (JSON-LD, one script, sanitized):** `Organization` + `WebSite` + `SoftwareApplication` (category: BusinessApplication) + `FAQPage` mirroring the four rendered FAQs exactly (AEO rule: schema never claims unrendered content).
- **Semantic structure:** single `<h1>`, ordered `<h2>` per section, `<main>/<section>/<nav>/<footer>` landmarks, FAQ as `<details>` (crawlable text, no JS gate).
- **AEO/LLM-friendliness:** the category definition appears verbatim near the top ("Kernl is the system of record for decisions...") in plain HTML; terminology repeated consistently (decision ledger, replay, append-only) so answer engines quote it; FAQ targets the literal queries buyers type ("what is a decision ledger", "AI agent audit trail").
- **Files:** `sitemap.ts` (/, /login), `robots.ts` (allow all; disallow console routes: /evaluate /ledger /escalations /policies /replays /sources /settings /onboarding /decisions).
- **Internal links:** nav anchors + footer Sign in; console deliberately noindexed (product UI, no SEO value, avoids thin-content dilution).
- **Headings = answers:** each H2 is a claim an engine can lift as a snippet.

## Accessibility (WCAG 2.2 AA)

- Landmarks + skip link ("Skip to content", first focusable).
- Contrast: ink/body/mute all AA on canvas (mute fixed to ≥4.5:1 earlier); aurora is `aria-hidden` decoration behind AA-checked text; chips carry text labels, never color-only.
- Keyboard: all interactive = native `<a>/<button>/<details>`; global `:focus-visible` ring (existing system); logical tab order; no focus traps; nav anchors scroll with `scroll-margin-top`.
- Reduced motion: every animation has a `prefers-reduced-motion` branch (doc 05 table); meaning never lives in motion alone (e.g., counters render final values).
- Semantics: ledger strip/terminal/artifacts get `aria-label` summaries; decorative SVG `aria-hidden` + `role="presentation"`; FAQ uses native disclosure semantics for free.
- Touch targets ≥44px on mobile; text scales with rem; no viewport zoom lock.

## Performance (targets: 100/100/100/100)

- **JS budget:** landing route is server components + 3 tiny client islands (IO reveal hook, counter, strip pause) ≈ <5KB added JS. No animation libraries (doc 05 rationale).
- **Fonts:** existing `next/font` Geist Sans/Mono (self-hosted, swap, preloaded by Next automatically). No new fonts.
- **Images: none** (all visuals are HTML/SVG; OG image is route-generated). LCP element = the H1 text: server-rendered, zero-request. Expected LCP well under 1s on 4G.
- **CLS ≈ 0:** no async layout-shifting content; strip/terminal reserve fixed heights.
- **CSS:** Tailwind v4 tree-shaken; landing keyframes add ~2KB.
- **Providers caveat (measured decision):** root layout wraps children in Auth/Toast client providers; the landing still SSRs and the providers are ~1KB. Accepted for now; extracting providers to (console)/login layouts is a follow-up micro-optimization if Lighthouse TBT ever flags it.
- **Verification honesty:** Lighthouse CLI isn't installed in this environment; verification = build-size output + methodology above + a follow-up `npx lighthouse` run recommended in the build plan. No fabricated scores will be claimed.
