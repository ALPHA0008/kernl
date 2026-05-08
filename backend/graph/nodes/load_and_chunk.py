"""
Node 1: Load source files from disk and chunk them.
Emits SSE stages: LOADING_DOCS, CHUNKING
"""
import os
import json
import hashlib
import time
from backend.graph.state import BrainState
from backend.sse import emit


async def load_and_chunk(state: BrainState) -> dict:
    company_id = state["company_id"]
    job_id = state["job_id"]

    print(f"[{job_id}] Node load_and_chunk started")
    await emit(job_id, "stage", {"name": "LOADING_DOCS", "detail": f"Reading sources for {company_id}"})

    # Read files from the company-specific directory
    # __file__ is backend/graph/nodes/load_and_chunk.py
    base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    sources_dir = os.path.join(base, "data", "sources", company_id)

    if not os.path.isdir(sources_dir):
        await emit(job_id, "pipeline_error", {"error": f"No source directory found: data/sources/{company_id}/"})
        print(f"[{job_id}] Node load_and_chunk failed (Missing dir: {sources_dir})")
        return {"errors": [f"Missing directory: {sources_dir}"], "source_files": [], "chunks": []}

    source_files = []
    for filename in sorted(os.listdir(sources_dir)):
        filepath = os.path.join(sources_dir, filename)
        if not os.path.isfile(filepath):
            continue
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        doc_type = _detect_type(filename)
        source_files.append({
            "filename": filename,
            "content": content,
            "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
            "doc_type": doc_type,
        })

    await emit(job_id, "stage", {
        "name": "CHUNKING",
        "detail": f"Splitting {len(source_files)} files into chunks",
    })

    chunks = []
    for sf in source_files:
        if sf["doc_type"] == "notion_md":
            chunks.extend(_chunk_markdown(sf))
        elif sf["doc_type"] == "slack_json":
            chunks.extend(_chunk_slack(sf))
        elif sf["doc_type"] == "tickets_json":
            chunks.extend(_chunk_tickets(sf))
        else:
            # Treat unknown as plain text
            chunks.append({
                "text": sf["content"],
                "source_file": sf["filename"],
                "chunk_index": 0,
                "doc_type": sf["doc_type"],
            })

    await emit(job_id, "stage", {
        "name": "CHUNKING_DONE",
        "detail": f"Produced {len(chunks)} chunks from {len(source_files)} files",
    })

    print(f"[{job_id}] Node load_and_chunk finished (chunks: {len(chunks)})")
    return {"source_files": source_files, "chunks": chunks}


# --- Helpers ---

def _detect_type(filename: str) -> str:
    fn = filename.lower()
    if fn.endswith(".json"):
        if "slack" in fn:
            return "slack_json"
        if "ticket" in fn or "zendesk" in fn:
            return "tickets_json"
        return "json"
    if fn.endswith(".md"):
        return "notion_md"
    return "unknown"


def _chunk_markdown(sf: dict) -> list:
    """Split a markdown file by ## headers. Each section is a chunk."""
    content = sf["content"]
    sections = []
    current_header = "Introduction"
    current_body = []

    for line in content.split("\n"):
        if line.startswith("## "):
            if current_body:
                sections.append((current_header, "\n".join(current_body).strip()))
            current_header = line.lstrip("# ").strip()
            current_body = []
        else:
            current_body.append(line)

    if current_body:
        sections.append((current_header, "\n".join(current_body).strip()))

    chunks = []
    for i, (header, body) in enumerate(sections):
        if not body:
            continue
        chunks.append({
            "text": f"[{header}] {body}",
            "source_file": sf["filename"],
            "chunk_index": i,
            "doc_type": "notion_md",
            "section_header": header,
        })
    return chunks


def _chunk_slack(sf: dict) -> list:
    """Each Slack message is one chunk."""
    try:
        messages = json.loads(sf["content"])
    except json.JSONDecodeError:
        return []
    chunks = []
    for i, msg in enumerate(messages):
        text = msg.get("text", "")
        if not text:
            continue
        user = msg.get("user", "unknown")
        channel = msg.get("channel", "unknown")
        chunks.append({
            "text": f"[Slack #{channel} @{user}] {text}",
            "source_file": sf["filename"],
            "chunk_index": i,
            "doc_type": "slack_json",
        })
    return chunks


def _chunk_tickets(sf: dict) -> list:
    """Each ticket is one chunk."""
    try:
        tickets = json.loads(sf["content"])
    except json.JSONDecodeError:
        return []
    chunks = []
    for i, tkt in enumerate(tickets):
        parts = []
        if tkt.get("subject"):
            parts.append(f"Subject: {tkt['subject']}")
        if tkt.get("description"):
            parts.append(f"Description: {tkt['description']}")
        if tkt.get("resolution"):
            parts.append(f"Resolution: {tkt['resolution']}")
        if tkt.get("priority"):
            parts.append(f"Priority: {tkt['priority']}")
        if tkt.get("customer_plan"):
            parts.append(f"Plan: {tkt['customer_plan']}")
        text = " | ".join(parts)
        if not text:
            continue
        chunks.append({
            "text": f"[Zendesk Ticket] {text}",
            "source_file": sf["filename"],
            "chunk_index": i,
            "doc_type": "tickets_json",
        })
    return chunks
