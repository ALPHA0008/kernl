---
name: kernl-docs-and-writing
description: Load this when writing or updating ANY kernl documentation — CLAUDE.md, README.md, docs/, or a .claude/skills/ skill — or when you need to know which doc to trust ("is CLAUDE.md accurate?", "what is the design doc of record?", "why does the README say port 7860?"). Provides the doc inventory with authority ranking, the itemized CLAUDE.md drift ledger, the docs-update discipline, house style rules, SKILL.md and design-doc templates, and a ready-made docs-debt fix list with verification commands.
---

# kernl Docs and Writing

**What this covers:** which documents are authoritative for what (and how stale each one is), the exact known drift between CLAUDE.md and the code, the rule that code changes must carry their doc updates, house style for skills and design docs, copy-paste templates, and a prioritized docs-debt list.

**When NOT to use this:**
- Whether a change may merge at all, and which gate it must pass → `kernl-change-control` (gating lives there; this skill never overrides it — a docs fix is a "Docs-only" class change under its gate table).
- What the architecture actually is → `kernl-architecture-contract`; pipeline internals → `knowledge-compilation-reference`; env vars and thresholds → `kernl-config-and-flags`.
- Running the system or the eval → `kernl-run-and-operate`, `kernl-validation-and-qa`; build/deploy → `kernl-build-and-env`; debugging → `kernl-debugging-playbook`; incident history → `kernl-failure-archaeology`.
- Writing outward-facing copy (pitch, positioning) → `kernl-external-positioning`. Research writing → `kernl-research-methodology`.

Jargon, defined once:
- **Doc of record** — the single document a fact officially lives in. Every other doc that mentions the fact must cross-reference, not restate.
- **Drift ledger** — the itemized list of claims in CLAUDE.md that no longer match the code (section 2).
- **The 2ca7f83 restructure** — commit `2ca7f83` (2026-06-17) that moved the backend into `backend/core/` + `backend/engine/` + `backend/runtime/` and deleted the old `backend/graph|agent|db` layout. CLAUDE.md was last committed 2026-05-09 (commit `a688aff`) and describes the pre-restructure world: it is exactly ONE refactor stale.
- **vLLM gateway** — the shared LLM HTTP service the backend calls: `POST {VLLM_BASE_URL}/generate` with an `x-api-key` header (`backend/core/llm.py:93-97`). NOT an OpenAI-compatible endpoint.

---

## 1. Doc inventory: authority ranking and freshness (as of 2026-07-08)

When two sources disagree, the higher row wins. **Code always wins over every doc.**

| Rank | Document | Role | Last commit | Freshness verdict |
|---|---|---|---|---|
| 0 | The code itself | Ground truth | HEAD | Always current by definition |
| 1 | `.claude/skills/` (this library, 16 skills) | Onboarding + volatile-facts of record, each with dated provenance and re-verification commands | `d215501` | Authored 2026-07-07; trust each skill's own provenance table, re-run its commands when in doubt |
| 2 | `docs/operational-graph-master-plan.md` | **Design doc of record** — thesis, phased roadmap, acceptance criteria | authored 2026-05-28, committed in `2ca7f83` | Intent is current; status headers are stale. Its Phase-1 tasks (port to `engine/`+`runtime/`, delete old paths, Dockerfile → `backend.api:app`, port 8081) are largely DONE — executed by `2ca7f83`. Its Phase-1c "OpenRouter as primary LLM" plan is **SUPERSEDED**: the actual client is the custom httpx vLLM gateway in `backend/core/llm.py` (no `openrouter` string exists anywhere in `backend/`). Read Phases 2-5 as the live roadmap; read Phase 1 as history. |
| 3 | `CLAUDE.md` | AI-assistant context file | `a688aff` (2026-05-09) | **ONE REFACTOR STALE** — see the drift ledger, section 2. Structural sections (thesis, prompt pattern, SSE pattern, DB tables) remain broadly accurate; the mechanical facts do not. |
| 4 | `README.md` | Hugging Face Spaces deploy config + one-paragraph pitch | `f00b2f4` (2026-05-09) | Frontmatter `app_port: 7860` (README.md:7) contradicts the container, which listens on 8081 (`Dockerfile:29,31`). |
| 5 | `backend/.env.example` | Env template | `0762fba` (2026-05-08) | Stale: URL shape wrong for the gateway and `VLLM_API_KEY` missing entirely (section 5, DEBT-4). |
| — | `graphiti.md` | **External prior-art copy** — the Graphiti (Zep) project README, kept for reference | — | Do NOT treat as kernl design. It describes someone else's system. Never cite it as a source of kernl facts. |
| — | `backend/tests/eval_harness.py` docstring | Describes the eval | — | Stale: claims "21-scenario + 5 adversarial" (eval_harness.py:4); the `SCENARIOS` list actually contains 40 distinct scenario ids (as of 2026-07-08). |

