from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime
from app.schemas.base import BaseSchema


# Request schemas
class SessionCreate(BaseModel):
    course_id: int
    title: str
    date: Optional[datetime] = None


class CaseCreate(BaseModel):
    prompt: str
    attachments: Optional[List[str]] = None


# Response schemas
class CaseResponse(BaseSchema):
    id: int
    session_id: int
    prompt: str
    attachments: Optional[List[str]] = None
    created_at: datetime


class SessionResponse(BaseSchema):
    id: int
    course_id: int
    title: str
    date: Optional[datetime] = None
    status: str
    plan_version: Optional[str] = None
    plan_json: Optional[Any] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    model_name: Optional[str] = None
    prompt_version: Optional[str] = None
