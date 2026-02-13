"""Routes for LMS integrations (Canvas first, extensible to Blackboard/UPP)."""

from __future__ import annotations

import io
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.core.database import get_db
from api.models.course import Course
from api.models.course_material import CourseMaterial
from api.models.session import Session as SessionModel
from api.services.integrations.registry import get_provider, list_supported_providers
from api.services.s3_service import get_s3_service

router = APIRouter(prefix="/integrations", tags=["integrations"])


class ProviderStatus(BaseModel):
    name: str
    configured: bool
    enabled: bool


class ExternalCourseResponse(BaseModel):
    provider: str
    external_id: str
    title: str
    code: Optional[str] = None
    term: Optional[str] = None


class ExternalMaterialResponse(BaseModel):
    provider: str
    external_id: str
    course_external_id: str
    title: str
    filename: str
    content_type: str
    size_bytes: int
    updated_at: Optional[str] = None
    source_url: Optional[str] = None


class ImportRequest(BaseModel):
    target_course_id: int = Field(..., description="AristAI course id")
    source_course_external_id: str = Field(..., description="External provider course id")
    material_external_ids: list[str] = Field(default_factory=list, description="External material ids to import")
    target_session_id: Optional[int] = Field(None, description="Optional AristAI session id")
    uploaded_by: Optional[int] = Field(None, description="Optional AristAI user id")
    overwrite_title_prefix: Optional[str] = Field(None, description="Optional prefix added to imported title")


class ImportItemResult(BaseModel):
    material_external_id: str
    status: str
    message: str
    created_material_id: Optional[int] = None


class ImportResponse(BaseModel):
    provider: str
    imported_count: int
    failed_count: int
    results: list[ImportItemResult]


@router.get("/providers", response_model=list[ProviderStatus])
def get_providers() -> list[ProviderStatus]:
    statuses: list[ProviderStatus] = []
    for provider_name in list_supported_providers():
        configured = False
        enabled = provider_name == "canvas"
        if provider_name == "canvas":
            configured = get_provider("canvas").is_configured()
        statuses.append(
            ProviderStatus(name=provider_name, configured=configured, enabled=enabled)
        )
    return statuses


@router.get("/{provider}/courses", response_model=list[ExternalCourseResponse])
def list_external_courses(provider: str):
    try:
        p = get_provider(provider)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not p.is_configured():
        raise HTTPException(status_code=400, detail=f"{provider} provider is not configured.")

    return [ExternalCourseResponse(**course.__dict__) for course in p.list_courses()]


@router.get("/{provider}/courses/{course_external_id}/materials", response_model=list[ExternalMaterialResponse])
def list_external_materials(
    provider: str,
    course_external_id: str,
):
    try:
        p = get_provider(provider)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not p.is_configured():
        raise HTTPException(status_code=400, detail=f"{provider} provider is not configured.")

    return [ExternalMaterialResponse(**m.__dict__) for m in p.list_materials(course_external_id)]


@router.post("/{provider}/import", response_model=ImportResponse)
def import_materials(
    provider: str,
    request: ImportRequest,
    user_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    try:
        p = get_provider(provider)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not p.is_configured():
        raise HTTPException(status_code=400, detail=f"{provider} provider is not configured.")

    if not request.material_external_ids:
        raise HTTPException(status_code=400, detail="material_external_ids cannot be empty.")

    target_course = db.query(Course).filter(Course.id == request.target_course_id).first()
    if not target_course:
        raise HTTPException(status_code=404, detail="Target course not found.")

    if request.target_session_id is not None:
        session = db.query(SessionModel).filter(
            SessionModel.id == request.target_session_id,
            SessionModel.course_id == request.target_course_id,
        ).first()
        if not session:
            raise HTTPException(status_code=404, detail="Target session not found for target course.")

    s3_service = get_s3_service()
    if not s3_service.is_enabled():
        raise HTTPException(status_code=503, detail="S3 is not configured. Cannot import materials.")

    results: list[ImportItemResult] = []
    imported_count = 0
    failed_count = 0

    actor_id = request.uploaded_by if request.uploaded_by is not None else user_id
    prefix = request.overwrite_title_prefix.strip() if request.overwrite_title_prefix else ""

    for external_id in request.material_external_ids:
        try:
            content_bytes, material_meta = p.download_material(external_id)
            if not content_bytes:
                raise RuntimeError("Downloaded file is empty.")

            s3_key = s3_service.generate_s3_key(
                request.target_course_id,
                material_meta.filename,
                request.target_session_id,
            )
            file_like = io.BytesIO(content_bytes)
            ok, err = s3_service.upload_file(
                file_like,
                s3_key,
                material_meta.content_type,
                material_meta.filename,
            )
            if not ok:
                raise RuntimeError(err or "S3 upload failed.")

            title = material_meta.title
            if prefix:
                title = f"{prefix}{title}"

            record = CourseMaterial(
                course_id=request.target_course_id,
                session_id=request.target_session_id,
                filename=material_meta.filename,
                s3_key=s3_key,
                file_size=material_meta.size_bytes or len(content_bytes),
                content_type=material_meta.content_type,
                title=title,
                description=f"Imported from {provider} (external id: {external_id})",
                uploaded_by=actor_id,
            )
            db.add(record)
            db.commit()
            db.refresh(record)

            imported_count += 1
            results.append(
                ImportItemResult(
                    material_external_id=external_id,
                    status="imported",
                    message="Imported successfully.",
                    created_material_id=record.id,
                )
            )
        except Exception as exc:
            db.rollback()
            failed_count += 1
            results.append(
                ImportItemResult(
                    material_external_id=external_id,
                    status="failed",
                    message=str(exc),
                )
            )

    return ImportResponse(
        provider=provider,
        imported_count=imported_count,
        failed_count=failed_count,
        results=results,
    )