Rule of use: quote CLAUDE.md or the master plan to a human or a model **only after** checking the drift ledger below. If the claim appears in the ledger, the code-side entry is the truth.

---

## 2. The CLAUDE.md drift ledger (as of 2026-07-08)

Every known false claim in CLAUDE.md, with the code location that disproves it. Fixing CLAUDE.md = walking this table top to bottom (see DEBT-1).

| # | CLAUDE.md claims (location) | Repo reality (location) |
|---|---|---|
| D1 | Monorepo tree: `backend/main.py`, `backend/llm.py`, `backend/sse.py`, `backend/graph/`, `backend/agent/`, `backend/db/`, `backend/models/` (CLAUDE.md:16-74) | None of these exist. Actual layout: `backend/api.py`, `backend/core/` (llm.py, sse.py, db/, models/), `backend/engine/` (state.py, graph.py, nodes/), `backend/runtime/` (brain_agent, constraint_resolver, guardrails, precedence, condition_eval, graph_retriever), `backend/chunking/`, `backend/tests/` |
| D2 | LLM client is `AsyncOpenAI(base_url="http://localhost:8000/v1")` with model `RedHatAI/Qwen2.5-72B-Instruct-FP8-dynamic` (CLAUDE.md:82-83, 96-117) | Custom httpx client: `POST {VLLM_BASE_URL}/generate`, headers `x-api-key` + `x-user-name` (backend/core/llm.py:93-98). Default URL `http://172.20.7.22:9000` (llm.py:13). No model id is sent — the gateway picks the model. No `openai` SDK involved |
| D3 | Graph = 13 nodes including `ingest_slack/ingest_notion/ingest_tickets/ingest_join` with a `route_to_ingestion` fan-out (CLAUDE.md:23-39, 157-193) | Graph is 13 nodes but a DIFFERENT 13: `load_sources → chunk_documents → [5-way Send fan-out: extract_decisions, extract_workflows, extract_exceptions, detect_contradictions, extract_entities] → build_operational_graph (barrier) → discover_operational_metadata → synthesize_skills → link_evidence → score_confidence → write_brain` (backend/engine/graph.py:21-85). No ingest_* nodes exist |
| D4 | State checkpointing via `MemorySaver` (CLAUDE.md:86, 160) | No checkpointer at all: `workflow.compile()` with no arguments (backend/engine/graph.py:85); `MemorySaver` appears nowhere in `backend/` |
| D5 | `BrainState` has `structured_sops`, `normalized_events`, `resolved_cases` (CLAUDE.md:127-151) | Those fields are gone. `backend/engine/state.py:5-32` instead adds `extracted_entities`, `extracted_relationships`, `extracted_authority_rules`, `operational_graph`, `operational_metadata` |
| D6 | Rule 6: "`compile_runs` table is append-only — never update rows" (CLAUDE.md:417) | Code UPDATES compile_runs rows: backend/api.py:187, backend/engine/nodes/write_brain.py:146, and helper `update_compile_run` at backend/core/db/supabase.py:51-54. The rule text and the code contradict each other — `kernl-change-control` section 3 owns how to handle this contradiction; do not "fix" either side without that gate |
| D7 | Endpoint list (CLAUDE.md:391-406) | Missing two live endpoints: `GET /skills/{company_id}/download` (backend/api.py:360) and `POST /skills/import` (backend/api.py:386). Separately, the frontend calls `GET /companies/{id}` (frontend/src/app/page.tsx:36) and `GET /auth/config` (frontend/src/lib/auth.tsx:30) which exist NOWHERE in backend/api.py — that frontend↔backend gap is catalogued in `kernl-architecture-contract` |
| D8 | Env vars: `VLLM_BASE_URL=http://localhost:8000/v1`, no API key (CLAUDE.md:379-385) | Code reads `VLLM_BASE_URL` (no `/v1` — the client appends `/generate`) and `VLLM_API_KEY` (backend/core/llm.py:13-14). Never write the key's default value in any doc — refer to it as "see backend/core/llm.py:14" |
| D9 | Confidence scoring formula (CLAUDE.md:239-264) | The formula itself is STILL ACCURATE — `backend/engine/nodes/score_confidence.py:5-28` implements it verbatim. What's stale is omission: synthesis also attaches per-field `metadata_confidence` and `conditions_confidence` (backend/engine/nodes/synthesize_skills.py:67-79, 319-336), which CLAUDE.md never mentions |
| D10 | No mention of port 8081, the `.claude/skills/` library, or the runtime resolver stack anywhere in CLAUDE.md | Canonical serving port is 8081 (`Dockerfile:29,31`); the 16-skill library exists; `backend/runtime/constraint_resolver.py` is the deterministic core. A reader of CLAUDE.md alone learns none of this |

