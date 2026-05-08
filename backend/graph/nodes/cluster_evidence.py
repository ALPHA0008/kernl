"""
Node 2: Embed all chunks and cluster them by domain using the LLM.
Emits SSE stage: EMBEDDING
"""
import json
from backend.graph.state import BrainState
from backend.llm import llm_call, get_embeddings
from backend.sse import emit


async def cluster_evidence(state: BrainState) -> dict:
    job_id = state["job_id"]
    chunks = state.get("chunks", [])

    print(f"[{job_id}] Node cluster_evidence started with {len(chunks)} chunks")

    if not chunks:
        await emit(job_id, "stage", {"name": "EMBEDDING", "detail": "No chunks to embed"})
        return {"clusters": {"domains": {}}}

    await emit(job_id, "stage", {"name": "EMBEDDING", "detail": f"Embedding {len(chunks)} chunks"})

    # Build a numbered summary of each chunk for the LLM
    summaries = []
    for i, c in enumerate(chunks):
        # Truncate long chunks for the categorization prompt
        preview = c["text"][:300].replace("\n", " ")
        summaries.append(f"[{i}] ({c['source_file']}) {preview}")

    chunk_list_text = "\n".join(summaries)

    prompt = """You are an operations analyst. Below is a numbered list of text chunks extracted from a company's internal documents (SOPs, Slack messages, support tickets).

Categorize each chunk into an operational domain. Use clear domain names like:
"Customer Support", "Engineering", "Sales", "Human Resources", "Finance", "Operations", etc.

Return ONLY a valid JSON object mapping domain names to arrays of chunk indices.
Example: {"Customer Support": [0, 3, 5], "Engineering": [1, 2], "Sales": [4]}

Every chunk index must appear exactly once. Do not skip any."""

    response_str = await llm_call(prompt, chunk_list_text)

    try:
        clean = response_str.strip()
        if clean.startswith("```json"):
            clean = clean[7:]
        if clean.startswith("```"):
            clean = clean[3:]
        if clean.endswith("```"):
            clean = clean[:-3]
        domains = json.loads(clean.strip())
    except Exception as e:
        print(f"[cluster_evidence] Failed to parse LLM clustering: {e}")
        # Fallback: put all chunks in one cluster
        domains = {"General": list(range(len(chunks)))}

    await emit(job_id, "stage", {
        "name": "EMBEDDING_DONE",
        "detail": f"Clustered into {len(domains)} domains: {list(domains.keys())}",
    })

    print(f"[{job_id}] Node cluster_evidence finished with {len(domains)} domains")
    return {"clusters": {"domains": domains}}
