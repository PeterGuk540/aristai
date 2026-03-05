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
    filled_text: str                    # full text with placeholders replaced
    replacements: dict[str, str]        # {placeholder: value} map
    original_file_id: int               # for export
    placeholders_found: list[str]       # for UI display


class FilledTemplateExportRequest(BaseModel):
    file_id: int
    replacements: dict[str, str]
