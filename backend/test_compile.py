import asyncio
import os
import json
import uuid
import sys
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from backend.graph.graph import build_compilation_graph


async def run_compilation_test():
    load_dotenv()

    vllm_url = os.getenv("VLLM_BASE_URL")
    if not vllm_url:
        print("VLLM_BASE_URL not set in .env. LLM calls will fail.")
    else:
        print(f"Using VLLM_BASE_URL: {vllm_url}")

    company_id = "rivanly-inc"
    job_id = str(uuid.uuid4())

    source_files = []
    sources_dir = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "data", "sources"
    )
    if os.path.exists(sources_dir):
        import hashlib

        for filename in os.listdir(sources_dir):
            filepath = os.path.join(sources_dir, filename)
            if os.path.isfile(filepath):
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()
                ftype = "unknown"
                if filename.endswith(".json"):
                    if "slack" in filename:
                        ftype = "slack_json"
                    elif "tickets" in filename:
                        ftype = "tickets_json"
                elif filename.endswith(".md"):
                    ftype = "notion_md"
                source_files.append(
                    {
                        "filename": filename,
                        "content": content,
                        "type": ftype,
                        "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
                    }
                )
    else:
        print(f"No sources dir found at {sources_dir}")
        return

    print(
        f"Found {len(source_files)} source files. Starting parallel multi-agent graph..."
    )

    initial_state = {
        "job_id": job_id,
        "company_id": company_id,
        "source_files": [],  # load_sources reads from disk
        "structured_sops": [],
        "normalized_events": [],
        "resolved_cases": [],
        "all_chunks": [],
        "raw_decisions": [],
        "workflow_steps": [],
        "exception_rules": [],
        "contradictions": [],
        "draft_skills": [],
        "skills_with_evidence": [],
        "final_skills": [],
        "skills_file": {},
        "brain_version": "",
        "start_time": __import__("time").time(),
        "errors": [],
    }

    graph = build_compilation_graph()

    try:
        final_state = await graph.ainvoke(initial_state)
        print("\n=== COMPILATION COMPLETE ===")

        raw_decisions = final_state.get("raw_decisions", [])
        workflow_steps = final_state.get("workflow_steps", [])
        exception_rules = final_state.get("exception_rules", [])
        contradictions = final_state.get("contradictions", [])

        print(f"Raw Decisions: {len(raw_decisions)}")
        print(f"Workflow Steps: {len(workflow_steps)}")
        print(f"Exception Rules: {len(exception_rules)}")
        print(f"Contradictions: {len(contradictions)}")

        for c in contradictions:
            print(
                f"  - Contradiction: {c.get('claim_a', '')[:80]} vs {c.get('claim_b', '')[:80]}"
            )

        final_skills = final_state.get("final_skills", [])
        print(f"\nFinal Skills: {len(final_skills)}")
        for s in final_skills:
            print(
                f"  - {s.get('id')} ({s.get('confidence')} conf) [{s.get('category')}]"
            )
            print(f"    Rule: {s.get('rule', '')[:100]}")
            ev = s.get("evidence", [])
            if ev:
                print(f"    Evidence: {len(ev)} sources")

        skills_file = final_state.get("skills_file", {})
        if skills_file:
            print(
                f"\nBrain version: {skills_file.get('meta', {}).get('compiled_at', 'N/A')}"
            )

    except Exception as e:
        print(f"Graph execution failed: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(run_compilation_test())
