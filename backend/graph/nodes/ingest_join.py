from backend.graph.state import BrainState
from backend.sse import emit


async def ingest_join(state: BrainState) -> dict:
    job_id = state["job_id"]

    structured_sops = state.get("structured_sops", [])
    normalized_events = state.get("normalized_events", [])
    resolved_cases = state.get("resolved_cases", [])

    all_chunks = []
    all_chunks.extend(structured_sops)
    all_chunks.extend(normalized_events)
    all_chunks.extend(resolved_cases)

    print(
        f"[{job_id}] Node ingest_join: merged {len(structured_sops)} SOPs + {len(normalized_events)} events + {len(resolved_cases)} tickets = {len(all_chunks)} chunks"
    )

    await emit(
        job_id,
        "stage",
        {
            "name": "INGEST_JOIN",
            "detail": f"Merged {len(all_chunks)} total chunks from all sources",
        },
    )
    return {"all_chunks": all_chunks}
