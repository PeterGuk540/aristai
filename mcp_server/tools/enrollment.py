"""
Enrollment-related MCP tools.

Tools for managing student enrollment and user listings.
"""

import logging
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from api.models.user import User, UserRole
from api.models.course import Course
from api.models.enrollment import Enrollment

logger = logging.getLogger(__name__)


def get_enrolled_students(db: Session, course_id: int) -> Dict[str, Any]:
    """
    Get list of students enrolled in a course.
    """
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        return {"error": f"Course {course_id} not found"}
    
    enrollments = (
        db.query(Enrollment, User)
        .join(User, Enrollment.user_id == User.id)
        .filter(
            Enrollment.course_id == course_id,
            User.role == UserRole.student
        )
        .all()
    )
    
    if not enrollments:
        return {
            "message": f"No students are enrolled in '{course.title}'.",
            "course_id": course_id,
            "course_title": course.title,
            "students": [],
            "count": 0,
        }
    
    students = []
    for enrollment, user in enrollments:
        students.append({
            "user_id": user.id,
            "name": user.name,
            "email": user.email,
            "enrolled_at": enrollment.enrolled_at.isoformat() if enrollment.enrolled_at else None,
        })
    
    # Voice-friendly message
    names = [s["name"] for s in students[:5]]
    message = f"Course '{course.title}' has {len(students)} enrolled student{'s' if len(students) != 1 else ''}. "
    message += f"Students include: {', '.join(names)}"
    if len(students) > 5:
        message += f" and {len(students) - 5} more."
    
    return {
        "message": message,
        "course_id": course_id,
        "course_title": course.title,
        "students": students,
        "count": len(students),
    }


def enroll_student(db: Session, user_id: int, course_id: int) -> Dict[str, Any]:
    """
    Enroll a student in a course.
    """
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        return {"error": f"Course {course_id} not found"}
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {"error": f"User {user_id} not found"}
    
    # Check if already enrolled
    existing = db.query(Enrollment).filter(
        Enrollment.user_id == user_id,
        Enrollment.course_id == course_id
    ).first()
    
    if existing:
        return {
            "message": f"{user.name} is already enrolled in '{course.title}'.",
            "already_enrolled": True,
            "user_id": user_id,
            "course_id": course_id,
        }
    
    try:
        enrollment = Enrollment(user_id=user_id, course_id=course_id)
        db.add(enrollment)
        db.commit()
        
        message = f"Enrolled {user.name} in course '{course.title}'."
        
        return {
            "message": message,
            "user_id": user_id,
            "user_name": user.name,
            "course_id": course_id,
            "course_title": course.title,
            "success": True,
        }
        
    except Exception as e:
        db.rollback()
        logger.exception(f"Failed to enroll student: {e}")
        return {"error": f"Failed to enroll student: {str(e)}"}


def bulk_enroll_students(db: Session, course_id: int, user_ids: list[int]) -> Dict[str, Any]:
    """
    Bulk enroll students in a course.
    """
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        return {"error": f"Course {course_id} not found"}

    users = db.query(User).filter(User.id.in_(user_ids)).all()
    valid_user_ids = {u.id for u in users}
    invalid_ids = [user_id for user_id in user_ids if user_id not in valid_user_ids]
    if invalid_ids:
        return {"error": f"Invalid user IDs: {invalid_ids}"}

    existing = db.query(Enrollment.user_id).filter(Enrollment.course_id == course_id).all()
    enrolled_ids = {row.user_id for row in existing}

    newly_enrolled = []
    already_enrolled = []
    for user_id in user_ids:
        if user_id in enrolled_ids:
            already_enrolled.append(user_id)
            continue
        enrollment = Enrollment(user_id=user_id, course_id=course_id)
        db.add(enrollment)
        newly_enrolled.append(user_id)

    try:
        db.commit()
        return {
            "message": f"Enrolled {len(newly_enrolled)} students in '{course.title}'.",
            "course_id": course_id,
            "course_title": course.title,
            "newly_enrolled_user_ids": newly_enrolled,
            "already_enrolled_user_ids": already_enrolled,
        }
    except Exception as e:
        db.rollback()
        logger.exception(f"Failed bulk enroll: {e}")
        return {"error": f"Failed to bulk enroll students: {str(e)}"}


def get_users(db: Session, role: Optional[str] = None) -> Dict[str, Any]:
    """
    Get list of users, optionally filtered by role.
    """
    query = db.query(User)
    
    if role:
        try:
            role_enum = UserRole(role)
            query = query.filter(User.role == role_enum)
        except ValueError:
            return {"error": f"Invalid role: {role}. Use 'instructor' or 'student'."}
    
    users = query.order_by(User.name).all()
    
    if not users:
        filter_msg = f" with role '{role}'" if role else ""
        return {
            "message": f"No users found{filter_msg}.",
            "users": [],
            "count": 0,
        }
    
    user_list = []
    instructors = 0
    students = 0
    
    for u in users:
        user_role = u.role.value if hasattr(u.role, 'value') else str(u.role)
        user_list.append({
            "id": u.id,
            "name": u.name,
            "email": u.email,
            "role": user_role,
            "is_admin": u.is_admin,
        })
        
        if user_role == "instructor":
            instructors += 1
        else:
            students += 1
    
    # Voice-friendly message
    if role:
        message = f"Found {len(users)} {role}{'s' if len(users) != 1 else ''}."
    else:
        message = f"Found {len(users)} users: {instructors} instructor{'s' if instructors != 1 else ''} and {students} student{'s' if students != 1 else ''}."
    
    return {
        "message": message,
        "users": user_list,
        "count": len(users),
        "instructor_count": instructors,
        "student_count": students,
    }
