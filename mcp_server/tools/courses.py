"""
Course-related MCP tools.

Tools for listing, creating, and managing courses.
"""

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from api.models.course import Course, generate_join_code
from api.models.session import Session as SessionModel

logger = logging.getLogger(__name__)


def list_courses(db: Session, skip: int = 0, limit: int = 100) -> Dict[str, Any]:
    """
    List all available courses.
    
    Returns a voice-friendly list of courses with their key information.
    """
    courses = db.query(Course).offset(skip).limit(limit).all()
    
    if not courses:
        return {
            "message": "No courses found in the system.",
            "courses": [],
            "count": 0,
        }
    
    course_list = []
    for c in courses:
        # Count sessions for each course
        session_count = db.query(SessionModel).filter(SessionModel.course_id == c.id).count()
        
        course_list.append({
            "id": c.id,
            "title": c.title,
            "join_code": c.join_code,
            "session_count": session_count,
            "has_syllabus": bool(c.syllabus_text),
            "objective_count": len(c.objectives_json) if c.objectives_json else 0,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        })
    
    # Voice-friendly summary
    message = f"Found {len(courses)} course{'s' if len(courses) != 1 else ''}. "
    if len(courses) <= 5:
        titles = [c["title"] for c in course_list]
        message += "Courses: " + ", ".join(titles) + "."
    
    return {
        "message": message,
        "courses": course_list,
        "count": len(courses),
    }


def get_course(db: Session, course_id: int) -> Dict[str, Any]:
    """
    Get detailed information about a specific course.
    """
    course = db.query(Course).filter(Course.id == course_id).first()
    
    if not course:
        return {"error": f"Course {course_id} not found"}
    
    # Get session count and status breakdown
    sessions = db.query(SessionModel).filter(SessionModel.course_id == course_id).all()
    status_counts = {"draft": 0, "scheduled": 0, "live": 0, "completed": 0}
    for s in sessions:
        status = s.status.value if hasattr(s.status, 'value') else s.status
        if status in status_counts:
            status_counts[status] += 1
    
    objectives = course.objectives_json if course.objectives_json else []
    
    # Voice-friendly summary
    message = f"Course: {course.title}. "
    message += f"It has {len(sessions)} sessions. "
    if status_counts["live"] > 0:
        message += f"{status_counts['live']} session{'s are' if status_counts['live'] > 1 else ' is'} currently live. "
    if objectives:
        message += f"There are {len(objectives)} learning objectives."
    
    return {
        "message": message,
        "id": course.id,
        "title": course.title,
        "join_code": course.join_code,
        "syllabus_preview": course.syllabus_text[:500] + "..." if course.syllabus_text and len(course.syllabus_text) > 500 else course.syllabus_text,
        "objectives": objectives,
        "session_count": len(sessions),
        "session_status_breakdown": status_counts,
        "created_at": course.created_at.isoformat() if course.created_at else None,
    }


def create_course(
    db: Session,
    title: str,
    syllabus_text: Optional[str] = None,
    objectives: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Create a new course.
    """
    try:
        # Generate unique join code
        join_code = generate_join_code()
        while db.query(Course).filter(Course.join_code == join_code).first():
            join_code = generate_join_code()
        
        course = Course(
            title=title,
            syllabus_text=syllabus_text,
            objectives_json=objectives,
            join_code=join_code,
        )
        db.add(course)
        db.commit()
        db.refresh(course)
        
        message = f"Created course '{title}' with ID {course.id}. "
        message += f"Join code is {join_code}."
        
        return {
            "message": message,
            "id": course.id,
            "title": course.title,
            "join_code": join_code,
            "success": True,
        }
        
    except Exception as e:
        db.rollback()
        logger.exception(f"Failed to create course: {e}")
        return {"error": f"Failed to create course: {str(e)}"}


def generate_session_plans(db: Session, course_id: int) -> Dict[str, Any]:
    """
    Trigger AI generation of session plans from syllabus.
    """
    course = db.query(Course).filter(Course.id == course_id).first()
    
    if not course:
        return {"error": f"Course {course_id} not found"}
    
    if not course.syllabus_text:
        return {"error": "Course has no syllabus. Please add a syllabus first."}
    
    try:
        from worker.tasks import generate_plans_task
        task = generate_plans_task.delay(course_id)
        
        message = f"Started generating session plans for '{course.title}'. "
        message += "This may take a minute or two. "
        message += "Check back soon to see the generated sessions."
        
        return {
            "message": message,
            "task_id": task.id,
            "course_id": course_id,
            "status": "queued",
        }
        
    except Exception as e:
        logger.exception(f"Failed to queue plan generation: {e}")
        return {"error": f"Failed to start plan generation: {str(e)}"}
