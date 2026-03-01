from pydantic import BaseModel
from typing import Optional

class GenerateRequest(BaseModel):
    course_title: str
    target_audience: str
    duration: str  # e.g. "16 weeks", "one semester"
    reference_file_id: Optional[int] = None