Skill inventory note: CLAUDE.md's "12 skills / 6 departments" Rivanly table (CLAUDE.md:429-436) is the design EXPECTATION and is still used as the brain-quality audit target (see `kernl-change-control`). Whether the currently compiled brain matches it is UNVERIFIED from docs alone — check with `python backend/show_brain.py` from the repo root (reads `backend/tests/last_compiled_brain.json`; no gateway call).

---

## 3. Update discipline — docs travel WITH the change

1. **Same-change rule.** Any PR that changes architecture, endpoints, env vars, ports, DB schema, graph nodes, or the LLM client MUST update CLAUDE.md (and any skill that states the changed fact) in the same change. The entire drift ledger above exists because `2ca7f83` violated this rule once. Docs-only edits are gated as the "Docs-only" class in `kernl-change-control`: no eval needed, but the edit must not contradict code, must date-stamp volatile claims, and must never contain credential values.
2. **Date-stamp claims.** Every volatile fact (port, count, threshold, accuracy number, "X is broken") gets "(as of YYYY-MM-DD)" inline. An undated claim is unfalsifiable and will rot silently.
3. **Skills carry re-verification commands.** Every skill in `.claude/skills/` ends with a "Provenance and maintenance" section: a date-stamp plus a table mapping each volatile fact to a one-line command that re-checks it. **When you touch a skill, run its provenance commands first** and fix anything that drifted — that is the maintenance model for the whole library.
4. **One home per fact.** Before writing a fact, ask which doc/skill owns it. If another skill owns it, cross-reference by name instead of restating. Duplicated facts drift independently; a cross-reference cannot.
5. **Design docs are append-annotated, not rewritten.** When reality diverges from `docs/operational-graph-master-plan.md`, add a dated status note ("Phase 1: DONE via 2ca7f83, 2026-06-17"; "Phase 1c: SUPERSEDED by vLLM gateway") rather than silently rewriting history. The plan is also the record of what was intended.
6. **Never paste credentials.** Refer to secrets only as "see `<file>:<line>`" or "commit `<sha>`". Two standing cases: the `VLLM_API_KEY` default (backend/core/llm.py:14 — do not reproduce the value) and the Hugging Face token in commit `22ee2f0`, which is **compromised and must be revoked** — never quote it, even in an incident writeup (narrative home: `kernl-failure-archaeology`).

---

## 4. House style — for skills and for docs

