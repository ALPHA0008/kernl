from typing import TypedDict, Annotated, List, Dict, Any
import operator


class BrainState(TypedDict):
    company_id: str
    job_id: str
    source_files: Annotated[List[Dict[str, Any]], operator.add]

    structured_sops: Annotated[List[Dict[str, Any]], operator.add]
    normalized_events: Annotated[List[Dict[str, Any]], operator.add]
    resolved_cases: Annotated[List[Dict[str, Any]], operator.add]

    all_chunks: List[Dict[str, Any]]

    raw_decisions: Annotated[List[Dict[str, Any]], operator.add]
    workflow_steps: Annotated[List[Dict[str, Any]], operator.add]
    exception_rules: Annotated[List[Dict[str, Any]], operator.add]
    contradictions: Annotated[List[Dict[str, Any]], operator.add]

    draft_skills: List[Dict[str, Any]]
    skills_with_evidence: List[Dict[str, Any]]
    final_skills: List[Dict[str, Any]]

    skills_file: Dict[str, Any]
    brain_version: str
    start_time: float
    errors: Annotated[List[str], operator.add]
