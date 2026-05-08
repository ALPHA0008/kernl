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
