# Company Brain — Product Requirements Document
**Version:** 4.0 — Final (Pre-Build, All Issues Resolved)
**Date:** May 4, 2026
**Authors:** Abhijith Pingali, Harshit Anand
**Status:** Final — Build starts post-kickoff

> **v4 changes over v3:**
> 1. Ground truth table completed — all 12 Rivanly scenarios with expected action + skill
> 2. `with_brain: false` behaviour fully documented in Section 9
> 3. Section 10 user flow added — screen-to-screen navigation with decision points
> 4. Competitive landscape updated with 8 real companies identified in LinkedIn thread
> 5. Risk table updated: "knowledge never captured" risk added from Paul Breuler's comment
> 6. Section 2.5 added: "The Stale Knowledge Problem" — validates drift detection as core feature
> 7. Section 15 updated: execution boundary insight from Horizon Labs added to v2 roadmap

---

## 1. Executive Summary

**Problem:** AI agents deployed by B2B companies behave like a new hire on day one — they lack the operational judgment embedded in how the company actually decides things. This knowledge lives in Slack threads, SOPs, support tickets, and people's heads, invisible to any model.

**Solution:** Company Brain is a compilation layer that extracts this operational judgment and produces a versioned, evidence-linked, executable skills file any AI agent can consume to act like the company's best employee.

**Success Criteria (Hackathon v0):**

| KPI | Target |
|---|---|
| Full compilation pipeline: sources → 12 skills | Completes without error, every run |
| Skills with confidence ≥ 0.7 | ≥ 10 of 12 |
| Brain agent: correct action on all Rivanly scenarios | 12 / 12 correct |
| Compilation time on AMD MI300X | < 90s (target 60s) |
| Brain agent response latency | < 8s per query |

---

## 2. Problem Statement & Solution

### 2.1 The Problem

Every company trying to deploy AI automation hits the same wall. The models are good enough. The infrastructure is available. But the AI behaves like a new hire on day one — it doesn't know how the company actually operates.

Refund policies live in Priya's head. Pricing exceptions get decided in Slack threads nobody archived. Escalation chains exist because three incidents taught the team the hard way. This operational knowledge — how the company actually decides things — is invisible to AI agents.

Existing solutions miss this entirely. RAG retrieves document chunks. Chatbots answer questions. Neither gives an AI agent the operational judgment to do real work correctly and consistently.

### 2.2 The Solution

Company Brain is the missing compilation layer. It extracts the operational judgment embedded in how a company behaves — not what it documents, but how it actually decides — and compiles it into an executable, versioned, living skills file that any AI agent can use.

**Agents are compilers, not assistants.** Company Brain's extraction agents do not summarize or search. They convert messy human behavior into structured, executable logic. The downstream brain agent that does real work is a consumer of that compiled output — it never reasons from scratch.

### 2.3 One-Line Pitch

> "We turn how your company actually operates into an executable Company Brain. Any agent can use it to do real work without guessing."

### 2.4 Product Positioning

Company Brain is **infrastructure, not a feature.**

| What it is NOT | What it IS |
|---|---|
| RAG over documents | Compiler of operational judgment |
| Chatbot over your data | Executable skills file for AI agents |
| A search engine | A living map of how your company works |
| One-time snapshot | Versioned, updatable, drift-aware |

### 2.5 The Stale Knowledge Problem (Why "Living" Matters)

*Validated by multiple practitioners in the YC RFS LinkedIn thread.*

The hardest part of any knowledge system is not building it — it is keeping it alive. Most companies will document their workflows once, ship the AI agent, and within six weeks the map diverges from reality. A new pricing exception gets approved in a Slack DM. An escalation chain changes when someone leaves. The AI keeps following the old rules.

Company Brain's stale detection — SHA-256 hashing of source files, `stale: true` badges on affected skills, and recompile triggers — directly solves this. The skills file is not a document. It is a living artifact that stays current with how the company actually evolves.

This is not a minor feature. It is the moat.

### 2.6 What Company Brain Does NOT Solve (v0)

*Acknowledged risk from Paul Breuler (BaseState founder), LinkedIn thread:*

> "The decisions that matter happen in context, on the ground, and were never captured in a ticket or Slack thread."

Company Brain compiles knowledge that was captured somewhere — Slack, SOPs, tickets, call transcripts. Knowledge that exists only in someone's head and was never written down or discussed in any recorded channel cannot be extracted. This is a known limitation. The pitch should never claim to capture all company knowledge — only the knowledge that was communicated in any digital form.

For v1, voice call transcription addresses a portion of this gap. For v2, an active knowledge capture interface (where employees record decisions as they happen) closes it further.

---

## 3. Target Customer & User Personas

### 3.1 Primary Wedge — v1

**B2B SaaS companies, 10–50 employees, actively deploying AI automation for the first time.**

These companies have:
- Enough operational complexity that AI agents fail without context
- Enough technical sophistication to understand why RAG isn't solving their problem
- Enough urgency to pay for a solution (they are actively trying and failing to deploy AI)
- Not enough resources to build this infrastructure themselves

### 3.2 User Personas

| Persona | Role | Primary Goal | Pain Point |
|---|---|---|---|
| **Ops Owner** | Head of Operations / Founder | Get AI agents to handle work consistently | Agents hallucinate edge cases; policies go stale |
| **AI Builder** | Developer / Automation Lead | Consume company knowledge in agent prompts | No structured source of truth to inject into prompts |
| **Agent Consumer** | Support agent, AM, anyone using the AI | Get correct, policy-backed responses instantly | Generic AI responses that don't match company policy |
| **Demo Viewer / Judge** | Hackathon judge, investor, prospect | Understand what the product does in 5 minutes | Can't distinguish this from "just another RAG tool" |

### 3.3 Fictional Reference Customer — Rivanly Inc.

Rivanly is a 15-person B2B SaaS company used throughout this document and the demo. 6 departments, 12 operational skills. Enough complexity to make the product real, small enough to demo in 5 minutes.

### 3.4 Expanded Customer Universe — v2+

- E-commerce operators (refund, shipping, returns automation)
- Agencies (client approval, scope change, billing exception workflows)
- Healthcare admin (referral routing, prior authorization, scheduling exceptions)
- Legal operations (intake, escalation, matter routing)