| Rule | Do | Don't |
|---|---|---|
| Voice | Imperative runbook: "Run X. If Y, do Z." | "One might consider running X" |
| Structure | Tables and numbered checklists | Paragraphs that hide steps |
| Commands | Copy-pasteable, from the repo root, paths QUOTED (the repo path contains a space: `"D:\Abhijith P\Desktop\Project\kernl"`) | Commands that assume a cd or an activated venv without saying so |
| Jargon | Define each term ONCE at first use, in a "Jargon, defined once" block near the top | Assuming the reader knows LangGraph `Send`, "strict vs relaxed", or who Rivanly is |
| Facts | One home per fact + cross-references; date-stamp volatile facts | Restating another doc's numbers |
| Claims | Label unproven things `open` / `candidate` / `hypothesis`; never call anything "production-ready" that hasn't passed its gate | Oversell. The eval numbers are what they are — quoting them lives in `kernl-validation-and-qa` |
| Citations | `backend/core/llm.py:13` style, repo-relative, with line numbers you actually opened | Citing from memory |
| Provenance | End every skill with date-stamp + re-verification command table | Undated "trust me" sections |
| Secrets | "see file:line" / "commit sha" only | Any credential value, ever, including in examples |

---

## 5. Templates

### 5a. SKILL.md skeleton

```markdown
---
name: kernl-<topic>
description: Load this when <symptoms / tasks / keywords that should trigger it>. Provides <what the reader gets>.
---

# kernl <Topic>

**What this covers:** <one sentence>.

**When NOT to use this:**
- <adjacent need> → `kernl-<sibling-skill>`
- <adjacent need> → `kernl-<sibling-skill>`

Jargon, defined once:
- **<Term>** — <definition, with file:line anchor if code-backed>.

---

## 1. <Imperative runbook section>

<Numbered steps. Copy-pasteable commands, quoted paths, run from repo root.>

## 2. <...>

---

## Provenance and maintenance

Facts verified YYYY-MM-DD against the working tree at commit `<sha>`.

| Volatile fact | Re-verify with |
|---|---|
| <port / count / function name / line ref> | `grep -n "<pattern>" <file>` |
```

### 5b. Design-doc skeleton (modeled on the master plan's good structure)

```markdown
# <System> — <Plan Name>

**Author:** <who>  **Date:** YYYY-MM-DD  **Status:** Draft | Reviewed | Superseded-by-<doc>

## Core thesis
<The 2-3 sentence bet this design makes.>

## Where we are now
<Current state, VERIFIED against code with file:line refs — not remembered.>

## Target architecture
<Diagram + a Current-vs-Target properties table.>

## Phase N: <name>
**Duration:** <estimate>  **Goal:** <one sentence>
### Tasks
<Tables mapping source → destination → why it matters.>
### Acceptance criteria
- [ ] <binary, checkable statement>
### Verification
```bash
<exact commands that prove the criteria, runnable from repo root>
```

## Open questions and answers
### <Question>? **Answer: <decision>.** <Rationale.>

## Handoff
<Per phase: ready-to-implement, needs-review, or blocked-on-what.>
```

Why this shape: the master plan's strongest features are (a) acceptance criteria as checkboxes, (b) a literal Verification command block per phase, and (c) an "Open Questions and Answers" section recording decided trade-offs with rationale. Keep all three in any new design doc. Its weakness — no status updates after execution — is what rule 5 in section 3 fixes.

---

## 6. Docs debt — ready-made fix tasks (as of 2026-07-08)

Each is a self-contained "Docs-only" class change (gate: `kernl-change-control`). Commands run from the repo root in Git Bash; each command shows the CURRENT (stale) state — after your fix it should show the corrected state.

