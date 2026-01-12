from typing import Optional, Any
from datetime import datetime
from api.schemas.base import BaseSchema


class ReportResponse(BaseSchema):
    id: int
    session_id: int
    version: str
    report_md: Optional[str] = None
    report_json: Optional[Any] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    model_name: Optional[str] = None
    prompt_version: Optional[str] = None

    # Observability fields (Milestone 6)
    execution_time_seconds: Optional[float] = None
    total_tokens: Optional[int] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    estimated_cost_usd: Optional[float] = None
    error_message: Optional[str] = None
    retry_count: Optional[int] = 0
    used_fallback: Optional[int] = 0
