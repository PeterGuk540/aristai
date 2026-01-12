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