| ID | Task | Verify the staleness / your fix with |
|---|---|---|
| DEBT-1 | Rewrite CLAUDE.md against the drift ledger (section 2, D1-D10): new dir layout, httpx gateway client, real 13-node graph, no checkpointer, real BrainState, endpoint list incl. download/import, real env vars (no key values), note on metadata/conditions confidence, port 8081, pointer to `.claude/skills/`. Do NOT unilaterally resolve D6 — see `kernl-change-control` first | `grep -n "AsyncOpenAI\|MemorySaver\|ingest_slack\|localhost:8000" CLAUDE.md` (stale while any line matches) |
| DEBT-2 | README.md frontmatter: `app_port: 7860` → `8081` to match the container. Confirm against the HF Space settings before merging — the Space's routing follows `app_port` | `grep -n "app_port" README.md && grep -n "EXPOSE\|--port" Dockerfile` |
| DEBT-3 | eval_harness docstring: "21-scenario + 5 adversarial" → the real count (40 distinct scenario ids as of 2026-07-08). Recount, don't trust this table | `sed -n '1,8p' backend/tests/eval_harness.py && grep -o '"id": "[A-Z-]*[0-9]*"' backend/tests/eval_harness.py \| sort -u \| wc -l` |
| DEBT-4 | `backend/.env.example`: fix `VLLM_BASE_URL` shape (no `/v1` suffix — the client appends `/generate`; a `/v1` URL yields `/v1/generate` and 404s) and add a `VLLM_API_KEY=` line with a PLACEHOLDER, never the real default | `cat backend/.env.example && grep -n "VLLM_API_KEY\|VLLM_BASE_URL" backend/core/llm.py` |
| DEBT-5 | Add a dated status header to `docs/operational-graph-master-plan.md`: Phase 1 DONE via `2ca7f83` (2026-06-17); Phase 1c SUPERSEDED (vLLM gateway, not OpenRouter); Phases 2-5 = live roadmap. Annotate, don't rewrite | `grep -n "Status:" docs/operational-graph-master-plan.md && grep -rni "openrouter" backend --include="*.py"` (second grep must stay empty) |
| DEBT-6 | Decide `graphiti.md`'s fate: move under `docs/prior-art/` or add a first-line banner "EXTERNAL PRIOR ART — not kernl design". Today nothing marks it as foreign | `head -3 graphiti.md` |

Priority order: DEBT-1 first (CLAUDE.md is loaded by every AI assistant and actively misleads), then DEBT-4 (a wrong env template breaks new-machine setup — coordinate with `kernl-build-and-env`), then the rest.

---

## Provenance and maintenance

Facts verified 2026-07-08 against the working tree at commit `d215501` (repo `D:\Abhijith P\Desktop\Project\kernl`). Commands run from the repo root in Git Bash; quote the path if you cd.

| Volatile fact | Re-verify with |
|---|---|
| CLAUDE.md last committed `a688aff` 2026-05-09; restructure is `2ca7f83` 2026-06-17 | `git log --format="%h %ad %s" --date=short -1 -- CLAUDE.md && git log --format="%h %ad" --date=short -1 2ca7f83` |
| Gateway client: `POST {VLLM_BASE_URL}/generate`, `x-api-key`; default URL at llm.py:13 | `grep -n "VLLM_BASE_URL\|/generate\|x-api-key" backend/core/llm.py` |
| Graph nodes and bare `compile()` (no checkpointer) | `grep -n "add_node\|workflow.compile" backend/engine/graph.py && grep -rn "MemorySaver" backend --include="*.py"` (second grep must be empty) |
| BrainState fields (no `structured_sops`; has `extracted_entities`, `operational_graph`) | `grep -n "structured_sops\|extracted_entities\|operational_graph" backend/engine/state.py` |
| compile_runs rows are updated (contradicts CLAUDE.md:417) | `grep -rn "compile_runs" backend --include="*.py"` |
| Endpoints `/skills/{company_id}/download` (api.py:360) and `/skills/import` (api.py:386) exist; CLAUDE.md omits them | `grep -n "@app\." backend/api.py && grep -n "download\|import" CLAUDE.md` |
| Frontend calls `/companies/{id}` and `/auth/config`, absent from api.py | `grep -rn "companies/\|auth/config" frontend/src backend/api.py` |
| Confidence formula still matches CLAUDE.md; per-field confidences added in synthesis | `sed -n '5,28p' backend/engine/nodes/score_confidence.py && grep -n "_build_metadata_confidence\|conditions_confidence" backend/engine/nodes/synthesize_skills.py` |
| 40 eval scenarios vs "21+5" docstring | see DEBT-3 command |
| Port 8081 (Dockerfile) vs 7860 (README) | see DEBT-2 command |
| `.env.example` missing `VLLM_API_KEY`, has `/v1` suffix | see DEBT-4 command |
| No OpenRouter anywhere in backend (master plan 1c superseded) | `grep -rni "openrouter" backend --include="*.py"` (must be empty) |
| Skill count in this library | `ls ".claude/skills" \| wc -l` |
