"""Pydantic schemas for Voice Assistant feature."""

from pydantic import BaseModel
from typing import Optional, List, Any, Literal
from datetime import datetime
from api.schemas.base import BaseSchema


# ---------- MCP Tool Argument Schemas ----------

class ListCoursesArgs(BaseModel):
    skip: int = 0
    limit: int = 100


class ListSessionsArgs(BaseModel):
    course_id: int


class GetSessionArgs(BaseModel):
    session_id: int


class GetReportArgs(BaseModel):
    session_id: int


class CreateCourseArgs(BaseModel):
    title: str
    syllabus_text: Optional[str] = None
    objectives_json: Optional[List[Any]] = None


class CreateSessionArgs(BaseModel):
    course_id: int
    title: str


class UpdateSessionStatusArgs(BaseModel):
    session_id: int
    status: Literal["draft", "scheduled", "live", "completed"]


class GenerateSessionPlanArgs(BaseModel):
    course_id: int


class PostCaseArgs(BaseModel):
    session_id: int
    prompt: str


class CreatePollArgs(BaseModel):
    session_id: int
    question: str
    options_json: List[str]


# ---------- Plan Schemas ----------

class PlanStep(BaseModel):
    tool_name: str
    args: dict
    mode: Literal["read", "write"]


class VoicePlan(BaseModel):
    intent: str
    steps: List[PlanStep]
    rationale: str
    required_confirmations: List[str]


# ---------- API Request Schemas ----------

class PlanRequest(BaseModel):
    transcript: str


class ExecuteRequest(BaseModel):
    plan: VoicePlan
    confirmed: bool = False


# ---------- API Response Schemas ----------

class TranscribeResponse(BaseModel):
    transcript: str
    language: Optional[str] = None
    duration_seconds: Optional[float] = None


class PlanResponse(BaseModel):
    plan: VoicePlan
    transcript: str


class StepResult(BaseModel):
    tool_name: str
    success: bool
    result: Optional[Any] = None
    error: Optional[str] = None
    skipped: bool = False
    skipped_reason: Optional[str] = None


class ExecuteResponse(BaseModel):
    results: List[StepResult]
    summary: str
    audio_url: Optional[str] = None


class VoiceAuditResponse(BaseSchema):
    id: int
    user_id: int
    transcript_hash: str
    plan_json: dict
    tool_calls: Optional[List[dict]] = None
    created_at: datetime


class VoiceAuditListResponse(BaseModel):
    audits: List[VoiceAuditResponse]
    total: int
