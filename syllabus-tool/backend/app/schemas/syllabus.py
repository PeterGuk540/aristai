from pydantic import BaseModel
from typing import List, Optional

class CourseInfo(BaseModel):
    title: str
    code: str
    instructor: str
    semester: str
    description: Optional[str] = ""
    prerequisites: Optional[str] = ""
    office_hours: Optional[str] = ""
    email: Optional[str] = ""
    format: Optional[str] = ""
    materials: Optional[str] = ""

class LearningGoal(BaseModel):
    id: int
    text: str

class ScheduleItem(BaseModel):
    week: str
    date: str = ""
    topic: str
    assignment: str

class Policies(BaseModel):
    academic_integrity: str
    accessibility: str
    attendance: str
    late_work: Optional[str] = ""
    communication: Optional[str] = ""
    technology: Optional[str] = ""
    learning_resources: Optional[str] = ""
    grading: Optional[str] = ""

class SyllabusData(BaseModel):
    course_info: CourseInfo
    learning_goals: List[LearningGoal]
    schedule: List[ScheduleItem]
    policies: Policies
    startDate: str = ""
    template_id: str = "BGSU_Standard"
    custom_sections: Optional[dict] = {}
