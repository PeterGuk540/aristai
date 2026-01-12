from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime
from api.schemas.base import BaseSchema


# Request schemas (no from_attributes needed)
class CourseCreate(BaseModel):
    title: str
    syllabus_text: Optional[str] = None
    objectives_json: Optional[List[Any]] = None


class CourseResourceCreate(BaseModel):
    resource_type: str
    title: str
    content: Optional[str] = None
    link: Optional[str] = None


# Response schemas (need from_attributes for ORM)
class CourseResourceResponse(BaseSchema):
    id: int
    course_id: int
    resource_type: str
    title: str
    content: Optional[str] = None
    link: Optional[str] = None
    created_at: datetime


class CourseResponse(BaseSchema):
    id: int
    title: str
    syllabus_text: Optional[str] = None
    objectives_json: Optional[List[Any]] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
