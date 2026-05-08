# Company Brain — CLAUDE.md
## Project context for AI coding assistants

---

## What This Project Is

Company Brain is a multi-agent compilation pipeline that extracts operational decision knowledge from company data sources (Slack, Notion SOPs, support tickets) and compiles it into a versioned, evidence-linked, executable skills file. A downstream brain agent uses this skills file to handle operational scenarios correctly — acting like the company's best employee.

**The core thesis:** Agents are compilers, not assistants. We don't search raw documents. We compile tribal knowledge into structured, executable logic once. Then we read the compiled output forever.

---

## Monorepo Structure

```
kernl/
├── backend/              ← FastAPI + LangGraph pipeline (Python)
│   ├── main.py           ← FastAPI app entry point
│   ├── llm.py            ← vLLM client, semaphore(4), embeddings, JSON self-repair
│   ├── sse.py            ← Server-Sent Events bus for streaming
│   ├── test_compile.py   ← Standalone graph test
│   ├── graph/
│   │   ├── state.py      ← BrainState TypedDict
│   │   ├── graph.py      ← graph assembly + compile
│   │   └── nodes/        ← one file per LangGraph node
│   │       ├── load_sources.py
│   │       ├── ingest_slack.py
│   │       ├── ingest_notion.py
│   │       ├── ingest_tickets.py
│   │       ├── ingest_join.py
│   │       ├── extract_decisions.py
│   │       ├── extract_workflows.py
│   │       ├── extract_exceptions.py
│   │       ├── detect_contradictions.py
│   │       ├── synthesize_skills.py
│   │       ├── link_evidence.py
│   │       ├── score_confidence.py
│   │       └── write_brain.py
│   ├── agent/
│   │   └── brain_agent.py ← query-time brain agent (embedding + LLM reasoning)
│   ├── db/
│   │   ├── supabase.py   ← Supabase client + queries
│   │   └── schema.sql    ← DB schema (5 tables)
│   ├── models/
│   │   └── schemas.py    ← Pydantic models for API
│   ├── requirements.txt
│   └── .env.example
├── frontend/             ← Next.js 16.2.5 + Tailwind v4
│   ├── src/app/
│   │   ├── page.tsx          ← Dashboard
│   │   ├── layout.tsx        ← Root layout
│   │   ├── globals.css       ← Tailwind + custom theme
│   │   ├── compile/[jobId]/page.tsx   ← Pipeline stream viewer
│   │   ├── skills/[companyId]/page.tsx ← Skills viewer
│   │   └── demo/[companyId]/page.tsx  ← Brain vs Generic A/B comparison
│   └── ...
├── data/
│   └── sources/rivanly-inc/  ← 8 synthetic source files
│       ├── notion_refund_sop.md
│       ├── notion_pricing_policy.md
│       ├── notion_eng_runbook.md
│       ├── notion_hr_playbook.md
│       ├── notion_cs_playbook.md
│       ├── slack_export_support.json
│       ├── slack_export_ops.json
│       └── zendesk_tickets.json
├── scripts/
│   ├── smoke_test.py     ← Dynamic policy change propagation test
│   └── stress_test.py    ← Resilience test (malformed input, contradictions)
├── CLAUDE.md             ← this file
└── .gitignore
```
**Note:** `backend/agents/` is empty — `brain_agent.py` lives in `backend/agent/` instead.

---

## Tech Stack

| Layer | Technology |
|---|---|
| LLM inference | vLLM serving `RedHatAI/Qwen2.5-72B-Instruct-FP8-dynamic` on AMD MI300X, port 8000 |
| LLM client | `openai` Python SDK pointed at `http://localhost:8000/v1` |
| Agent orchestration | `langgraph` with async nodes + `Send` API for parallel fan-out |
| State checkpointing | `MemorySaver` (in-memory for v0) |
| Embedding (skill matching) | `sentence-transformers` `all-MiniLM-L6-v2` in-memory, CPU |
| Web framework | `FastAPI` with `uvicorn` |
| Real-time streaming | FastAPI `StreamingResponse` with `text/event-stream` |
| Database | Supabase (Postgres) via `supabase-py` |
| File storage | Supabase Storage |

---

## LLM Client Setup

```python
from openai import AsyncOpenAI

llm = AsyncOpenAI(
    base_url="http://localhost:8000/v1",
    api_key="not-needed"
)

# All LLM calls use this pattern:
response = await llm.chat.completions.create(
    model="RedHatAI/Qwen2.5-72B-Instruct-FP8-dynamic",
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content}
    ],
    temperature=0.1,
    max_tokens=4096
)
result = response.choices[0].message.content
```

**Never use `openai.OpenAI()` — always use `AsyncOpenAI`. All nodes are async.**

