import json
from backend.graph.state import BrainState
from backend.sse import emit


async def ingest_slack(state: BrainState) -> dict:
    job_id = state["job_id"]
    source_files = state.get("source_files", [])

    slack_files = [f for f in source_files if f.get("doc_type") == "slack_json"]
    print(f"[{job_id}] Node ingest_slack: {len(slack_files)} slack files")

    normalized_events = []
    for sf in slack_files:
        chunks = _chunk_slack(sf)
        normalized_events.extend(chunks)

    await emit(
        job_id,
        "stage",
        {
            "name": "INGEST_SLACK",
            "detail": f"Processed {len(slack_files)} Slack exports into {len(normalized_events)} messages",
        },
    )
    print(f"[{job_id}] ingest_slack finished: {len(normalized_events)} messages")
    return {"normalized_events": normalized_events}


def _chunk_slack(sf: dict) -> list:
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
        chunks.append(
            {
                "text": f"[Slack #{channel} @{user}] {text}",
                "source_file": sf["filename"],
                "chunk_index": i,
                "doc_type": "slack_json",
            }
        )
    return chunks