---

## 4. Jobs To Be Done

| Job | Current Solution | Problem |
|---|---|---|
| "I want an AI agent to handle customer refunds correctly" | Write a long system prompt with refund rules | Rules go stale, edge cases missed, no evidence trail |
| "I need to onboard a new AI tool to how we operate" | Document everything manually in Notion | Takes weeks, immediately outdated, agent still hallucinates |
| "I want to know if my AI agent is following company policy" | Read agent logs manually | No structured audit trail linking actions to rules |
| "We updated our pricing policy — the AI needs to know" | Edit the system prompt manually | No systematic way to detect or propagate policy changes |
| "Why did the agent make that decision?" | Cannot answer | No evidence chain from agent action back to source |

---

## 5. User Stories

### Source Ingestion & File Handling

1. As an Ops Owner, I want to upload `.md` Notion SOPs so that my written policies are ingested without manual reformatting.
2. As an Ops Owner, I want to upload Slack JSON exports so that informal decision patterns from real conversations are captured.
3. As an Ops Owner, I want to upload Zendesk ticket JSON exports so that resolved case reasoning is extracted as evidence.
4. As an Ops Owner, I want the system to detect unchanged files by SHA-256 hash so that re-uploading a file doesn't trigger unnecessary re-extraction.
5. As an Ops Owner, I want a clear parse error message when a file is malformed so that I know exactly which file to fix.
6. As an Ops Owner, I want unsupported file types to be rejected with a helpful error so that I don't wait for a compilation that will fail.
7. As an Ops Owner, I want source files stored in Supabase so that I don't need to re-upload them on every compile.

### Compilation Pipeline

8. As an Ops Owner, I want 4 extraction agents to run in parallel on AMD MI300X so that compilation completes under 90 seconds instead of 8+ minutes.
9. As an Ops Owner, I want IF-THEN-EXCEPT decision rules extracted from Slack threads so that informal decisions become structured, executable policies.
10. As an Ops Owner, I want sequential process steps extracted from SOPs and runbooks so that workflow sequences are captured correctly.
11. As an Ops Owner, I want edge cases, overrides, and "unless..." patterns extracted specifically so that exception logic isn't lost in summarization.
12. As an Ops Owner, I want contradictions between SOPs and actual Slack/ticket behavior flagged so that I can identify and resolve policy drift.
13. As an Ops Owner, I want skills with confidence below 0.6 to be flagged for human review rather than auto-published so that only verified rules go live.
14. As an Ops Owner, I want each decision rule backlinked to its source file and excerpt so that every policy is auditable, not asserted.
15. As an Ops Owner, I want the system to retry once if the LLM returns malformed JSON so that a single bad LLM response doesn't abort the whole compile.
16. As an Ops Owner, I want a clear compile error message if vLLM becomes unreachable so that I know the issue is infrastructure, not my data.
17. As a Developer, I want LangGraph checkpointing via MemorySaver so that a crashed compile can be inspected and does not silently lose data.

### Skills File & Schema

18. As an Ops Owner, I want each skill stored as a versioned JSON object with id, name, domain, confidence, decision_logic, forbidden_actions, escalation_chain, and evidence_sources so that the schema is complete and consistent.
19. As an Ops Owner, I want skills converted to markdown at query time so that they are injected into LLM prompts efficiently.
20. As an Ops Owner, I want the meta block of the skills file to store source hashes so that stale skills can be detected when source files change.
21. As an Ops Owner, I want the skills file versioned with semver so that every compile produces a traceable snapshot.

### Version Management & Drift Detection

22. As an Ops Owner, I want to compare any two historical brain versions in a diff view so that I can see exactly what changed after a policy update.
23. As an Ops Owner, I want changed rules highlighted in the diff (added green, removed red, modified yellow) so that I don't have to read everything to spot changes.
24. As an Ops Owner, I want stale skills badged in the Skills Viewer so that I know which skills need recompilation after a source file changed.
25. As an Ops Owner, I want at least 2 pre-seeded historical versions in the demo so that the diff view is usable on day one.

### Brain Dashboard (Frontend)

26. As an Ops Owner, I want a "Build Company Brain" button on the dashboard so that I can trigger recompilation from the UI without touching a terminal.
27. As an Ops Owner, I want the button to be disabled with a spinner during an active compile so that I can't trigger duplicate jobs.
28. As an Ops Owner, I want a real-time SSE feed showing each pipeline node completing with timestamps so that I trust the system is working.
29. As an Ops Owner, I want the compilation time displayed to the second so that I can use this as a live AMD MI300X proof point.
30. As an Ops Owner, I want the current brain version and last-compiled timestamp visible at a glance so that I know which brain is active.

### Skills Viewer (Frontend)

31. As an Ops Owner, I want skills grouped by department so that I can navigate to the right area quickly.
32. As an Ops Owner, I want a visual confidence bar per skill so that I can immediately see which skills are strong vs. uncertain without reading numbers.
33. As an Ops Owner, I want to expand any skill and see all its decision conditions and forbidden actions so that I can verify the rules are correct.
34. As an Ops Owner, I want the evidence panel per skill to show source file names and excerpts so that I can trace every policy back to where it came from.

### Brain Agent (Demo)

35. As an AI Builder, I want to submit a natural language scenario to the brain agent so that I get a structured action recommendation with evidence, not a guess.
36. As an AI Builder, I want the response to include the exact rule condition that matched so that I can verify the logic is correct.
37. As an AI Builder, I want the agent to gracefully handle scenarios with no matching skill so that low-confidence situations escalate to a human rather than produce a wrong answer.
38. As a Demo Viewer / Judge, I want to see the agent without the brain respond generically to the same scenario so that the value of the compilation layer is immediately obvious.
39. As a Demo Viewer / Judge, I want to see the "Change a SOP rule → Rebuild → same scenario → different outcome" flow so that I understand this is a living map, not a static snapshot.

---

## 6. Product Scope

### 6.1 Three-Ring Model