---

## BrainState — The Central Data Structure

```python
from typing import TypedDict, Annotated, List, Dict, Any
import operator

class BrainState(TypedDict):
    company_id: str
    job_id: str
    source_files: Annotated[List[Dict[str, Any]], operator.add]

    structured_sops: Annotated[List[Dict[str, Any]], operator.add]
    normalized_events: Annotated[List[Dict[str, Any]], operator.add]
    resolved_cases: Annotated[List[Dict[str, Any]], operator.add]

    all_chunks: List[Dict[str, Any]]

    raw_decisions: Annotated[List[Dict[str, Any]], operator.add]
    workflow_steps: Annotated[List[Dict[str, Any]], operator.add]
    exception_rules: Annotated[List[Dict[str, Any]], operator.add]
    contradictions: Annotated[List[Dict[str, Any]], operator.add]

    draft_skills: List[Dict[str, Any]]
    skills_with_evidence: List[Dict[str, Any]]
    final_skills: List[Dict[str, Any]]

    skills_file: Dict[str, Any]
    brain_version: str
    start_time: float
    errors: Annotated[List[str], operator.add]
```

**The `Annotated[list, operator.add]` pattern is critical.** It allows multiple parallel nodes to write to the same list field without overwriting each other. Do not change this.

---

## LangGraph Architecture — Fan-Out Pattern

```python
from langgraph.graph import StateGraph
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Send

def route_to_ingestion(state: BrainState) -> list[Send]:
    """Fan out to 3 parallel ingestion nodes based on source file types."""
    sends = []
    for file in state["source_files"]:
        if file["type"] == "slack_json":
            sends.append(Send("ingest_slack", {"source_files": [file], ...}))
        elif file["type"] == "notion_md":
            sends.append(Send("ingest_notion", {"source_files": [file], ...}))
        elif file["type"] == "tickets_json":
            sends.append(Send("ingest_tickets", {"source_files": [file], ...}))
    return sends

def route_to_extraction(state: BrainState) -> list[Send]:
    """Fan out to 4 parallel extraction nodes after ingestion join."""
    return [
        Send("extract_decisions", state),
        Send("extract_workflows", state),
        Send("extract_exceptions", state),
        Send("detect_contradictions", state),
    ]

# Graph assembly:
# START → route_to_ingestion (conditional) → [ingest_slack, ingest_notion, ingest_tickets]
#       → ingest_join (barrier, waits for all) → route_to_extraction (conditional)
#       → [extract_decisions, extract_workflows, extract_exceptions, detect_contradictions]
#       → synthesize_skills → link_evidence → score_confidence → write_brain → END
```

**Never use `graph.add_edge("extractor", "synthesize_skills")` for parallel nodes — this causes synthesize_skills to fire multiple times. Always use the `Send` API + barrier join node.**

---

## Extraction Prompt Pattern

Every extraction node uses this prompt structure:

```python
SYSTEM = """You are a policy analyst. Your ONLY job is to extract {type} from company communications.
Output ONLY a JSON array. No preamble. No explanation. No markdown.
Each item must have exactly these fields: {schema}
If you find nothing, output: []
Example output: {example}"""

USER = """Extract all {type} from this company data:
{content}"""
```

- Temperature: always `0.1`
- Max tokens: `4096`
- Always wrap LLM call in try/except — on JSON parse failure, retry once with stricter prompt, then return `[]`

---

## Skills File Schema (per skill — pipeline output)

```python
{
    "id": "handle_refund_request",        # snake_case
    "category": "Customer Support",       # operational domain
    "rule": "Approve full refund for annual plans within 14 days",  # actionable rule text
    "rationale": "No-questions policy within 14 days for annual plans",
    "evidence": [
        "notion_refund_sop.md: Annual plan customers within 14 days..."
    ],
    "source_files": ["notion_refund_sop.md"],
    "confidence": 0.85,                    # 0.0 - 1.0 (scored by score_confidence node)
    "embedding_vector": [...]              # pre-computed for semantic matching
}
```

---

## Confidence Scoring Formula

```python
def score_confidence(skill: dict, contradictions: list) -> float:
    base = 0.5
    
    # More sources = higher confidence
    source_count = len(skill.get("evidence", []))
    if source_count >= 3:
        base += 0.25
    elif source_count == 2:
        base += 0.15
    elif source_count == 1:
        base += 0.05
    
    # Recency bonus (assume recent for v0)
    base += 0.15
    
    # No contradictions for this skill = higher confidence
    skill_id = skill.get("id", "")
    has_contradiction = any(
        c.get("id", "").startswith(skill_id.split("_")[0])
        or skill_id in str(c.get("domain", ""))
        for c in contradictions
    )
    if not has_contradiction:
        base += 0.10
    
    return round(min(base, 1.0), 2)
```

