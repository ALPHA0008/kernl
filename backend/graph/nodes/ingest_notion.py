from backend.graph.state import BrainState
from backend.sse import emit


async def ingest_notion(state: BrainState) -> dict:
    job_id = state["job_id"]
    source_files = state.get("source_files", [])

    notion_files = [f for f in source_files if f.get("doc_type") == "notion_md"]
    print(f"[{job_id}] Node ingest_notion: {len(notion_files)} notion files")

    structured_sops = []
    for sf in notion_files:
        chunks = _chunk_markdown(sf)
        structured_sops.extend(chunks)

    await emit(
        job_id,
        "stage",
        {
            "name": "INGEST_NOTION",
            "detail": f"Processed {len(notion_files)} SOP files into {len(structured_sops)} chunks",
        },
    )
    print(f"[{job_id}] ingest_notion finished: {len(structured_sops)} chunks")
    return {"structured_sops": structured_sops}


def _chunk_markdown(sf: dict) -> list:
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
        chunks.append(
            {
                "text": f"[{header}] {body}",
                "source_file": sf["filename"],
                "chunk_index": i,
                "doc_type": "notion_md",
                "section_header": header,
            }
        )
    return chunks
