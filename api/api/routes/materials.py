"""API routes for course materials (file upload/download/delete)."""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from api.core.database import get_db
from api.core.config import get_settings
from api.models.course import Course
from api.models.session import Session as SessionModel
from api.models.course_material import CourseMaterial
from api.models.enrollment import Enrollment
from api.services.s3_service import get_s3_service
from pydantic import BaseModel
from datetime import datetime

logger = logging.getLogger(__name__)
router = APIRouter()


# --- Pydantic Schemas ---

class MaterialResponse(BaseModel):
    id: int
    course_id: int
    session_id: Optional[int]
    filename: str
    file_size: int
    content_type: str
    title: Optional[str]
    description: Optional[str]
    uploaded_by: Optional[int]
    created_at: datetime
    updated_at: datetime
    version: int
    download_url: Optional[str] = None

    class Config:
        from_attributes = True


class MaterialListResponse(BaseModel):
    materials: List[MaterialResponse]
    total: int


class MaterialUpdateRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None


class PresignedUploadResponse(BaseModel):
    upload_url: str
    fields: dict
    s3_key: str
    expires_in: int


# --- Helper Functions ---

def get_material_with_url(material: CourseMaterial) -> MaterialResponse:
    """Convert a CourseMaterial to response with download URL."""
    s3_service = get_s3_service()
    download_url = s3_service.generate_presigned_url(material.s3_key) if s3_service.is_enabled() else None

    return MaterialResponse(
        id=material.id,
        course_id=material.course_id,
        session_id=material.session_id,
        filename=material.filename,
        file_size=material.file_size,
        content_type=material.content_type,
        title=material.title,
        description=material.description,
        uploaded_by=material.uploaded_by,
        created_at=material.created_at,
        updated_at=material.updated_at,
        version=material.version,
        download_url=download_url,
    )


def check_course_access(db: Session, course_id: int, user_id: Optional[int] = None) -> Course:
    """Verify course exists and user has access (enrolled or instructor)."""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    # TODO: Add proper access control when auth is implemented
    # For now, allow access to all
    return course


def check_instructor_access(db: Session, course_id: int, user_id: Optional[int] = None) -> Course:
    """Verify user is an instructor for the course."""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    # TODO: Add proper instructor check when auth is implemented
    return course


# --- API Endpoints ---

@router.post("/courses/{course_id}/materials", response_model=MaterialResponse, status_code=status.HTTP_201_CREATED)
async def upload_material(
    course_id: int,
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    session_id: Optional[int] = Form(None),
    user_id: Optional[int] = Form(None),  # Would come from auth
    db: Session = Depends(get_db),
):
    """
    Upload a course material file.

    - Instructors can upload to any session or course-wide
    - Files are stored in S3 with metadata in database
    - Maximum file size: 100MB (configurable)
    """
    settings = get_settings()
    s3_service = get_s3_service()

    if not s3_service.is_enabled():
        raise HTTPException(status_code=503, detail="File storage service is not configured")

    # Verify course access
    check_instructor_access(db, course_id, user_id)

    # Verify session if provided
    if session_id:
        session = db.query(SessionModel).filter(
            SessionModel.id == session_id,
            SessionModel.course_id == course_id
        ).first()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found in this course")

    # Check file size
    file_content = await file.read()
    file_size = len(file_content)

    if file_size > s3_service.max_file_size_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {settings.aws_s3_max_file_size_mb}MB"
        )

    # Reset file pointer
    await file.seek(0)

    # Generate S3 key and upload
    s3_key = s3_service.generate_s3_key(course_id, file.filename, session_id)
    content_type = file.content_type or "application/octet-stream"

    success, error = s3_service.upload_file(
        file.file,
        s3_key,
        content_type,
        file.filename,
    )

    if not success:
        raise HTTPException(status_code=500, detail=f"Failed to upload file: {error}")

    # Create database record
    try:
        material = CourseMaterial(
            course_id=course_id,
            session_id=session_id,
            filename=file.filename,
            s3_key=s3_key,
            file_size=file_size,
            content_type=content_type,
            title=title or file.filename,
            description=description,
            uploaded_by=user_id,
        )
        db.add(material)
        db.commit()
        db.refresh(material)

        logger.info(f"Material uploaded: {material.id} for course {course_id}")
        return get_material_with_url(material)

    except SQLAlchemyError as e:
        # Clean up S3 file if database fails
        s3_service.delete_file(s3_key)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.get("/courses/{course_id}/materials", response_model=MaterialListResponse)
