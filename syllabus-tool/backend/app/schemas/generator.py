from pydantic import BaseModel
from typing import Optional, Literal

class GenerateRequest(BaseModel):
    course_title: str
    target_audience: str
    duration: str  # e.g. "16 weeks", "one semester"
    reference_file_id: Optional[int] = None


class FillTemplateRequest(BaseModel):
    reference_file_id: int
    course_title: str
    target_audience: str = ""
    duration: str = ""


class FillTemplateJobResponse(BaseModel):
    job_id: str


class FillTemplateStatusResponse(BaseModel):
    status: Literal["pending", "running", "completed", "failed"]
    result: Optional[dict] = None          # {filled_text, paragraph_map, original_file_id} when completed
    error: Optional[str] = None


class FillTemplateResponse(BaseModel):
    filled_text: str                       # complete generated text for preview/editing
    paragraph_map: dict[str, str]          # {"0": "text", "1": "text", ...} for DOCX export
    original_file_id: int


class FilledTemplateExportRequest(BaseModel):
    file_id: int
    paragraph_map: dict[str, str]          # edited paragraph map from frontend
