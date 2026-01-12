from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from typing import List
from api.core.database import get_db
from api.models.course import Course, CourseResource
from api.schemas.course import (
    CourseCreate,
    CourseResponse,
    CourseResourceCreate,
    CourseResourceResponse,
)

router = APIRouter()


@router.post("/", response_model=CourseResponse, status_code=status.HTTP_201_CREATED)
def create_course(course: CourseCreate, db: Session = Depends(get_db)):
    """Create a new course with syllabus and objectives."""
    try:
        db_course = Course(**course.model_dump())
        db.add(db_course)
        db.commit()
        db.refresh(db_course)
        return db_course
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.get("/{course_id}", response_model=CourseResponse)
def get_course(course_id: int, db: Session = Depends(get_db)):
    """Get a course by ID."""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    return course


@router.get("/", response_model=List[CourseResponse])
def list_courses(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """List all courses."""
    courses = db.query(Course).offset(skip).limit(limit).all()
    return courses


@router.post(
    "/{course_id}/resources",
    response_model=CourseResourceResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_course_resource(
    course_id: int, resource: CourseResourceCreate, db: Session = Depends(get_db)
):
    """Add a resource to a course."""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    try:
        db_resource = CourseResource(course_id=course_id, **resource.model_dump())
        db.add(db_resource)
        db.commit()
        db.refresh(db_resource)
        return db_resource
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.post("/{course_id}/generate_plans", status_code=status.HTTP_202_ACCEPTED)
def generate_session_plans(course_id: int, db: Session = Depends(get_db)):
    """Trigger async job to generate session plans from syllabus."""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    # Import here to avoid circular imports
    from worker.tasks import generate_plans_task

    task = generate_plans_task.delay(course_id)
    return {"task_id": task.id, "status": "queued"}