def list_course_materials(
    course_id: int,
    session_id: Optional[int] = Query(None, description="Filter by session"),
    user_id: Optional[int] = Query(None),  # Would come from auth
    db: Session = Depends(get_db),
):
    """
    List all materials for a course.

    - Optionally filter by session_id
    - Returns download URLs valid for 1 hour
    """
    check_course_access(db, course_id, user_id)

    query = db.query(CourseMaterial).filter(CourseMaterial.course_id == course_id)

    if session_id is not None:
        query = query.filter(CourseMaterial.session_id == session_id)

    materials = query.order_by(CourseMaterial.created_at.desc()).all()

    return MaterialListResponse(
        materials=[get_material_with_url(m) for m in materials],
        total=len(materials),
    )


@router.get("/courses/{course_id}/materials/{material_id}", response_model=MaterialResponse)
def get_material(
    course_id: int,
    material_id: int,
    user_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    """Get a specific material with download URL."""
    check_course_access(db, course_id, user_id)

    material = db.query(CourseMaterial).filter(
        CourseMaterial.id == material_id,
        CourseMaterial.course_id == course_id,
    ).first()

    if not material:
        raise HTTPException(status_code=404, detail="Material not found")

    return get_material_with_url(material)


@router.get("/courses/{course_id}/materials/{material_id}/download")
def download_material(
    course_id: int,
    material_id: int,
    user_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    """
    Get a redirect to download the material.

    Returns a 302 redirect to the presigned S3 URL.
    """
    check_course_access(db, course_id, user_id)

    material = db.query(CourseMaterial).filter(
        CourseMaterial.id == material_id,
        CourseMaterial.course_id == course_id,
    ).first()

    if not material:
        raise HTTPException(status_code=404, detail="Material not found")

    s3_service = get_s3_service()
    download_url = s3_service.generate_presigned_url(material.s3_key)

    if not download_url:
        raise HTTPException(status_code=500, detail="Failed to generate download URL")

    return RedirectResponse(url=download_url, status_code=302)


@router.put("/courses/{course_id}/materials/{material_id}", response_model=MaterialResponse)
def update_material(
    course_id: int,
    material_id: int,
    update: MaterialUpdateRequest,
    user_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    """Update material metadata (title, description)."""
    check_instructor_access(db, course_id, user_id)

    material = db.query(CourseMaterial).filter(
        CourseMaterial.id == material_id,
        CourseMaterial.course_id == course_id,
    ).first()

    if not material:
        raise HTTPException(status_code=404, detail="Material not found")

    try:
        if update.title is not None:
            material.title = update.title
        if update.description is not None:
            material.description = update.description

        db.commit()
        db.refresh(material)
        return get_material_with_url(material)

    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.post("/courses/{course_id}/materials/{material_id}/replace", response_model=MaterialResponse, status_code=status.HTTP_201_CREATED)
async def replace_material(
    course_id: int,
    material_id: int,
    file: UploadFile = File(...),
    user_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
):
    """
    Replace a material with a new file (creates a new version).

    - Keeps the old file in S3 (versioning enabled)
    - Creates a new database record with incremented version
    - Links to the replaced material
    """
    settings = get_settings()
    s3_service = get_s3_service()

    if not s3_service.is_enabled():
        raise HTTPException(status_code=503, detail="File storage service is not configured")

    check_instructor_access(db, course_id, user_id)

    # Get existing material
    old_material = db.query(CourseMaterial).filter(
        CourseMaterial.id == material_id,
        CourseMaterial.course_id == course_id,
    ).first()

    if not old_material:
        raise HTTPException(status_code=404, detail="Material not found")

    # Check file size
    file_content = await file.read()
    file_size = len(file_content)

    if file_size > s3_service.max_file_size_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {settings.aws_s3_max_file_size_mb}MB"
        )

    await file.seek(0)

    # Generate new S3 key and upload
    s3_key = s3_service.generate_s3_key(course_id, file.filename, old_material.session_id)
    content_type = file.content_type or "application/octet-stream"

    success, error = s3_service.upload_file(
        file.file,
        s3_key,
        content_type,
        file.filename,
    )

    if not success:
        raise HTTPException(status_code=500, detail=f"Failed to upload file: {error}")

    # Create new version record
    try:
        new_material = CourseMaterial(
            course_id=course_id,
            session_id=old_material.session_id,
            filename=file.filename,
            s3_key=s3_key,
            file_size=file_size,
            content_type=content_type,
            title=old_material.title,  # Keep same title
            description=old_material.description,  # Keep same description
            uploaded_by=user_id,
            version=old_material.version + 1,
            replaced_material_id=old_material.id,
        )
        db.add(new_material)
        db.commit()
        db.refresh(new_material)

        logger.info(f"Material replaced: {old_material.id} -> {new_material.id}")
        return get_material_with_url(new_material)

    except SQLAlchemyError as e:
        s3_service.delete_file(s3_key)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.delete("/courses/{course_id}/materials/{material_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_material(
    course_id: int,
    material_id: int,
    user_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    """
    Delete a material.

    - Removes from database
    - Deletes file from S3
    """
    check_instructor_access(db, course_id, user_id)

    material = db.query(CourseMaterial).filter(
        CourseMaterial.id == material_id,
        CourseMaterial.course_id == course_id,
    ).first()

    if not material:
        raise HTTPException(status_code=404, detail="Material not found")

    s3_key = material.s3_key

    try:
        db.delete(material)
        db.commit()

        # Delete from S3 after database success
        s3_service = get_s3_service()
        s3_service.delete_file(s3_key)

        logger.info(f"Material deleted: {material_id}")

    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.get("/sessions/{session_id}/materials", response_model=MaterialListResponse)
def list_session_materials(
    session_id: int,
    user_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    """List all materials for a specific session."""
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    check_course_access(db, session.course_id, user_id)

    materials = db.query(CourseMaterial).filter(
        CourseMaterial.session_id == session_id
    ).order_by(CourseMaterial.created_at.desc()).all()

    return MaterialListResponse(
        materials=[get_material_with_url(m) for m in materials],
        total=len(materials),
    )


@router.get("/materials/presigned-upload", response_model=PresignedUploadResponse)
def get_presigned_upload_url(
    course_id: int,
    filename: str,
    content_type: str,
    session_id: Optional[int] = None,
    user_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    """
    Get a presigned URL for direct browser upload to S3.

    Use this for large files to upload directly from browser to S3,
    bypassing the API server.
    """
    s3_service = get_s3_service()

    if not s3_service.is_enabled():
        raise HTTPException(status_code=503, detail="File storage service is not configured")

    check_instructor_access(db, course_id, user_id)

    s3_key = s3_service.generate_s3_key(course_id, filename, session_id)

    presigned_data = s3_service.generate_presigned_upload_url(s3_key, content_type)

    if not presigned_data:
        raise HTTPException(status_code=500, detail="Failed to generate upload URL")

    return PresignedUploadResponse(
        upload_url=presigned_data["url"],
        fields=presigned_data["fields"],
        s3_key=s3_key,
        expires_in=3600,
    )
