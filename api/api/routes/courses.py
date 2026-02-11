from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from typing import List, Optional
from pydantic import BaseModel
from api.core.database import get_db
from api.core.config import get_settings
from api.models.course import Course, CourseResource, generate_join_code
from api.models.session import Session as SessionModel
from api.models.enrollment import Enrollment
from api.models.user import User, UserRole
from api.models.course_material import CourseMaterial
from api.schemas.course import (
    CourseCreate,
    CourseUpdate,
    CourseResponse,
    CourseResourceCreate,
    CourseResourceResponse,
    JoinCourseRequest,
    JoinCourseResponse,
)
from api.schemas.session import SessionResponse
from api.services.document_extractor import extract_text, is_supported_document, get_supported_extensions_display
from api.services.s3_service import get_s3_service
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


class SyllabusUploadResponse(BaseModel):
    """Response for syllabus upload endpoint."""
    extracted_text: str
    filename: str
    file_size: int
    material_id: Optional[int] = None
    message: str


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


@router.put("/{course_id}", response_model=CourseResponse)
def update_course(
    course_id: int,
    course_update: CourseUpdate,
    user_id: int,
    db: Session = Depends(get_db)
):
    """
    Update a course.
    - Admin: Can update any course
    - Instructor: Can only update courses they created
    """
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    # Check permissions
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not user.is_admin and course.created_by != user_id:
        raise HTTPException(status_code=403, detail="You don't have permission to edit this course")

    try:
        # Update only provided fields
        update_data = course_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(course, field, value)

        db.commit()
        db.refresh(course)
        return course
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.delete("/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_course(
    course_id: int,
    user_id: int,
    db: Session = Depends(get_db)
):
    """
    Delete a course and all related data (sessions, enrollments, materials, etc.).
    - Admin: Can delete any course
    - Instructor: Can only delete courses they created
    """
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    # Check permissions
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not user.is_admin and course.created_by != user_id:
        raise HTTPException(status_code=403, detail="You don't have permission to delete this course")

    try:
        db.delete(course)
        db.commit()
        return None
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.get("/", response_model=List[CourseResponse])
def list_courses(
    skip: int = 0,
    limit: int = 100,
    user_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """
    List courses based on user role:
    - Admin: See all courses
    - Instructor: See only courses they created
    - Student: See only courses they are enrolled in (handled in frontend)

    If user_id is not provided, returns all courses (for backward compatibility).
    """
    if user_id:
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            if user.is_admin:
                # Admin sees all courses
                courses = db.query(Course).offset(skip).limit(limit).all()
            elif user.role == UserRole.instructor:
                # Instructor sees only their own courses
                courses = db.query(Course).filter(Course.created_by == user_id).offset(skip).limit(limit).all()
            else:
                # Student - return empty, frontend handles enrolled courses separately
                courses = []
            return courses

    # Default: return all courses (backward compatibility)
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


@router.post("/upload-syllabus", response_model=SyllabusUploadResponse)
async def upload_syllabus(
    file: UploadFile = File(...),
    course_id: Optional[int] = Form(None),
    user_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
):
    """
    Upload a syllabus file and extract its text content.

    - Supports PDF, Word (.docx), and text files
    - Extracts text for use in course creation
    - If course_id is provided, stores the file as a course material

    Returns the extracted text for use in the course creation form.
    """
    # Validate file type
    if not is_supported_document(file.filename, file.content_type or ""):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Supported formats: {get_supported_extensions_display()}"
        )

    # Read file content
    file_content = await file.read()
    file_size = len(file_content)

    # Check file size (10MB limit for syllabus)
    max_size = 10 * 1024 * 1024
    if file_size > max_size:
        raise HTTPException(
            status_code=413,
            detail="File too large. Maximum size for syllabus is 10MB."
        )

    # Extract text
    extracted_text, error = extract_text(
        file_content,
        file.filename,
        file.content_type or "application/octet-stream"
    )

    if error:
        raise HTTPException(status_code=422, detail=error)

    material_id = None

    # If course_id provided, save to S3 and create material record
    if course_id:
        course = db.query(Course).filter(Course.id == course_id).first()
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")

        s3_service = get_s3_service()

        if s3_service.is_enabled():
            try:
                # Find the materials session for this course
                materials_session = db.query(SessionModel).filter(
                    SessionModel.course_id == course_id,
                    SessionModel.title == "Course Materials"
                ).first()

                session_id = materials_session.id if materials_session else None

                # Generate S3 key and upload
                s3_key = s3_service.generate_s3_key(
                    course_id,
                    f"syllabus_{file.filename}",
                    session_id
                )

                # Reset file position and upload
                await file.seek(0)
                success, upload_error = s3_service.upload_file(
                    file.file,
                    s3_key,
                    file.content_type or "application/octet-stream",
                    file.filename,
                )

                if success:
                    # Create material record
                    material = CourseMaterial(
                        course_id=course_id,
                        session_id=session_id,
                        filename=file.filename,
                        s3_key=s3_key,
                        file_size=file_size,
                        content_type=file.content_type or "application/octet-stream",
                        title=f"Syllabus - {file.filename}",
                        description="Course syllabus uploaded during course creation",
                        uploaded_by=user_id,
                    )
                    db.add(material)
                    db.commit()
                    db.refresh(material)
                    material_id = material.id
                    logger.info(f"Syllabus uploaded and saved as material {material_id} for course {course_id}")
                else:
                    logger.warning(f"Failed to upload syllabus to S3: {upload_error}")
            except Exception as e:
                logger.error(f"Error saving syllabus to S3: {e}")
                # Don't fail the whole request, just log the error

    return SyllabusUploadResponse(
        extracted_text=extracted_text,
        filename=file.filename,
        file_size=file_size,
        material_id=material_id,
        message="Syllabus text extracted successfully" + (
            " and saved to course materials" if material_id else ""
        )
    )


class ExtractObjectivesRequest(BaseModel):
    """Request for extracting learning objectives from syllabus text."""
    syllabus_text: str


class ExtractObjectivesResponse(BaseModel):
    """Response for learning objectives extraction."""
    objectives: List[str]
    confidence: str
    notes: Optional[str] = None
    success: bool
    error: Optional[str] = None


@router.post("/extract-objectives", response_model=ExtractObjectivesResponse)
async def extract_learning_objectives(request: ExtractObjectivesRequest):
    """
    Extract learning objectives from syllabus text using AI.

    - Analyzes syllabus content to identify key learning objectives
    - Returns 5-10 clear, measurable objectives
    - Uses LLM when available, falls back to pattern matching otherwise
    """
    from api.services.learning_objectives_extractor import extract_learning_objectives as extract_objectives

    result = extract_objectives(request.syllabus_text)

    return ExtractObjectivesResponse(
        objectives=result.get("objectives", []),
        confidence=result.get("confidence", "low"),
        notes=result.get("notes"),
        success=result.get("success", False),
        error=result.get("error"),
    )
