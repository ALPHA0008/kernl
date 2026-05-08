"""
Node 3: For each domain cluster, call vLLM to synthesize structured skills.
Emits SSE stage: SYNTHESIZING_SKILLS
"""
import json
import uuid
from backend.graph.state import BrainState
from backend.llm import llm_call
from backend.sse import emit


async def synthesize_skills(state: BrainState) -> dict:
    job_id = state["job_id"]
    chunks = state.get("chunks", [])
    clusters = state.get("clusters", {})
    domains = clusters.get("domains", {})

    print(f"[{job_id}] Node synthesize_skills started with {len(domains)} domains")

    if not domains:
        await emit(job_id, "stage", {"name": "SYNTHESIZING_SKILLS", "detail": "No clusters to synthesize"})
        print(f"[{job_id}] Node synthesize_skills finished (0 domains)")
        return {"raw_skills": []}

    await emit(job_id, "stage", {
        "name": "SYNTHESIZING_SKILLS",
        "detail": f"Synthesizing skills for {len(domains)} domains",
    })

    all_skills = []

    for domain_name, chunk_indices in domains.items():
        # Gather the actual chunk texts for this domain
        domain_chunks = []
        for idx in chunk_indices:
            if 0 <= idx < len(chunks):
                domain_chunks.append(chunks[idx])

        if not domain_chunks:
            continue

        chunk_text = "\n\n".join([c["text"] for c in domain_chunks])
        source_files = list(set(c["source_file"] for c in domain_chunks))

        prompt = f"""You are a Principal Operations Architect analyzing the "{domain_name}" domain.

Below are real excerpts from a company's internal documents (SOPs, Slack messages, support tickets) related to {domain_name}.

Your job: extract every distinct operational rule, policy, process, or decision pattern you can find.

For EACH skill, provide:
- id: a unique identifier (use a short slug like "refund_loyal_customer")
- category: "{domain_name}"
- rule: the specific, actionable rule or process (be precise — include thresholds, timeframes, approvals)
- rationale: why this rule exists (based on the evidence)
- evidence: array of specific quotes or references from the source chunks that support this rule
- source_files: which files this came from

Rules for quality:
- Extract what the documents ACTUALLY say, not what you assume.
- If there are contradictions (e.g., SOP says X but Slack shows Y), note BOTH and state which takes precedence in practice.
- Do NOT invent rules that aren't supported by the text below.
- Each rule should be specific enough that a human could follow it without additional context.

Respond with ONLY a JSON object:
{{
  "skills": [
    {{
      "id": "refund_loyal_customer",
      "category": "{domain_name}",
      "rule": "Approve refunds up to 45 days for customers with >2 years tenure",
      "rationale": "Exception applied over standard 30-day limit for loyal customers",
      "evidence": ["slack_export_support.json: Mike approved 45-day refund for Acme Corp"],
      "source_files": ["slack_export_support.json", "notion_refund_sop.md"]
    }}
  ]
}}"""

        print(f"[{job_id}] Requesting skills for domain '{domain_name}'...")
        response_str = await llm_call(prompt, chunk_text)
        print(f"[{job_id}] Received skills response for domain '{domain_name}'")

        try:
            clean = response_str.strip()
            if clean.startswith("```json"):
                clean = clean[7:]
            if clean.startswith("```"):
                clean = clean[3:]
            if clean.endswith("```"):
                clean = clean[:-3]
            data = json.loads(clean.strip())
            domain_skills = data.get("skills", [])
        except Exception as e:
            print(f"[{job_id}] [synthesize_skills] Parse error for {domain_name}: {e}")
            domain_skills = []

        # Ensure every skill has an id
        for sk in domain_skills:
            if not sk.get("id"):
                sk["id"] = str(uuid.uuid4())[:8]
            sk["category"] = domain_name  # ensure consistency

        all_skills.extend(domain_skills)

        await emit(job_id, "stage", {
            "name": "SYNTHESIZING_SKILLS",
            "detail": f"{domain_name}: extracted {len(domain_skills)} skills",
        })

    print(f"[{job_id}] Node synthesize_skills finished (extracted {len(all_skills)} skills overall)")
    return {"raw_skills": all_skills}
