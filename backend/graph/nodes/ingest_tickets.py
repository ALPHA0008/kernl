import json
from backend.graph.state import BrainState
from backend.sse import emit


async def ingest_tickets(state: BrainState) -> dict:
    job_id = state["job_id"]
    source_files = state.get("source_files", [])

    ticket_files = [f for f in source_files if f.get("doc_type") == "tickets_json"]
    print(f"[{job_id}] Node ingest_tickets: {len(ticket_files)} ticket files")

    resolved_cases = []
    for sf in ticket_files:
        chunks = _chunk_tickets(sf)
        resolved_cases.extend(chunks)

    await emit(
        job_id,
        "stage",
        {
            "name": "INGEST_TICKETS",
            "detail": f"Processed {len(ticket_files)} ticket files into {len(resolved_cases)} cases",
        },
    )
    print(f"[{job_id}] ingest_tickets finished: {len(resolved_cases)} tickets")
    return {"resolved_cases": resolved_cases}


def _chunk_tickets(sf: dict) -> list:
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
        chunks.append(
            {
                "text": f"[Zendesk Ticket] {text}",
                "source_file": sf["filename"],
                "chunk_index": i,
                "doc_type": "tickets_json",
            }
        )
    return chunks
