from typing import Optional, Any, List
from datetime import datetime
from api.schemas.base import BaseSchema


class InterventionResponse(BaseSchema):
    id: int
    session_id: int
    intervention_type: str
    suggestion_json: Any
    created_at: datetime
    model_name: Optional[str] = None
    prompt_version: Optional[str] = None
    evidence_post_ids: Optional[List[int]] = None

    # Observability fields (Milestone 6)
    execution_time_seconds: Optional[float] = None
    total_tokens: Optional[int] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    estimated_cost_usd: Optional[float] = None
    error_message: Optional[str] = None
    used_fallback: Optional[int] = 0
    posts_analyzed: Optional[int] = None
