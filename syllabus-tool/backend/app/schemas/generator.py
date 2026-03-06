from pydantic import BaseModel
from typing import Optional, Literal


class GenerateRequest(BaseModel):
    course_title: str
    target_audience: str
    duration: str  # e.g. "16 weeks", "one semester"
    reference_file_id: Optional[int] = None
    language: str = "en"


class FillTemplateRequest(BaseModel):
    reference_file_id: int
    course_title: str
    target_audience: str = ""
    duration: str = ""
    language: str = "en"
    syllabus_content: Optional[dict] = None  # saved syllabus content to guide the fill


class FillTemplateJobResponse(BaseModel):
    job_id: str


class FillTemplateSection(BaseModel):
    id: str                        # "body", "table_0", "table_1", ...
    label: str                     # "Course Content", "Points Breakdown", ...
    paragraph_indices: list[int]   # flat indices belonging to this section
    filled_text: str               # newline-joined text for this section only
    original_text: str             # original template text for comparison
    is_policy: bool = False        # true if this section was preserved verbatim


class FillTemplateResult(BaseModel):
    sections: list[FillTemplateSection]
    paragraph_map: dict[str, str]  # flat map of ALL indices (for DOCX export)
    original_file_id: int


class FillTemplateStatusResponse(BaseModel):
    status: Literal["pending", "running", "completed", "failed"]
    result: Optional[FillTemplateResult] = None
    error: Optional[str] = None


class FillTemplateResponse(BaseModel):
    filled_text: str                       # complete generated text for preview/editing
    paragraph_map: dict[str, str]          # {"0": "text", "1": "text", ...} for DOCX export
    original_file_id: int


class FilledTemplateExportRequest(BaseModel):
    file_id: int
    paragraph_map: dict[str, str]          # edited paragraph map from frontend


class RegenerateSectionRequest(BaseModel):
    reference_file_id: int
    section_id: str                        # "body", "table_0", etc.
    paragraph_indices: list[int]           # paragraph indices belonging to this section
    course_title: str
    target_audience: str = ""
    duration: str = ""
    language: str = "en"
    instruction: str = ""                  # optional user instruction, e.g. "Make more detailed"


class RegenerateSectionResponse(BaseModel):
    filled_text: str                       # regenerated text for the section
    paragraph_map: dict[str, str]          # index->text map for this section only
