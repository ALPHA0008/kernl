from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from backend.v1_api import router as v1_router

app = FastAPI(title="Kernl API", version="3.0.0")
app.include_router(v1_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Legacy surface (pre-V1) -- fully retired 2026-07-16.
#
# api.py used to mount the whole pre-ledger pipeline: unauthenticated source
# upload, an LLM compile graph writing straight to a `skills_files` blob, a
# skills marketplace, and a semantic diff engine. None of it is called by
# anything in this repo (verified: no HTTP caller, no direct Python import
# outside the legacy eval harness and a diagnostics script, both of which
# import backend.engine/backend.runtime.brain_agent directly and never went
# through this HTTP surface). It predates the bundle/ledger/replay model and
# every one of its endpoints was reachable with zero auth -- upload, delete,
# and LLM-trigger, wide open.
#
# It's retired here rather than just left alone for two concrete reasons:
#   1. Security: no other endpoint in this app is unauthenticated; leaving
#      these live means part of the API surface silently isn't ledgered or
#      gated the way the constitutional rules (CLAUDE.md) require for
#      anything that can produce or store norms.
#   2. Reliability: backend.engine.graph eagerly imported the LLM extraction
#      chain (langgraph -> transformers -> sklearn -> pandas -> numpy). A
#      single ABI mismatch anywhere in that chain took the ENTIRE server
#      down at import time, including /v1, which needs none of it. Retiring
#      these routes removes the eager import, so a broken legacy dependency
#      can no longer take the ledger offline.
#
# The underlying modules (backend/engine/, backend/core/llm.py,
# backend/runtime/brain_agent.py) are untouched and still directly
# importable -- backend/tests/eval_harness.py and
# .agents/skills/kernl-diagnostics-and-tooling/scripts/brain_audit.py still
# use them as library code for historical/diagnostic runs. Only the live,
# unauthenticated HTTP surface is gone.
_RETIRED_LEGACY_ROUTES: dict[str, str] = {
    "/health": "GET",
    "/sources/upload": "POST",
    "/sources/{company_id}": "GET",
    "/sources/{company_id}/{filename}": "DELETE",
    "/compile": "POST",
    "/compile/run": "POST",
    "/compile/{job_id}/stream": "GET",
    "/compile/{job_id}/status": "GET",
    "/agent/handle": "POST",
    "/agent/query": "POST",
    "/skills": "GET",
    "/skills/{company_id}": "GET",
    "/skills/{company_id}/download": "GET",
    "/skills/import": "POST",
    "/brain/versions/{company_id}": "GET",
    "/diff/{v1}/{v2}": "GET",
}

_RETIREMENT = {
    "error": "gone",
    "detail": (
        "This endpoint is retired. The pre-ledger compile/skills/agent "
        "surface has been fully decommissioned. Use the /v1 API: "
        "GET /v1/health, POST /v1/onboarding/* + /v1/bundles/{id}/publish "
        "for authoring, POST /v1/decisions/evaluate for decisions "
        "(X-API-Key required)."
    ),
}


async def _gone(_request: Request):
    return _RETIREMENT


for _path, _method in _RETIRED_LEGACY_ROUTES.items():
    app.api_route(_path, methods=[_method], status_code=410)(_gone)
