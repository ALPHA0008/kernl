from pydantic import BaseModel
from typing import List, Optional, Dict, Any


class CompileRequest(BaseModel):
    company_id: str
    force_recompile: bool = False


class AgentHandleRequest(BaseModel):
    """Legacy schema — kept for frontend compatibility."""

    company_id: str
    scenario: str
    context: Optional[Dict[str, Any]] = None
    with_brain: bool = True


class AgentQueryRequest(BaseModel):
    """New canonical schema for agent queries."""

    company_id: str
    scenario_text: str
    json_context: Optional[Dict[str, Any]] = None
    with_brain: bool = True


class DiffRequest(BaseModel):
    version_v1: str
    version_v2: str
    company_id: str


class DiffItem(BaseModel):
    id: str
    name: str = ""


class DiffModified(BaseModel):
    id: str
    field: str
    old_value: Any = None
    new_value: Any = None


class DiffConfidenceShift(BaseModel):
    id: str
    old_confidence: float = 0.0
    new_confidence: float = 0.0
    reason: str = ""


class DiffResponse(BaseModel):
    v1_version: str
    v2_version: str
    added: List[DiffItem] = []
    deleted: List[DiffItem] = []
    modified: List[DiffModified] = []
    confidence_shifts: List[DiffConfidenceShift] = []



# ─────────────────────────────────────────────
# Skills Marketplace
# ─────────────────────────────────────────────


class SkillsImportRequest(BaseModel):
    company_id: str
    version: str = "imported"
    skills: List[Dict[str, Any]]
    source_label: str = "marketplace_import"
