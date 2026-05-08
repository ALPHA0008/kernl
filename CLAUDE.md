# Company Brain — CLAUDE.md
## Project context for AI coding assistants

---

## What This Project Is

Company Brain is a multi-agent compilation pipeline that extracts operational decision knowledge from company data sources (Slack, Notion SOPs, support tickets) and compiles it into a versioned, evidence-linked, executable skills file. A downstream brain agent uses this skills file to handle operational scenarios correctly — acting like the company's best employee.

**The core thesis:** Agents are compilers, not assistants. We don't search raw documents. We compile tribal knowledge into structured, executable logic once. Then we read the compiled output forever.

---

## Monorepo Structure

```
company-brain/
├── backend/              ← FastAPI + LangGraph pipeline (Python)
│   ├── main.py           ← FastAPI app entry point
│   ├── graph/
│   │   ├── state.py      ← BrainState TypedDict
│   │   ├── nodes/        ← one file per LangGraph node
│   │   │   ├── ingest_slack.py
│   │   │   ├── ingest_notion.py
│   │   │   ├── ingest_tickets.py
│   │   │   ├── ingest_join.py
│   │   │   ├── extract_decisions.py
│   │   │   ├── extract_workflows.py
│   │   │   ├── extract_exceptions.py
│   │   │   ├── detect_contradictions.py
│   │   │   ├── synthesize_skills.py
│   │   │   ├── link_evidence.py
│   │   │   ├── score_confidence.py
│   │   │   └── write_brain.py
│   │   └── graph.py      ← graph assembly + compile
│   ├── agents/
│   │   └── brain_agent.py ← query-time brain agent
│   ├── db/
│   │   └── supabase.py   ← Supabase client + queries
│   ├── models/
│   │   └── schemas.py    ← Pydantic models for API
│   └── requirements.txt
├── frontend/             ← Next.js 14 + Tailwind (Harshit)
├── data/
│   └── sources/          ← 8 synthetic source files
│       ├── notion_refund_sop.md
│       ├── notion_pricing_policy.md
│       ├── notion_eng_runbook.md
│       ├── notion_hr_playbook.md
│       ├── notion_cs_playbook.md
│       ├── slack_export_support.json
│       ├── slack_export_ops.json
│       └── zendesk_tickets.json
└── CLAUDE.md             ← this file
```

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
from typing import TypedDict, Annotated
import operator

class BrainState(TypedDict):
    company_id: str
    source_files: list[dict]          # [{filename, content, sha256, type}]
    
    # Ingestion outputs (parallel, accumulated with operator.add)
    normalized_events: Annotated[list[dict], operator.add]    # from Slack
    structured_sops: Annotated[list[dict], operator.add]      # from Notion
    resolved_cases: Annotated[list[dict], operator.add]       # from tickets
    
    # Extraction outputs (parallel, accumulated with operator.add)
    raw_decisions: Annotated[list[dict], operator.add]
    workflow_steps: Annotated[list[dict], operator.add]
    exception_rules: Annotated[list[dict], operator.add]
    contradictions: Annotated[list[dict], operator.add]
    
    # Compilation outputs (sequential)
    draft_skills: list[dict]
    skills_with_evidence: list[dict]
    final_skills: list[dict]
    
    # Metadata
    job_id: str
    brain_version: str
    errors: Annotated[list[str], operator.add]
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

## Skills File Schema (per skill)

```python
{
    "id": "handle_refund_request",          # snake_case
    "name": "Handle Refund Request",         # human readable
    "domain": "support",                     # support|revenue|product_eng|customer_success|hr|finance_ops
    "version": "1.0",
    "confidence": 0.91,                      # 0.0 - 1.0
    "stale": False,
    "review_required": False,                # True if confidence < 0.6
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
                {
                    "source": "notion_refund_sop.md",
                    "excerpt": "Annual plan customers within 14 days...",
                    "confidence": 0.95
                }
            ]
        }
    ],
    "forbidden_actions": [
        "Never process refunds for lifetime deal accounts"
    ],
    "escalation_chain": ["support_agent", "support_lead", "account_manager", "founder"],
    "sla": "respond_within_2h, resolve_within_24h"
}
```

---

## Confidence Scoring Formula

