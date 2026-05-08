import asyncio
import os
import json
import uuid
import sys
from dotenv import load_dotenv

# Set backend in path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from backend.graph.graph import build_compilation_graph

async def run_compilation_test():
    load_dotenv()
    
    # Check vLLM
    vllm_url = os.getenv("VLLM_BASE_URL")
    if not vllm_url:
        print("VLLM_BASE_URL not set in .env. LLM calls will fail.")
    else:
        print(f"Using VLLM_BASE_URL: {vllm_url}")

    company_id = "rivanly-inc"
    job_id = str(uuid.uuid4())
    
    # Read files
    source_files = []
    sources_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "sources")
    if os.path.exists(sources_dir):
        import hashlib
        for filename in os.listdir(sources_dir):
            filepath = os.path.join(sources_dir, filename)
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            
            ftype = "unknown"
            if filename.endswith(".json"):
                if "slack" in filename: ftype = "slack_json"
                elif "tickets" in filename: ftype = "tickets_json"
            elif filename.endswith(".md"):
                ftype = "notion_md"
                
            source_files.append({
                "filename": filename,
                "content": content,
                "type": ftype,
                "sha256": hashlib.sha256(content.encode('utf-8')).hexdigest()
            })
    else:
        print(f"No sources dir found at {sources_dir}")
        return

    print(f"Found {len(source_files)} source files. Starting graph...")
    
    initial_state = {
        "job_id": job_id,
        "company_id": company_id,
        "source_files": source_files,
        "structured_sops": [],
        "normalized_events": [],
        "resolved_cases": [],
        "extracted_decisions": [],
        "extracted_workflows": [],
        "extracted_exceptions": [],
        "detected_contradictions": [],
        "skills_file": {}
    }
    
    graph = build_compilation_graph()
    
    try:
        final_state = await graph.ainvoke(initial_state)
        print("\n=== COMPILATION COMPLETE ===")
        print(f"Extracted Decisions: {len(final_state.get('extracted_decisions', []))}")
        print(f"Detected Contradictions: {len(final_state.get('detected_contradictions', []))}")
        for c in final_state.get('detected_contradictions', []):
            print(f"  - Contradiction: {c}")
            
        skills_file = final_state.get('skills_file', {})
        skills = skills_file.get('skills', [])
        print(f"Generated Skills: {len(skills)}")
        for s in skills:
            print(f"  - {s.get('id')} ({s.get('confidence')} conf)")
            
    except Exception as e:
        print(f"Graph execution failed: {e}")

if __name__ == "__main__":
    asyncio.run(run_compilation_test())