| Ring | Name | Timeline | What Ships |
|---|---|---|---|
| **Ring 1** | Hackathon v0 | May 4–10, 2026 | Offline compiler, Rivanly demo, file upload inputs, brain agent demo |
| **Ring 2** | Product v1 | 4–6 weeks post-hackathon | Live connectors, multi-tenant, real company data, auth |
| **Ring 3** | Scale | 2–6 months | Agent SDK, skills marketplace, audit trails, RBAC |

### 6.2 Hackathon v0 — In Scope

- Multi-agent compilation pipeline (LangGraph, 4 parallel async extraction agents)
- 6-department, 12-skill coverage of Rivanly Inc.
- Synthetic dataset (8 source files authored before kickoff)
- Skills file: JSON storage, markdown runtime, evidence-linked, confidence-scored, versioned
- Brain agent: scenario input → in-memory skill match → structured response with rule trace
- Frontend: Brain Dashboard + Skills Viewer + Demo Agent panel
- Real-time SSE compilation progress feed
- Brain version diffing (v1.2 → v1.3 what changed)
- AMD MI300X deployment via vLLM (`RedHatAI/Qwen2.5-72B-Instruct-FP8-dynamic`)
- Side-by-side "with brain vs. without brain" comparison panel — **P0, the money shot**
- Build in Public: 2 posts on X/LinkedIn during build

### 6.3 Out of Scope for v0

- Real Slack, Notion, Zendesk OAuth connectors — file upload only
- Multi-tenant isolation — single company demo
- Auth / login — none required for demo
- Redis job queue — direct `graph.ainvoke()` only
- pgvector — in-memory sentence-transformers for v0 skill matching
- Webhook-triggered recompilation
- Human skill review queue UI

### 6.4 Team Ownership

| Owner | Scope |
|---|---|
| **Abhijith** | F-01, F-02, F-03, F-04, F-05, F-06, F-07, F-12 (pipeline + API) |
| **Harshit** | F-08, F-09, F-10, F-11 (all frontend) |
| **Both** | Synthetic dataset — 4 files each, done before May 4 kickoff |

---

## 7. Feature Requirements

Priority: **[P0]** = demo breaks without it · **[P1]** = must ship · **[P2]** = ship if time allows

---

### F-01: Source Ingestion [P0]

**Functional Requirements:**
- Accept `.md`, `.json`, `.txt` file uploads
- Parse Notion SOP markdown → `structured_sops[]`
- Parse Slack export JSON → `normalized_events[]`
- Parse ticket JSON → `resolved_cases[]`
- Compute SHA-256 hash per file; compare to previous run; skip unchanged files
- No LLM calls at this stage — pure Python parsing only

**Acceptance Criteria:**

*AC-01-1:*
- **Given** a valid Notion SOP `.md` file is uploaded
- **When** the ingest node runs
- **Then** `structured_sops` contains at least one entry with `source`, `content`, and `type` fields

*AC-01-2:*
- **Given** a file was uploaded in a previous compile with hash `H`
- **When** the same file is uploaded again unchanged
- **Then** the ingestion node skips extraction for that file and logs "hash match, skipping"

*AC-01-3:*
- **Given** a malformed JSON file is uploaded
- **When** the ingest node attempts to parse it
- **Then** the SSE stream emits `node_error` with `file`, `error: "parse_error"`, and `detail` — and the compile continues with remaining files

*AC-01-4:*
- **Given** an unsupported file type (e.g. `.xlsx`) is uploaded
- **When** `POST /sources/upload` is called
- **Then** the API returns `400` with `{"error": "unsupported_file_type", "accepted": [".md", ".json", ".txt"]}`

---

### F-02: Parallel Extraction [P0]

**Functional Requirements:**
- Four async LangGraph nodes run simultaneously via `Send` API + `await llm.ainvoke()`
- Decision Extractor: IF-THEN-EXCEPT judgment patterns from Slack + tickets
- Workflow Extractor: sequential process steps from SOPs and runbooks
- Exception Extractor: edge cases, overrides, "unless..." patterns
- Contradiction Detector: divergence between SOPs and actual behavior
- All four target `RedHatAI/Qwen2.5-72B-Instruct-FP8-dynamic` on AMD MI300X via vLLM

**Acceptance Criteria:**

*AC-02-1:*
- **Given** all three ingest nodes have completed
- **When** `route_to_extractors` is called
- **Then** all four extraction nodes start within 2 seconds of each other

*AC-02-2:*
- **Given** the Rivanly synthetic dataset
- **When** extraction completes
- **Then** each extractor returns a non-empty list; `contradictions[]` contains ≥ 1 entry

*AC-02-3:*
- **Given** the LLM returns malformed JSON for one extractor
- **When** the node catches the error
- **Then** it retries once with a stricter JSON-only prompt; if still malformed, returns empty list and emits `node_error` without aborting other extractors

*AC-02-4:*
- **Given** all four async extractors complete
- **When** wall clock is checked
- **Then** total extraction time is under 45 seconds on MI300X

---

### F-03: Skill Compilation [P0]

**Functional Requirements:**
- Synthesize extractor outputs into 12 canonical skill objects
- Evidence linker: backfill `evidence_sources[]` for every `decision_logic` entry
- Confidence scorer: `f(source_count, source_recency, internal_consistency)`
- Skills below 0.6 confidence: present with `"review_required": true`, not auto-published
- Write `skills_file.json` to Supabase `skills_files` table with incremented semver

**Acceptance Criteria:**

*AC-03-1:*
- **Given** all extraction nodes have produced output
- **When** `synthesize_skills` runs
- **Then** output contains exactly 12 skill objects, each with all required schema fields

*AC-03-2:*
- **Given** a skill has been synthesized
- **When** `link_evidence` runs
- **Then** every `decision_logic` entry has at least one `evidence_sources` entry with non-empty `source` and `excerpt`

*AC-03-3:*
- **Given** a skill has only one supporting source
- **When** `score_confidence` runs
- **Then** that skill's `confidence` is below 0.7 and `review_required` is `true` if below 0.6

*AC-03-4:*
- **Given** compilation succeeds
- **When** `write_brain` runs
- **Then** `skills_files` table gains a new row with semver one minor bump higher, `is_current: true`, and all previous rows `is_current: false`

