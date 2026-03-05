from pydantic import BaseModel
from typing import Optional

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


class FillTemplateResponse(BaseModel):
    filled_text: str                       # complete generated text for preview/editing
    paragraph_map: dict[str, str]          # {"0": "text", "1": "text", ...} for DOCX export
    original_file_id: int


class FilledTemplateExportRequest(BaseModel):
    file_id: int
    paragraph_map: dict[str, str]          # edited paragraph map from frontend
