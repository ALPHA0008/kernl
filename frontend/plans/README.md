# Motion plans — Kernl Console

Produced by the `improve-animations` audit (commit 39db919). The audit found the
motion foundation **mostly already correct** (strong `--ease-out` on entrances,
`prefers-reduced-motion` honored, no `ease-in`/`transition: all`/`scale(0)`/
animated layout props). The high-leverage fixes below were **implemented in the
motion pass**; the remaining one is deferred with a full plan.

## Implemented in the motion pass (not tracked as plans)

| Finding | What shipped |
|---|---|
| Motion tokens missing | Added `--ease-out`/`--ease-in-out`/`--ease-drawer` + `--duration-*` to `globals.css`; `page-enter` now references them. |
| Tab underline teleports (5 surfaces) | `Tabs.tsx` rewritten to a single indicator that **slides** (`.tab-underline`, `left`/`width` transition, reduced-motion off, first-paint gate so it appears in place). |
| Dropdowns used a generic drop | TopBar menu + replay picker now use `.menu-enter` — `scale(0.96)→1` **from the trigger corner** (`--menu-origin`), 150ms `--ease-out`. |
| Toasts used `page-enter` | `.toast-enter` — rise+scale from the stack, 150ms `--ease-out`. |

## Open plans

| # | Plan | Severity | Status |
|---|---|---|---|
| 001 | [details-height-expansion](001-details-height-expansion.md) | LOW | DEFERRED — needs real-device feel-check; cross-browser risk |

## Execution order

001 is independent and optional. Implement only after a feel-check confirms the
`grid-rows` (or `interpolate-size`) approach is smooth on the long Policies list
in Safari + Firefox.
