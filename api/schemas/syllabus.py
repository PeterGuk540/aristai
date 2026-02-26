"""
Syllabus Schema - Structured syllabus format matching the Syllabus Tool template.

This schema defines the structure for AI-generated syllabi, ensuring consistency
with the external Syllabus Tool product (http://120.53.222.178:8081/).
"""

from pydantic import BaseModel, Field
from typing import List, Optional


class CourseInfo(BaseModel):
    """Basic course information"""
    title: str = Field(..., description="Course title")
    code: Optional[str] = Field(None, description="Course code (e.g., CS-101)")
    semester: Optional[str] = Field(None, description="Semester (e.g., Fall 2024)")
    instructor: Optional[str] = Field(None, description="Instructor name")
    description: str = Field(..., description="Course description (2-3 sentences)")
    prerequisites: Optional[str] = Field(None, description="Prerequisites or 'None'")


class ScheduleItem(BaseModel):
    """A single week/module in the course schedule"""
    week: int = Field(..., description="Week number (1-14)")
    module: str = Field(..., description="Module/unit name")
    topic: str = Field(..., description="Topic covered this week")


class Policies(BaseModel):
    """Course policies"""
    grading: str = Field(..., description="Grading breakdown (e.g., 'Assignments: 40%, Midterm: 25%, Final: 35%')")
    attendance: str = Field(..., description="Attendance policy")
    academic_integrity: str = Field(..., description="Academic integrity/honesty policy")
    accessibility: Optional[str] = Field(None, description="Accessibility accommodations")
    office_hours: Optional[str] = Field(None, description="Office hours information")


class SyllabusSchema(BaseModel):
    """
    Complete structured syllabus matching the Syllabus Tool template.

    This schema ensures all generated syllabi follow a consistent,
    comprehensive format with proper sections for course info,
    learning goals, resources, schedule, and policies.
    """
    course_info: CourseInfo = Field(..., description="Basic course information")
    learning_goals: List[str] = Field(..., description="List of 5-8 learning objectives")
    learning_resources: List[str] = Field(..., description="Textbooks, articles, and other resources")
    schedule: List[ScheduleItem] = Field(..., description="Week-by-week course schedule (10-14 weeks)")
    policies: Policies = Field(..., description="Course policies")

    class Config:
        json_schema_extra = {
            "example": {
                "course_info": {
                    "title": "Introduction to Machine Learning",
                    "code": "CS-4780",
                    "semester": "Fall 2024",
                    "instructor": "TBD",
                    "description": "This course provides a comprehensive introduction to machine learning techniques and algorithms. Students will learn both theoretical foundations and practical applications.",
                    "prerequisites": "Linear Algebra, Probability & Statistics, Python programming"
                },
                "learning_goals": [
                    "Understand fundamental machine learning concepts and algorithms",
                    "Implement supervised and unsupervised learning methods",
                    "Evaluate model performance using appropriate metrics",
                    "Apply ML techniques to real-world problems"
                ],
                "learning_resources": [
                    "Textbook: Pattern Recognition and Machine Learning by Bishop",
                    "Online: Coursera Machine Learning Specialization",
                    "Python libraries: scikit-learn, TensorFlow, PyTorch"
                ],
                "schedule": [
                    {"week": 1, "module": "Introduction", "topic": "Course overview and ML fundamentals"},
                    {"week": 2, "module": "Supervised Learning", "topic": "Linear regression and gradient descent"}
                ],
                "policies": {
                    "grading": "Assignments: 40%, Midterm: 25%, Final Project: 35%",
                    "attendance": "Attendance is expected. More than 3 unexcused absences may affect your grade.",
                    "academic_integrity": "All work must be your own. Collaboration is encouraged for understanding, but submissions must be individual.",
                    "accessibility": "Students requiring accommodations should contact the instructor during the first week.",
                    "office_hours": "Tuesdays and Thursdays 2-4 PM, or by appointment"
                }
            }
        }