---

### F-04: Skills File Format [P0]

**Schema (per skill):**
```json
{
  "id": "handle_refund_request",
  "name": "Handle Refund Request",
  "domain": "support",
  "version": "1.2",
  "confidence": 0.91,
  "stale": false,
  "review_required": false,
  "last_updated": "2026-05-04T09:30:00Z",
  "trigger": {
    "phrases": ["refund", "money back"],
    "conditions": ["customer mentions payment dissatisfaction"]
  },
  "decision_logic": [
    {
      "condition": "plan == 'annual' AND days_since_purchase <= 14",
      "action": "approve_full_refund",
      "note": "No-questions policy within 14 days.",
      "evidence_sources": [
        { "source": "notion_refund_sop.md", "excerpt": "...", "confidence": 0.95 }
      ]
    }
  ],
  "forbidden_actions": ["Never process refunds for lifetime deal accounts"],
  "escalation_chain": ["support_agent", "support_lead", "account_manager", "founder"],
  "sla": "respond_within_2h, resolve_within_24h"
}
```

**Acceptance Criteria:**

*AC-04-1:*
- **Given** the compiled skills file
- **When** validated against JSON schema
- **Then** zero validation errors

*AC-04-2:*
- **Given** a skill selected for prompt injection
- **When** converted to markdown
- **Then** output is plain English, contains all conditions and forbidden actions, under 800 tokens

---

### F-05: Brain Version Management [P1]

**Acceptance Criteria:**

*AC-05-1:*
- **Given** one source file changed and recompilation triggered
- **When** compile finishes
- **Then** new brain version is a minor bump (`1.2.0 → 1.3.0`) and diff endpoint returns that file's dependent skills as `modified_skills`

*AC-05-2:*
- **Given** two brain versions exist
- **When** `GET /diff/1.2.0/1.3.0` is called
- **Then** response contains `added_skills`, `removed_skills`, and `modified_skills` with per-skill field-level changes

*AC-05-3:*
- **Given** a source file changes
- **When** the new compile runs
- **Then** skills whose `evidence_sources` reference that file have `stale: true`

---

### F-06: Scenario Handling — Brain Agent [P0]

**Functional Requirements:**
- Accept natural language scenario input + optional structured context
- Embed query via `all-MiniLM-L6-v2` (in-memory, CPU); pre-compute skill embeddings once at startup
- Cosine similarity match → select top skill
- Convert skill JSON → markdown snippet
- Single LLM call: company context + skill rules + scenario
- Return structured response (F-07)

**Acceptance Criteria:**

*AC-06-1:*
- **Given** an enterprise refund scenario
- **When** `POST /agent/handle` is called
- **Then** matched skill is `handle_refund_request` (cosine similarity > 0.6)

*AC-06-2:*
- **Given** all 12 Rivanly demo scenarios submitted in sequence
- **When** each response reviewed
- **Then** all 12 return correct action (verified against ground truth table in Section 12)

*AC-06-3:*
- **Given** a scenario matching no skill above cosine 0.4
- **When** match function runs
- **Then** response is `{"action": "escalate_to_human", "reason": "no_skill_match", "confidence": <score>}` — not an error, not a hallucination

*AC-06-4:*
- **Given** a valid scenario submitted
- **When** response returned
- **Then** wall-clock latency under 8 seconds

---

### F-07: Response Structure [P0]

Every `POST /agent/handle` response:

```json
{
  "action": "escalate_to_am_within_1hr",
  "message_to_customer": "...",
  "rule_applied": "plan == 'enterprise' AND any_amount",
  "evidence": {
    "source": "slack_thread_2024-03-12",
    "excerpt": "enterprise = always AM"
  },
  "skill_matched": "handle_refund_request",
  "confidence": 0.91
}
```

**Acceptance Criteria:**

*AC-07-1:*
- **Given** any valid scenario input
- **When** brain agent responds
- **Then** all six top-level fields present and non-null

*AC-07-2:*
- **Given** the response `rule_applied` field
- **When** compared to matched skill's `decision_logic`
- **Then** string matches an exact `condition` field — never paraphrased

---

### F-08: Brain Dashboard [P0]

**Acceptance Criteria:**

*AC-08-1:*
- **Given** the dashboard is loaded
- **When** user clicks "Build Company Brain"
- **Then** button becomes disabled with spinner and SSE feed begins showing node events within 2 seconds

*AC-08-2:*
- **Given** SSE stream is active
- **When** each pipeline node completes
- **Then** feed shows node name, completion checkmark, and elapsed time in real time without page refresh

*AC-08-3:*
- **Given** compilation completes
- **When** dashboard updates
- **Then** brain version, last-compiled timestamp, and total compilation time displayed with correct values

---

### F-09: Skills Viewer [P0]

**Acceptance Criteria:**

*AC-09-1:*
- **Given** a compiled brain with 12 skills
- **When** Skills Viewer loaded
- **Then** all 12 skills visible, grouped under 6 correct department headings

*AC-09-2:*
- **Given** a skill with `stale: true`
- **When** it appears in the viewer
- **Then** it has a visible "Stale" badge and confidence bar is visually de-emphasized

*AC-09-3:*
- **Given** user clicks any skill
- **When** detail panel expands
- **Then** all `decision_logic` conditions, all `forbidden_actions`, `escalation_chain`, and at least one `evidence_sources` entry visible

---

### F-10: Demo Agent Panel [P0] — Side-by-Side Required

**Functional Requirements:**
- Free-text scenario input + optional structured context fields
- Two response panels rendered simultaneously:
  - **Without Brain:** Same LLM, same scenario, system prompt contains only the raw scenario — no company name, no skills context, no Rivanly-specific information. Goal: produce a demonstrably generic response.
  - **With Brain:** Full skill context + rule trace + evidence
- Visual trace showing matched skill and cosine similarity score

**Acceptance Criteria:**

*AC-10-1:*
- **Given** a scenario submitted
- **When** both panels render
- **Then** both responses appear within 10 seconds

