from backend.graph.state import BrainState
from backend.chunking import get_chunker
from backend.sse import emit


async def chunk_documents(state: BrainState) -> dict:
    job_id = state["job_id"]
    source_files = state.get("source_files", [])

    print(f"[{job_id}] Node chunk_documents: processing {len(source_files)} files")
    await emit(
        job_id,
        "stage",
        {
            "name": "CHUNKING",
            "detail": f"Chunking {len(source_files)} source files",
        },
    )

    all_chunks = []
    for sf in source_files:
        doc_type = sf.get("doc_type", "plain_text")
        filename = sf.get("filename", "unknown")
        content = sf.get("content", "")
        chunker = get_chunker(doc_type)
        chunks = chunker(content, filename)
        all_chunks.extend(chunks)

    print(
        f"[{job_id}] chunk_documents: produced {len(all_chunks)} chunks from {len(source_files)} files"
    )
    await emit(
        job_id,
        "stage",
        {
            "name": "CHUNKING_DONE",
            "detail": f"Produced {len(all_chunks)} chunks from {len(source_files)} files",
        },
    )

    return {"all_chunks": all_chunks}
