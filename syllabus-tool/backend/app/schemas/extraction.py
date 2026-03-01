from __future__ import annotations

from typing import List, Optional, Dict, Any

from pydantic import BaseModel, Field


class ExtractedCourseInfo(BaseModel):
    title: str = ""
    code: str = ""
    instructor: str = ""
    semester: str = ""
    description: str = ""
    prerequisites: str = ""
    office_hours: str = ""
    email: str = ""
    format: str = ""  # e.g. Online, In-person
    materials: str = ""  # Required textbooks/software


class ExtractedLearningGoal(BaseModel):
    id: Optional[int] = None
    text: str = ""


class ExtractedScheduleItem(BaseModel):
    week: str = ""
    date: str = ""
    topic: str = ""
    assignment: str = ""


class ExtractedPolicies(BaseModel):
    academic_integrity: str = ""
    accessibility: str = ""
    attendance: str = ""
    grading: str = ""
    late_work: str = ""
    communication: str = ""
    technology: str = ""
    learning_resources: str = ""


class ExtractedSuggestions(BaseModel):
    functional: List[str] = Field(default_factory=list)
    ui_ux: List[str] = Field(default_factory=list)


class ValidationIssue(BaseModel):
    type: str = ""  # e.g. "missing", "incorrect", "style", "passed"
    section: str = ""  # e.g. "course_info", "policies"
    field: str = ""  # e.g. "instructor", "attendance"
    issue: str = ""  # Description of the problem or the check performed
    current: str = ""  # Current value or description
    suggestion: str = ""  # Proposed value or fix description
    category: str = "functional"  # "functional" or "ui_ux"
    status: str = "failed" # "passed" or "failed"


class ExtractedValidation(BaseModel):
    conforms_to_guidance: bool = False
    issues: List[ValidationIssue] = Field(default_factory=list)


class ExtractedSyllabusData(BaseModel):
    course_info: ExtractedCourseInfo = Field(default_factory=ExtractedCourseInfo)
    learning_goals: List[ExtractedLearningGoal] = Field(default_factory=list)
    schedule: List[ExtractedScheduleItem] = Field(default_factory=list)
    policies: ExtractedPolicies = Field(default_factory=ExtractedPolicies)
    suggestions: Optional[ExtractedSuggestions] = None
    validation: Optional[ExtractedValidation] = None
    custom_sections: Optional[Dict[str, Any]] = Field(default_factory=dict)


class ChatSuggestedChanges(BaseModel):
    course_info: Optional[ExtractedCourseInfo] = None
    learning_goals: Optional[List[ExtractedLearningGoal]] = None
    schedule: Optional[List[ExtractedScheduleItem]] = None
    policies: Optional[ExtractedPolicies] = None


class ChatLLMResponse(BaseModel):
    assistant_message: str = ""
    suggested_changes: Optional[ChatSuggestedChanges] = None
