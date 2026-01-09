from typing import Optional, Any, List
from datetime import datetime
from app.schemas.base import BaseSchema


class InterventionResponse(BaseSchema):
    id: int
    session_id: int
    intervention_type: str
    suggestion_json: Any
    created_at: datetime
    model_name: Optional[str] = None
    prompt_version: Optional[str] = None
    evidence_post_ids: Optional[List[int]] = None