*AC-10-2:*
- **Given** the enterprise refund demo scenario
- **When** both panels render
- **Then** "Without Brain" response is generic (no company-specific rule, no evidence); "With Brain" response includes `rule_applied` and `evidence` visually highlighted

*AC-10-3:*
- **Given** a judge views the demo panel for the first time
- **When** they read both responses
- **Then** the value of the brain is legible without any verbal explanation

---

### F-11: Version Diff View [P1]

**Acceptance Criteria:**

*AC-11-1:*
- **Given** two pre-seeded brain versions (v1.1.0 and v1.2.0)
- **When** diff view opened and both selected
- **Then** modified skills highlighted yellow with field-level changes inline

*AC-11-2:*
- **Given** the "change a rule → rebuild → diff" demo flow
- **When** performed end-to-end
- **Then** diff correctly shows changed rule in under 30 seconds of demo time

---

### F-12: API Layer [P0]

**`POST /compile`**
```
Request:  { "company_id": "rivanly-inc", "force_recompile": false }
Response: { "job_id": "uuid", "status": "started", "stream_url": "/compile/stream?job_id=uuid" }
```

**`GET /brain/status`**
```
Response: {
  "company_id": "rivanly-inc",
  "brain_version": "1.3.0",
  "last_compiled_at": "2026-05-04T09:30:00Z",
  "total_skills": 12,
  "stale_skills": 2,
  "coverage_areas": ["support", "revenue", "product_eng", "customer_success", "hr", "finance_ops"]
}
```

**`GET /skills`**
```
Response: {
  "skills": [
    { "id": "handle_refund_request", "name": "Handle Refund Request",
      "domain": "support", "confidence": 0.91, "stale": false, "version": "1.2" }
  ]
}
```

**`GET /skills/:id`** → full skill object (schema per F-04)

**`POST /agent/handle`**
```
Request: {
  "scenario": "Enterprise customer, 18 months tenure, wants $1,200 refund",
  "context": { "plan": "enterprise", "tenure_months": 18, "refund_amount": 1200 },
  "with_brain": true
}
```

**`with_brain` flag behaviour (fully specified):**
- `with_brain: true` → system prompt includes: company name (Rivanly), active brain version, relevant skill in markdown, all decision conditions, forbidden actions, escalation chain
- `with_brain: false` → system prompt contains ONLY the raw scenario text. No company name. No skills context. No Rivanly-specific information. No hint that a brain exists. The goal is to produce a generic response from the base model that demonstrates what agents do WITHOUT the compilation layer. This is the "before" panel in the side-by-side comparison.

**`GET /compile/stream?job_id=uuid`** — SSE event schema:
```
event: node_start
data: {"node": "ingest_slack", "timestamp": "2026-05-04T09:30:01Z"}

event: node_complete
data: {"node": "ingest_slack", "duration_ms": 312, "output_count": 47}

event: node_error
data: {"node": "extract_decisions", "error": "llm_malformed_json", "retrying": true}

event: compile_complete
data: {
  "brain_version": "1.3.0",
  "total_skills": 12,
  "stale_skills": 0,
  "duration_ms": 54200,
  "skills_below_threshold": 1
}

event: compile_error
data: {"error": "llm_unavailable", "checkpoint_saved": true, "resume_job_id": "uuid"}
```

**`GET /diff/:v1/:v2`**
```
Response: {
  "from_version": "1.2.0", "to_version": "1.3.0",
  "added_skills": [], "removed_skills": [],
  "modified_skills": [
    { "id": "handle_refund_request",
      "changes": [{"field": "decision_logic[1].action",
                   "from": "approve_prorated_refund", "to": "escalate_to_am"}] }
  ]
}
```

**`POST /sources/upload`**
```
Request:  multipart/form-data: files[], company_id
Response: { "uploaded": ["notion_refund_sop.md"], "hashes": {"notion_refund_sop.md": "sha256:a1b2c3..."} }
```

---

## 8. AI System Requirements

### 8.1 Tool & Model Requirements

| Component | Tool / Model | Reason |
|---|---|---|
| All LLM extraction calls | `RedHatAI/Qwen2.5-72B-Instruct-FP8-dynamic` via vLLM | Best instruction following; FP8 = 1.5× throughput, ~72GB VRAM |
| Skill matching (v0) | `all-MiniLM-L6-v2` via `sentence-transformers` (in-memory, CPU) | Zero infra overhead; sufficient for 12 skills |
| Skill matching (v1) | pgvector on Supabase | Multi-tenant, persistent, scalable |
| LLM fallback | `Llama-3.3-70B BF16` | If Qwen2.5 unavailable on MI300X |
| Serving | vLLM on AMD MI300X (192GB VRAM) | Parallel batch inference, OpenAI-compatible API |

### 8.2 Extraction Prompts — Requirements

- All extractors demand: "Output ONLY structured JSON. Do not summarize. Do not generalize beyond what the text explicitly supports."
- All extractors include: output schema definition + 1-shot example in system prompt
- Temperature: 0.1 (deterministic extraction)
- Max tokens: 4096 per call

### 8.3 Evaluation Strategy

| Eval | Target | How to test |
|---|---|---|
| Brain agent correct action | 12 / 12 (100%) | Run all 12 scenarios against ground truth table |
| Evidence coverage | 100% of `decision_logic` entries have ≥ 1 `evidence_sources` | JSON schema validation post-compile |
| Contradiction recall | ≥ 2 contradictions flagged | Plant 2 deliberate contradictions in synthetic dataset |
| Confidence calibration | Well-sourced skills ≥ 0.7, single-source skills < 0.75 | Inspect post-compile |
| LLM JSON validity | 0 uncaught malformed responses in 10-run stress test | Run compile 10× on same dataset |
| "Without brain" failure rate | ≥ 8 of 12 scenarios produce generic/wrong response | Verify demo panel contrast is meaningful |

---

## 9. Implementation Decisions

**`with_brain: false` — Full Specification**

When `POST /agent/handle` is called with `"with_brain": false`, the system prompt sent to Qwen2.5-72B contains ONLY this:

```
You are a helpful customer support assistant.
The customer says: {scenario}
{context if provided}
Respond appropriately.
```