---

## Brain Agent Pattern

The brain agent at `backend/agent/brain_agent.py` uses:
1. **Embedding similarity** — encodes the query with `all-MiniLM-L6-v2` and scores all skills via cosine similarity
2. **Top-K retrieval** — fetches 5 best-matching skills
3. **LLM reasoning** — injects retrieved skills into the prompt with the scenario and does arithmetic threshold analysis
4. **JSON parsing** — extracts the response with a fallback for malformed JSON

Key behavior:
- Uses **pre-computed embeddings** (stored in DB by write_brain node) or computes on-the-fly
- The LLM prompt has explicit step-by-step threshold comparison logic
- Gibberish rejection: low embedding similarity → low confidence → meaningful fallback
- A/B comparison: `with_brain=True/False` to compare against a generic baseline

---

## SSE Event Bus Pattern

`backend/sse.py` uses an `asyncio.Queue` per job_id with a `CompilationEventBus` singleton. Events are unnamed (no `event:` field) — the frontend uses `EventSource.onmessage` which fires on unnamed events. Payload is wrapped: `data: {"event": "<type>", "data": {<payload>}}\n\n`.

```python
class CompilationEventBus:
    def __init__(self):
        self.queues: Dict[str, asyncio.Queue] = {}

    async def emit_event(self, job_id: str, event_type: str, data: dict):
        queue = self.get_queue(job_id)
        await queue.put({"type": event_type, "data": data})

    async def event_generator(self, job_id: str) -> AsyncGenerator[str, None]:
        queue = self.get_queue(job_id)
        while True:
            event = await asyncio.wait_for(queue.get(), timeout=300)
            payload = json.dumps({"event": event["type"], "data": event["data"]})
            yield f"data: {payload}\n\n"
            if event["type"] in ["pipeline_complete", "pipeline_error"]:
                break
```

Queue auto-cleaned in `finally` block after completion or error.

---

## Supabase Tables

```sql
-- Run these in Supabase SQL editor before starting

CREATE TABLE companies (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT now()
);

INSERT INTO companies VALUES ('rivanly-inc', 'Rivanly Inc.', now());

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

## Environment Variables

```bash
# backend/.env
VLLM_BASE_URL=http://localhost:8000/v1
SUPABASE_URL=your_supabase_project_url
SUPABASE_KEY=your_supabase_anon_key
COMPANY_ID=rivanly-inc
```

---

## API Endpoints — Full List

```
POST   /compile                    → trigger pipeline, returns {job_id, status}
POST   /compile/run                → alias for /compile
GET    /compile/{job_id}/stream    → SSE stream for live compilation progress
GET    /compile/{job_id}/status    → poll job status (started/running/complete/error)
GET    /health                     → API health + vLLM + DB status
POST   /sources/upload             → upload a source file
GET    /sources/{company_id}       → list all source files
DELETE /sources/{company_id}/{filename} → delete a source file
POST   /agent/handle               → brain agent query (legacy schema)
POST   /agent/query                → brain agent query (canonical schema)
GET    /skills                     → get current brain JSON (legacy)
GET    /skills/{company_id}        → get current brain with version + metadata
GET    /brain/versions/{company_id}→ list all compiled versions
GET    /diff/{v1}/{v2}             → semantic diff between two brain versions
```

---

## Critical Rules — Do Not Violate

1. **All LangGraph nodes must be `async def`** — sync nodes break parallelism
2. **Use `Send` API for fan-out, never direct edges between parallel nodes and their join**
3. **Never read raw source files at query time** — brain agent reads skills file only
4. **All LLM calls wrapped in try/except** — retry once on JSON parse failure, return `[]` if still failing
5. **`skills_files.is_current` enforced by partial unique index** — only one current per company
6. **`compile_runs` table is append-only** — never update rows, only insert status
7. **CORS headers on all endpoints** — frontend is on different domain
8. **Temperature 0.1 on all extraction calls** — deterministic is better than creative here

---

## Demo Company — Rivanly Inc.

The demo uses Rivanly Inc. — a fictional 15-person B2B SaaS company.

6 departments, 12 skills:

| Department | Skills |
|---|---|
| Support | handle_refund_request, respond_to_outage |
| Revenue | handle_pricing_exception, evaluate_discount_request |
| Product/Eng | prioritize_bug_report, handle_sla_breach |
| Customer Success | evaluate_churn_risk, enterprise_onboarding_steps |
| HR | hiring_process_engineering, performance_pip_trigger |
| Finance | approve_vendor_payment, expense_policy_exception |

The 8 synthetic source files in `data/sources/` are authored to produce these 12 skills when processed by the pipeline.
