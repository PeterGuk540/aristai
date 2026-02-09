from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from typing import List, Optional
from api.core.database import get_db
from api.models.course import Course, CourseResource, generate_join_code
from api.models.session import Session as SessionModel
from api.models.enrollment import Enrollment
from api.models.user import User, UserRole
from api.schemas.course import (
    CourseCreate,
    CourseResponse,
    CourseResourceCreate,
    CourseResourceResponse,
    JoinCourseRequest,
    JoinCourseResponse,
)
from api.schemas.session import SessionResponse

router = APIRouter()


@router.post("/", response_model=CourseResponse, status_code=status.HTTP_201_CREATED)
def create_course(course: CourseCreate, db: Session = Depends(get_db)):
    """Create a new course with syllabus and objectives."""
    try:
        # Generate a unique join code
        join_code = generate_join_code()
        # Ensure uniqueness (retry if collision)
        while db.query(Course).filter(Course.join_code == join_code).first():
            join_code = generate_join_code()

        db_course = Course(**course.model_dump(), join_code=join_code)
        db.add(db_course)
        db.flush()  # Get the course ID before commit

        # Auto-create a "Materials" session for course resources
        from api.models.session import SessionStatus
        materials_session = SessionModel(
            course_id=db_course.id,
            title="Course Materials",
            status=SessionStatus.completed,  # Always accessible, not live
            plan_json={
                "is_materials_session": True,
                "description": "Repository for course readings, documents, and other materials.",
            },
        )
        db.add(materials_session)

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


@router.get("/{course_id}/sessions", response_model=List[SessionResponse])
def list_course_sessions(
    course_id: int,
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """List all sessions for a course."""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    query = db.query(SessionModel).filter(SessionModel.course_id == course_id)

    if status:
        query = query.filter(SessionModel.status == status)

    sessions = query.order_by(SessionModel.created_at.desc()).all()
    return sessions


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


@router.post("/{course_id}/regenerate-join-code", response_model=CourseResponse)
def regenerate_join_code(course_id: int, db: Session = Depends(get_db)):
    """Regenerate the join code for a course (instructor only)."""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    try:
        # Generate a new unique join code
        new_code = generate_join_code()
        while db.query(Course).filter(Course.join_code == new_code).first():
            new_code = generate_join_code()

        course.join_code = new_code
        db.commit()
        db.refresh(course)
        return course
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.post("/join", response_model=JoinCourseResponse)
def join_course_by_code(
    request: JoinCourseRequest,
    user_id: int,  # This would come from auth in production
    db: Session = Depends(get_db)
):
    """Student joins a course using a join code."""
    # Find course by join code
    course = db.query(Course).filter(Course.join_code == request.join_code.upper()).first()
    if not course:
        raise HTTPException(status_code=404, detail="Invalid join code")

    # Verify user exists and is a student
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Check if already enrolled
    existing = db.query(Enrollment).filter(
        Enrollment.user_id == user_id,
        Enrollment.course_id == course.id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Already enrolled in this course")

    try:
        # Create enrollment
        enrollment = Enrollment(user_id=user_id, course_id=course.id)
        db.add(enrollment)
        db.commit()
        return JoinCourseResponse(
            message="Successfully enrolled in course",
            course_id=course.id,
            course_title=course.title
        )
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