No company name. No skills. No Rivanly. No hint that any compiled knowledge exists. The base model responds from its training data alone. This produces a generic, policy-free response — which is the "before" state that makes the "with brain" response look like magic.

**Other key architectural decisions:**

- `ingest_join` + `Send` API pattern required for correct LangGraph fan-in. Direct edges ingest→extract cause synthesis to fire before all extractors complete.
- `Annotated[List, operator.add]` on all extraction output fields required for parallel writes to merge correctly rather than overwrite.
- `await compiled_graph.ainvoke(initial_state)` — not `.invoke()` — in FastAPI background task. Without async, nodes block the event loop and parallelism is lost.
- Skills file is the only source of truth. The agent never reads raw source files at query time.
- `skills_files.is_current` enforced via partial unique index — only one row per company can be `true` at a time.
- `compile_runs` table is append-only. No updates.

---

## 10. Technical Specifications

### 10.1 Architecture Overview

```
FILE UPLOAD (Next.js)
       │
       ▼ POST /sources/upload
FASTAPI API LAYER
       │
       ▼ POST /compile → ainvoke
LANGGRAPH ENGINE (BrainState)
  │
  ├── INGESTION (parallel, CPU)
  │   ├── ingest_slack → normalized_events[]
  │   ├── ingest_notion → structured_sops[]
  │   └── ingest_tickets → resolved_cases[]
  │   └── ingest_join (barrier)
  │
  ├── EXTRACTION (parallel, async, AMD MI300X)
  │   ├── extract_decisions → raw_decisions[]
  │   ├── extract_workflows → workflow_steps[]
  │   ├── extract_exceptions → exception_rules[]
  │   └── detect_contradictions → contradictions[]
  │
  └── COMPILATION + VALIDATION (sequential)
      ├── synthesize_skills → draft_skills[]
      ├── link_evidence → skills_with_evidence[]
      ├── score_confidence → confidence per skill
      └── write_brain → skills_file.json → Supabase

BRAIN AGENT (query time)
  POST /agent/handle
  → sentence-transformers match → skill JSON → markdown
  → single vLLM call → structured response JSON
```

### 10.2 Screen-to-Screen User Flow

**Primary flow (Ops Owner compiling and testing for the first time):**

```
[Upload Sources page]
  → Upload 3–8 files (drag + drop or file picker)
  → See file list with SHA-256 hash status (new / unchanged / changed)
  → Click "Done — Go to Dashboard"
       ↓
[Brain Dashboard]
  → See: company name, current brain version (or "No brain yet"), last compiled timestamp
  → See: source files uploaded (count)
  → Click "Build Company Brain" button
       ↓
[SSE Progress overlay — renders in-place on Dashboard]
  → Real-time: each node appears as it starts, gets checkmark when complete
  → ingest_slack ✓ → ingest_notion ✓ → ingest_tickets ✓ → [join]
  → extract_decisions ✓ (parallel) extract_workflows ✓ extract_exceptions ✓ detect_contradictions ✓
  → synthesize_skills ✓ → link_evidence ✓ → score_confidence ✓ → write_brain ✓
  → "Brain compiled: v1.3.0 in 58 seconds"
       ↓
[Brain Dashboard — updated state]
  → Version badge updated: v1.3.0
  → Last compiled: just now
  → 12 skills / 6 departments / 0 stale
  → Click "View Skills" (or nav to Skills in sidebar)
       ↓
[Skills Viewer]
  → 6 department groups, 12 skill cards
  → Each card: name, confidence bar, stale badge (if applicable)
  → Click any skill card → detail panel expands right
  → Detail: all conditions, forbidden actions, escalation chain, evidence panel (source + excerpt)
  → Click "Try a scenario" button (appears in detail panel)
       ↓
[Demo Agent Panel]
  → Left panel: "Without Brain" — base model response (generic)
  → Right panel: "With Brain" — rule trace + evidence + action
  → Scenario input pre-filled from skill that was clicked (optional convenience)
  → Submit → both panels render simultaneously
  → Judge reads both — value is self-evident
  → Click "What changed?" link (appears in top nav after ≥ 2 brain versions exist)
       ↓
[Version Diff View]
  → Select v1 and v2 from dropdowns (pre-seeded with v1.1.0 and v1.2.0)
  → See: modified skills (yellow), new skills (green), removed (red)
  → Click modified skill → see field-level diff of changed conditions
  → Click "← Back to Dashboard" (always accessible from nav)
       ↓
[Brain Dashboard]
  → Modify a source file → re-upload → stale badge appears on affected skills
  → Click "Build Company Brain" → recompile cycle repeats
```

**Critical path for demo (8-step script):**
Upload Sources → Dashboard → Build → SSE feed → Skills Viewer → Evidence panel → Demo Agent (side-by-side) → Change + Rebuild → Diff view

**Navigation rules:**
- Sidebar always visible: Dashboard | Skills | Agent | Diff
- "Try a scenario" shortcut from Skills Viewer pre-fills the Agent panel's skill context
- "What changed?" link only appears when ≥ 2 brain versions exist (prevents confusion when first compiled)
- All pages accessible from nav at any time — no forced linear flow outside the demo script

### 10.3 Integration Points

| Integration | v0 | v1 |
|---|---|---|
| LLM | vLLM on AMD MI300X (private IP:8000) | Same + failover |
| Database | Supabase Postgres | Same + RLS per company |
| File storage | Supabase Storage | Same |
| Auth | None | Clerk |
| Queue | None (direct ainvoke) | Redis/Upstash |
| Connectors | File upload only | Slack OAuth, Notion API, Zendesk |
| Checkpointing | MemorySaver (in-memory) | PostgresSaver |

### 10.4 Security & Privacy

**v0 (hackathon):** All data is synthetic (Rivanly is fictional). No PII. vLLM on private AMD cloud IP. No RLS needed.

**v1 (required before real customer data):**
- Clerk auth on all endpoints
- Supabase RLS: `company_id` row-level isolation
- vLLM behind VPC — not publicly accessible
- No customer message content stored permanently — only extracted rules and evidence excerpts

---

## 11. Data Model (Supabase)

