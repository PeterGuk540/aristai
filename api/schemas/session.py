from pydantic import BaseModel
from typing import Optional, List, Any, Literal
from datetime import datetime
from api.schemas.base import BaseSchema


# Request schemas
class SessionCreate(BaseModel):
    course_id: int
    title: str
    date: Optional[datetime] = None


class SessionStatusUpdate(BaseModel):
    """Update session status (draft -> scheduled -> live -> completed)."""
    status: Literal["draft", "scheduled", "live", "completed"]


class SessionUpdate(BaseModel):
    """Update session details."""
    title: Optional[str] = None
    date: Optional[datetime] = None
    status: Optional[Literal["draft", "scheduled", "live", "completed"]] = None
    plan_json: Optional[Any] = None


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
