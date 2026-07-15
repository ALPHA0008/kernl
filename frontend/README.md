# Kernl Console

The V1 "Decision Ledger" console — the operator surface over the `/v1` API.
Next.js 16 (App Router, Turbopack) / React 19 / Tailwind 4. No mock data: every
screen reads the real backend, authenticated by a tenant API key.

## Screens

| Route | Purpose |
|---|---|
| `/evaluate` | Run a real decision against the active bundle (typed facts or raw JSON; omit a fact to see strict escalation). |
| `/decisions/[id]` | The trace — the receipt. Every policy considered, per-condition expected/actual, precedence winner, evidence, chain hashes. |
| `/ledger` | Append-only event browser: filter, chain-verify indicator, CSV/JSON export. |
| `/escalations` + `/escalations/[id]` | The adjudicator's inbox; resolutions are ledgered adjudications with mandatory rationale + promote-to-golden. |
| `/replays` + `/replays/[id]` | Blast-radius reports (flips, golden failures) and the publish-gate acknowledgment. |
| `/policies` | Policy workbench: published bundle with evidence, registry, replay→acknowledge→publish flow, rollback (pointer move). |
| `/settings` | Session/tenant, system status, workflow fact schemas, extraction drafts (owner). |

## Run

```bash
npm install
npm run dev      # http://localhost:3000
```

Point the console at a running backend via `.env.local`:

```
NEXT_PUBLIC_KERNL_API_URL=http://127.0.0.1:8000
```

Defaults to `http://127.0.0.1:8000` if unset. The API key is entered at `/login`
and held in `sessionStorage` (cleared when the tab closes); the server enforces
tenant + role on every request regardless of what the UI offers.

## Build

```bash
npm run build
npm run lint
```
