from typing import TypedDict, Annotated, List, Dict, Any
import operator

class BrainState(TypedDict):
    company_id: str
    job_id: str
    source_files: List[Dict[str, Any]]   # [{filename, content, sha256, doc_type}]
    chunks: List[Dict[str, Any]]         # [{text, source_file, chunk_index, doc_type}]
    clusters: Dict[str, Any]             # {domains: {domain_name: [chunk_indices]}}
    raw_skills: List[Dict[str, Any]]     # skills before quality pass
    skills_file: Dict[str, Any]          # final {skills: [...]}
    brain_version: str
    start_time: float
    errors: Annotated[List[str], operator.add]