```sql
CREATE TABLE companies (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE skills_files (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id TEXT REFERENCES companies(id),
  version TEXT NOT NULL,
  brain_json JSONB NOT NULL,
  source_hashes JSONB NOT NULL,
  compiled_at TIMESTAMPTZ DEFAULT now(),
  is_current BOOLEAN DEFAULT false
);
CREATE UNIQUE INDEX idx_skills_files_current ON skills_files(company_id) WHERE is_current = true;

CREATE TABLE skills (
  id TEXT NOT NULL,
  company_id TEXT REFERENCES companies(id),
  skills_file_id UUID REFERENCES skills_files(id),
  name TEXT NOT NULL,
  domain TEXT NOT NULL,
  version TEXT NOT NULL,
  confidence FLOAT NOT NULL,
  stale BOOLEAN DEFAULT false,
  review_required BOOLEAN DEFAULT false,
  skill_json JSONB NOT NULL,
  PRIMARY KEY (id, company_id, skills_file_id)
);

CREATE TABLE source_files (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id TEXT REFERENCES companies(id),
  filename TEXT NOT NULL,
  sha256 TEXT NOT NULL,
  storage_path TEXT NOT NULL,
  uploaded_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE compile_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id TEXT REFERENCES companies(id),
  status TEXT NOT NULL CHECK (status IN ('started','running','complete','error')),
  started_at TIMESTAMPTZ DEFAULT now(),
  completed_at TIMESTAMPTZ,
  duration_ms INTEGER,
  result_version TEXT,
  error_detail TEXT
);

CREATE INDEX idx_skills_files_company ON skills_files(company_id, compiled_at DESC);
CREATE INDEX idx_skills_company ON skills(company_id);
```

---

## 12. Testing Decisions

### Ground Truth Test Suite — All 12 Scenarios (COMPLETE)

**Owner: Abhijith. Must be run and passing before demo day. All 12 must return correct `action`.**

| # | Scenario | Key Context | Expected `action` | Expected `skill_matched` |
|---|---|---|---|---|
| 1 | Enterprise customer, 18 months tenure, $1,200 refund requested | plan=enterprise, tenure=18mo, amount=1200 | `escalate_to_am_within_1hr` | `handle_refund_request` |
| 2 | Annual plan customer, day 10 of subscription, $300 refund requested | plan=annual, days_since_purchase=10, amount=300 | `approve_full_refund` | `handle_refund_request` |
| 3 | New customer, 2 months tenure, $600 refund requested | plan=monthly, tenure=2mo, amount=600 | `escalate_to_founder` | `handle_refund_request` |
| 4 | Loyal annual customer, 14 months tenure, $150 refund outside window | plan=annual, tenure=14mo, amount=150 | `approve_prorated_refund` | `handle_refund_request` |
| 5 | Lifetime deal customer requesting any refund | plan=lifetime, amount=any | `deny_refund_ltd_terms` | `handle_refund_request` |
| 6 | Customer contact during active platform outage | context=outage_active | `send_incident_response_template` | `respond_to_outage` |
| 7 | Startup customer requesting 40% discount | customer_type=startup, discount_requested=40% | `escalate_to_ae` | `evaluate_discount_request` |
| 8 | P0 bug reported on dashboard module by enterprise customer | bug_severity=P0, customer_plan=enterprise | `page_oncall_engineer_immediately` | `prioritize_bug_report` |
| 9 | Customer SLA breached by 2 hours, enterprise plan | sla_breach_hours=2, plan=enterprise | `notify_am_and_eng_lead` | `handle_sla_breach` |
| 10 | Customer showing 3 churn signals in last 30 days (no login, support ticket, downgrade inquiry) | signals=3, timeframe=30days | `schedule_am_call_within_24h` | `evaluate_churn_risk` |
| 11 | Engineering candidate — completed 2 rounds, needs offer approval | stage=offer, role=engineer | `get_founder_approval_before_sending` | `hiring_process_engineering` |
| 12 | Vendor invoice for $3,500 needs payment approval | amount=3500, vendor_type=software | `route_to_ops_lead_approval` | `approve_vendor_payment` |

**How to run:**
```python
# Run before demo. All 12 must pass.
for scenario in GROUND_TRUTH_SCENARIOS:
    response = client.post("/agent/handle", json=scenario["input"])
    assert response.json()["action"] == scenario["expected_action"]
    assert response.json()["skill_matched"] == scenario["expected_skill"]
```

### Module Test Matrix

| Module | Test Type | What to Test |
|---|---|---|
| Source parsers | Unit | Given raw fixture file → correct normalized output shape |
| SHA-256 hasher | Unit | Same content → same hash; changed content → different hash |
| Skill matcher | Unit | Given 12 known queries → each returns correct `skill_id` |
| JSON→Markdown converter | Unit | Given skill object → output contains all conditions and forbidden actions, under 800 tokens |
| `POST /compile` | Integration | Returns `job_id` and `stream_url`; sets compile_run status to "started" |
| `GET /skills` | Integration | Returns exactly 12 skills for Rivanly |
| `POST /agent/handle` | Integration | All 12 ground-truth scenarios return correct `action` |
| `GET /diff/:v1/:v2` | Integration | Pre-seeded v1.1.0 and v1.2.0 → returns expected `modified_skills` |
| Full pipeline | End-to-end | 8 source files → 12 skills in Supabase, `is_current: true`, all with evidence |
| LLM output | Eval | 10-run stress test → zero uncaught malformed JSON |

---

## 13. Non-Functional Requirements

- Full compilation: under 90 seconds (target: 60s)
- Brain agent response: under 8 seconds
- SSE feed: real-time node events, no polling
- Skill matching: under 200ms (in-memory cosine similarity)
- LangGraph MemorySaver checkpointing: compile state survives crash
- Fallback model: Llama-3.3-70B BF16 if Qwen2.5 unavailable
- vLLM health check queried before accepting `/compile` requests

---

## 14. Success Metrics

### Hackathon v0 — Measurable Targets