```python
def score_confidence(skill: dict, all_sources: list[dict]) -> float:
    base = 0.5
    
    # More sources = higher confidence
    source_count = len(skill["decision_logic"][0].get("evidence_sources", []))
    if source_count >= 3:
        base += 0.25
    elif source_count == 2:
        base += 0.15
    elif source_count == 1:
        base += 0.05
    
    # Recent sources = higher confidence
    # (check source file last_modified if available)
    base += 0.15  # assume recent for v0
    
    # No contradictions for this skill = higher confidence
    # (passed in from contradiction detector)
    has_contradiction = False  # check contradictions list
    if not has_contradiction:
        base += 0.10
    
    return min(base, 1.0)
```

---

## Brain Agent Pattern

```python
from sentence_transformers import SentenceTransformer
import numpy as np

# Load once at startup
embedder = SentenceTransformer('all-MiniLM-L6-v2')

# Pre-compute skill embeddings (call after compile)
skill_embeddings = {}  # {skill_id: np.array}

def compute_skill_embeddings(skills: list[dict]):
    global skill_embeddings
    for skill in skills:
        text = f"{skill['name']} {' '.join(skill['trigger']['phrases'])}"
        skill_embeddings[skill['id']] = embedder.encode(text)

def match_skill(query: str) -> tuple[str, float]:
    query_emb = embedder.encode(query)
    scores = {}
    for skill_id, emb in skill_embeddings.items():
        score = float(np.dot(query_emb, emb) / 
                     (np.linalg.norm(query_emb) * np.linalg.norm(emb)))
        scores[skill_id] = score
    best_id = max(scores, key=scores.get)
    return best_id, scores[best_id]

def skill_to_markdown(skill: dict) -> str:
    """Convert skill JSON to markdown for prompt injection."""
    lines = [f"## {skill['name']}", ""]
    for logic in skill['decision_logic']:
        lines.append(f"- IF {logic['condition']}: {logic['action']}")
        if logic.get('note'):
            lines.append(f"  Note: {logic['note']}")
    lines.append("")
    lines.append("FORBIDDEN: " + "; ".join(skill['forbidden_actions']))
    lines.append("ESCALATE: " + " → ".join(skill['escalation_chain']))
    return "\n".join(lines)
```

---

## FastAPI SSE Pattern

```python
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
import asyncio
import json

async def event_generator(job_id: str):
    """Yields SSE events during compilation."""
    async for event in compilation_events[job_id]:
        yield f"event: {event['type']}\ndata: {json.dumps(event['data'])}\n\n"

@app.get("/compile/stream")
async def stream_compile(job_id: str):
    return StreamingResponse(
        event_generator(job_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*"  # CORS for frontend
        }
    )
```

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

CREATE UNIQUE INDEX idx_one_current_per_company 
  ON skills_files(company_id) WHERE is_current = true;

CREATE TABLE compile_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id TEXT REFERENCES companies(id),
  status TEXT CHECK (status IN ('started','running','complete','error')),
  started_at TIMESTAMPTZ DEFAULT now(),
  completed_at TIMESTAMPTZ,
  duration_ms INTEGER,
  result_version TEXT,
  error_detail TEXT
);

CREATE TABLE source_files (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id TEXT REFERENCES companies(id),
  filename TEXT NOT NULL,
  sha256 TEXT NOT NULL,
  content TEXT NOT NULL,
  source_type TEXT CHECK (source_type IN ('slack_json','notion_md','tickets_json')),
  uploaded_at TIMESTAMPTZ DEFAULT now()
);
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
POST /compile              → trigger pipeline, returns {job_id, stream_url}
GET  /compile/stream       → SSE stream for job_id
GET  /brain/status         → current brain version + stats
GET  /skills               → all skills (lightweight)
GET  /skills/{id}          → full skill detail
POST /agent/handle         → brain agent query
GET  /diff/{v1}/{v2}       → version diff
POST /sources/upload       → upload source files
```

---

## Critical Rules — Do Not Violate

1. **All LangGraph nodes must be `async def`** — sync nodes break parallelism
2. **Use `Send` API for fan-out, never direct edges between parallel nodes and their join**
3. **Never read raw source files at query time** — brain agent reads skills file only
4. **All LLM calls wrapped in try/except** — retry once on JSON parse failure, return `[]` if still failing
5. **`skills_files.is_current` enforced by partial unique index** — only one current per company
6. **`compile_runs` table is append-only** — never update rows, only insert
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
