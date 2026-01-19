from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from typing import List
from pydantic import BaseModel
from datetime import datetime
from api.core.database import get_db
from api.models.enrollment import Enrollment
from api.models.user import User, UserRole
from api.models.course import Course

router = APIRouter()


# Request/Response schemas
class EnrollmentCreate(BaseModel):
    user_id: int
    course_id: int


class EnrollmentResponse(BaseModel):
    id: int
    user_id: int
    course_id: int
    enrolled_at: datetime

    class Config:
        from_attributes = True


class EnrolledStudentResponse(BaseModel):
    user_id: int
    name: str
    email: str
    enrolled_at: datetime


@router.post("/", response_model=EnrollmentResponse, status_code=status.HTTP_201_CREATED)
def enroll_user(enrollment: EnrollmentCreate, db: Session = Depends(get_db)):
    """Enroll a user in a course."""
    # Validate user exists
    user = db.query(User).filter(User.id == enrollment.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Validate course exists
    course = db.query(Course).filter(Course.id == enrollment.course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    try:
        db_enrollment = Enrollment(**enrollment.model_dump())
        db.add(db_enrollment)
        db.commit()
        db.refresh(db_enrollment)
        return db_enrollment
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="User already enrolled in this course")
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.delete("/{enrollment_id}", status_code=status.HTTP_204_NO_CONTENT)
def unenroll_user(enrollment_id: int, db: Session = Depends(get_db)):
    """Remove a user from a course."""
    enrollment = db.query(Enrollment).filter(Enrollment.id == enrollment_id).first()
    if not enrollment:
        raise HTTPException(status_code=404, detail="Enrollment not found")

    try:
        db.delete(enrollment)
        db.commit()
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.get("/course/{course_id}/students", response_model=List[EnrolledStudentResponse])
def get_enrolled_students(course_id: int, db: Session = Depends(get_db)):
    """Get all students enrolled in a course."""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    enrollments = (
        db.query(Enrollment, User)
        .join(User, Enrollment.user_id == User.id)
        .filter(
            Enrollment.course_id == course_id,
            User.role == UserRole.student
        )
        .all()
    )

    return [
        EnrolledStudentResponse(
            user_id=user.id,
            name=user.name,
            email=user.email,
            enrolled_at=enrollment.enrolled_at
        )
        for enrollment, user in enrollments
    ]


@router.get("/user/{user_id}/courses", response_model=List[dict])
def get_user_enrollments(user_id: int, db: Session = Depends(get_db)):
    """Get all courses a user is enrolled in."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    enrollments = (
        db.query(Enrollment, Course)
        .join(Course, Enrollment.course_id == Course.id)
        .filter(Enrollment.user_id == user_id)
        .all()
    )

    return [
        {
            "enrollment_id": enrollment.id,
            "course_id": course.id,
            "course_title": course.title,
            "enrolled_at": enrollment.enrolled_at.isoformat()
        }
        for enrollment, course in enrollments
    ]


@router.post("/course/{course_id}/enroll-all-students", status_code=status.HTTP_201_CREATED)
def enroll_all_students(course_id: int, db: Session = Depends(get_db)):
    """Enroll all students (users with role='student') in a course. Useful for setup."""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    # Get all students
    students = db.query(User).filter(User.role == UserRole.student).all()

    # Get already enrolled user IDs
    existing_enrollments = db.query(Enrollment.user_id).filter(
        Enrollment.course_id == course_id
    ).all()
    enrolled_ids = {e.user_id for e in existing_enrollments}

    # Enroll students not yet enrolled
    new_enrollments = []
    for student in students:
        if student.id not in enrolled_ids:
            enrollment = Enrollment(user_id=student.id, course_id=course_id)
            db.add(enrollment)
            new_enrollments.append(student.id)

    try:
        db.commit()
        return {
            "message": f"Enrolled {len(new_enrollments)} students",
            "newly_enrolled_user_ids": new_enrollments,
            "already_enrolled_count": len(enrolled_ids)
        }
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