| Metric | Target | Verification |
|---|---|---|
| End-to-end pipeline | Completes without error | Run 3× in final 2 hours |
| Skills produced | Exactly 12 | Check `skills_file.json` |
| Skills with confidence ≥ 0.7 | ≥ 10 of 12 | Check confidence field |
| Agent correct action | 12 / 12 | Run ground truth suite |
| Agent latency | < 8 seconds | Time on demo day |
| Compilation time | < 90 seconds | Dashboard display |
| Live URL accessible | Yes | Test on fresh device before submission |
| Demo video submitted | Yes | Render early, keep backup |
| Public posts | 2 minimum | During hours 8–16 and 16–28 |

### The 8-Step Demo — Ring 1 Acceptance Test

1. Show source files — "Rivanly's scattered knowledge."
2. Click "Build Company Brain" — watch SSE feed in real time.
3. Show compilation time — "12 skills in 58 seconds on AMD MI300X."
4. Open Skills Viewer — 6 departments, 12 skills, confidence bars.
5. Click `handle_refund_request` — show evidence panel.
6. Submit enterprise refund scenario to agent panel.
7. Show side-by-side: without brain (generic) vs. with brain (rule trace + evidence).
8. Change one SOP rule → Rebuild → same scenario → different outcome. **This is the moment.**

### Post-Hackathon Business Metrics (v1)

- 3 paying pilot customers within 60 days of v1 launch
- Activation: first brain compiled + agent handles 1 scenario correctly
- Retention: brain recompiled at least once within 30 days
- Revenue: $200/month Starter, $500/month Growth

---

## 15. Competitive Landscape

*Updated with companies identified in YC/LinkedIn Company Brain thread.*

| Company | What they do | Differentiation |
|---|---|---|
| **Notion AI** | Q&A over documents | Retrieves chunks, doesn't compile operational judgment |
| **Guru / Confluence** | Knowledge base search | Human-maintained, not executable by AI agents |
| **Glean** | Enterprise search | Search-first, not compilation; no executable output |
| **Sugarwork** (sugarwork.com) | Surfaces tacit knowledge for AI | Adjacent; watch closely |
| **BrandOS** (getbrandos.site) | Company brain for marketing teams | Vertical-specific; not full company coverage |
| **Context AI** | Operational knowledge for agents | Direct competitor — monitor |
| **LineageOne** (NEXT'26) | Fragmented operations → live operational model | Direct competitor |
| **AutoBase** | Building this for 7 months | Direct competitor |
| **Company Brain** | Full compilation layer, all departments, versioned, evidence-linked | Evidence trail, stale detection, parallel AMD compilation |

**Observation:** Multiple teams are building in this space. This validates the market. The race is to who ships the most complete, demo-able, production-credible version. Company Brain's differentiator is the combination of: evidence-linked rules (not just structured outputs), stale detection, version diffing, and the clean "compiler not assistant" framing that competitors haven't articulated.

---

## 16. Risks & Mitigation

| Risk | Likelihood | Mitigation |
|---|---|---|
| Knowledge that was never captured cannot be extracted | **High — acknowledged** | Scope v0 to knowledge that exists in digital form; call out in pitch as known limitation; v1 adds call transcription |
| Extraction agents produce low-quality skills | Medium | Dataset authored backward from desired output; eval suite catches failures before demo |
| vLLM setup on AMD cloud takes too long | Low | Kubernetes on AMD course completed; fallback to Fireworks API |
| LangGraph parallel fan-in bug | Low | Fixed using `Send` API + `ingest_join` barrier node |
| Demo breaks during judging | Medium | Pre-recorded fallback video; deploy to stable URL 24h before submission |
| Qwen2.5-72B FP8 unavailable | Low | `RedHatAI/Qwen2.5-72B-Instruct-FP8-dynamic` confirmed on HuggingFace |
| Frontend/backend API contract mismatch | Medium | Both parties agree on F-12 schemas before writing frontend code |
| Synthetic dataset too shallow | Medium | Each file: ≥ 4 edge cases, ≥ 1 planted contradiction; reviewed together before kickoff |
| Competitors ship demo before May 11 | Low | Multiple are building but none have shipped a demo yet; Company Brain's AMD + parallel compile angle is unique |

---

## 17. v2 Roadmap — Insights from LinkedIn Thread

*Insights from practitioners who responded to Tom Blomfield's YC RFS post that should inform v2 product decisions.*

**Execution boundaries (Horizon Labs insight):** The skills file is currently advisory — the agent reads it and acts. In v2, the skills file should become constraining — the agent should not be able to take actions not in the admissible action set. This is the difference between a knowledge map and an execution boundary. Add to v2: `forbidden_actions` enforced at the runtime level, not just injected as prompt guidance.

**The stale knowledge divergence problem (Matan Elmalam insight):** Teams build the map once, ship the agent, and within six weeks reality diverges. Our stale detection addresses this for captured knowledge. For v2: active monitoring — compare agent actions against skills file weekly and surface divergences as "possible new skills" for human review.

**Call transcription (Paul Breuler gap):** Knowledge that exists only in spoken conversations will never be in Slack or Notion. In v2: integrate with Fireflies/Otter/Grain to pull meeting transcripts as a first-class source type. This closes the most common knowledge capture gap.

**Audit trail (Josh Jefferd insight):** Every agent action should be logged with which skill rule was applied and which evidence excerpt justified it. This is the compliance and trust layer. Add to v2 roadmap as a first-class feature, not an afterthought.

---

## 18. Open Questions — All Resolved

| Question | Resolution |
|---|---|
| Who owns frontend vs. pipeline? | Abhijith = pipeline + API. Harshit = all frontend. |
| Supabase schema? | Defined in Section 11. |
| SSE disconnect/reconnect handling? | Frontend: exponential backoff (1s, 2s, 4s). Fallback: `GET /brain/status` for final state. |
| Synthetic dataset ownership? | Both — 4 files each, authored before May 4 kickoff. |
| Ground truth table complete? | Yes — all 12 scenarios in Section 12. Run before demo. |
| `with_brain: false` behaviour? | Fully specified in F-10 and Section 9. |
| Screen-to-screen user flow? | Defined in Section 10.2. |

---

*This document supersedes company_brain_PRD_v3.md. All three audit issues resolved. Competitive landscape updated with real companies from LinkedIn thread. No scope changes after May 4 kickoff.*
