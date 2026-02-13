"""Routes for LMS integrations (Canvas first, extensible to Blackboard/UPP)."""

from __future__ import annotations

import hashlib
import io
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.core.database import get_db
from api.models.course import Course
from api.models.course_material import CourseMaterial
from api.models.integration import (
    IntegrationConnection,
    IntegrationCourseMapping,
    IntegrationMaterialLink,
    IntegrationSyncItem,
    IntegrationSyncJob,
)
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


class IntegrationConnectionResponse(BaseModel):
    id: int
    provider: str
    user_id: int
    status: str
    provider_user_id: Optional[str] = None
    provider_user_name: Optional[str] = None
    last_checked_at: Optional[datetime] = None


class MappingRequest(BaseModel):
    target_course_id: int
    source_course_external_id: str
    source_course_name: Optional[str] = None
    created_by: Optional[int] = None


class MappingResponse(BaseModel):
    id: int
    provider: str
    external_course_id: str
    external_course_name: Optional[str] = None
    target_course_id: int
    created_by: Optional[int] = None
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ImportRequest(BaseModel):
    target_course_id: int = Field(..., description="AristAI course id")
    source_course_external_id: str = Field(..., description="External provider course id")
    material_external_ids: list[str] = Field(default_factory=list, description="External material ids to import")
    target_session_id: Optional[int] = Field(None, description="Optional AristAI session id")
    uploaded_by: Optional[int] = Field(None, description="Optional AristAI user id")
    overwrite_title_prefix: Optional[str] = Field(None, description="Optional prefix added to imported title")


class SyncRequest(BaseModel):
    target_course_id: int = Field(..., description="AristAI course id")
    source_course_external_id: str = Field(..., description="External provider course id")
    target_session_id: Optional[int] = Field(None, description="Optional AristAI session id")
    uploaded_by: Optional[int] = Field(None, description="Optional AristAI user id")
    overwrite_title_prefix: Optional[str] = Field(None, description="Optional prefix added to imported title")
    mapping_id: Optional[int] = Field(None, description="Optional course mapping id")
    material_external_ids: list[str] = Field(default_factory=list, description="Optional material ids. Empty = sync all.")


class ImportItemResult(BaseModel):
    material_external_id: str
    status: str
    message: str
    created_material_id: Optional[int] = None


class ImportResponse(BaseModel):
    provider: str
    job_id: int
    imported_count: int
    skipped_count: int
    failed_count: int
    results: list[ImportItemResult]


class SyncJobResponse(BaseModel):
    id: int
    provider: str
    source_course_external_id: str
    target_course_id: int
    target_session_id: Optional[int] = None
    triggered_by: Optional[int] = None
    status: str
    requested_count: int
    imported_count: int
    skipped_count: int
    failed_count: int
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


def _resolve_provider(provider: str):
    try:
        p = get_provider(provider)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not p.is_configured():
        raise HTTPException(status_code=400, detail=f"{provider} provider is not configured.")
    return p


def _validate_target(db: Session, target_course_id: int, target_session_id: Optional[int]) -> None:
    target_course = db.query(Course).filter(Course.id == target_course_id).first()
    if not target_course:
        raise HTTPException(status_code=404, detail="Target course not found.")

    if target_session_id is not None:
        session = db.query(SessionModel).filter(
            SessionModel.id == target_session_id,
            SessionModel.course_id == target_course_id,
        ).first()
        if not session:
            raise HTTPException(status_code=404, detail="Target session not found for target course.")


def _import_with_tracking(
    db: Session,
    provider_name: str,
    provider_obj,
    request: ImportRequest,
    actor_id: Optional[int],
    material_external_ids: list[str],
) -> ImportResponse:
    s3_service = get_s3_service()
    if not s3_service.is_enabled():
        raise HTTPException(status_code=503, detail="S3 is not configured. Cannot import materials.")

    prefix = request.overwrite_title_prefix.strip() if request.overwrite_title_prefix else ""

    job = IntegrationSyncJob(
        provider=provider_name,
        source_course_external_id=request.source_course_external_id,
        target_course_id=request.target_course_id,
        target_session_id=request.target_session_id,
        triggered_by=actor_id,
        status="running",
        requested_count=len(material_external_ids),
        started_at=datetime.now(timezone.utc),
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    results: list[ImportItemResult] = []
    imported_count = 0
    skipped_count = 0
    failed_count = 0

    for external_id in material_external_ids:
        sync_item = IntegrationSyncItem(
            job_id=job.id,
            external_material_id=external_id,
            status="queued",
        )
        db.add(sync_item)
        db.commit()
        db.refresh(sync_item)

        try:
            existing_link = db.query(IntegrationMaterialLink).filter(
                IntegrationMaterialLink.provider == provider_name,
                IntegrationMaterialLink.external_material_id == external_id,
                IntegrationMaterialLink.target_course_id == request.target_course_id,
                IntegrationMaterialLink.target_session_id == request.target_session_id,
            ).first()
            if existing_link:
                skipped_count += 1
                msg = f"Already imported as material id {existing_link.course_material_id}."
                sync_item.status = "skipped"
                sync_item.message = msg
                sync_item.course_material_id = existing_link.course_material_id
                db.commit()
                results.append(
                    ImportItemResult(
                        material_external_id=external_id,
                        status="skipped",
                        message=msg,
                        created_material_id=existing_link.course_material_id,
                    )
                )
                continue

            content_bytes, material_meta = provider_obj.download_material(external_id)
            if not content_bytes:
                raise RuntimeError("Downloaded file is empty.")

            checksum = hashlib.sha256(content_bytes).hexdigest()

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

            title = f"{prefix}{material_meta.title}" if prefix else material_meta.title
            course_material = CourseMaterial(
                course_id=request.target_course_id,
                session_id=request.target_session_id,
                filename=material_meta.filename,
                s3_key=s3_key,
                file_size=material_meta.size_bytes or len(content_bytes),
                content_type=material_meta.content_type,
                title=title,
                description=f"Imported from {provider_name} (external id: {external_id})",
                uploaded_by=actor_id,
            )
            db.add(course_material)
            db.commit()
            db.refresh(course_material)

            db.add(
                IntegrationMaterialLink(
                    provider=provider_name,
                    external_material_id=external_id,
                    external_course_id=request.source_course_external_id,
                    target_course_id=request.target_course_id,
                    target_session_id=request.target_session_id,
                    course_material_id=course_material.id,
                    checksum_sha256=checksum,
                )
            )
            db.commit()

            imported_count += 1
            sync_item.status = "imported"
            sync_item.message = "Imported successfully."
            sync_item.course_material_id = course_material.id
            sync_item.external_material_name = material_meta.title
            db.commit()
            results.append(
                ImportItemResult(
                    material_external_id=external_id,
                    status="imported",
                    message="Imported successfully.",
                    created_material_id=course_material.id,
                )
            )
        except Exception as exc:
            db.rollback()
            failed_count += 1
            sync_item.status = "failed"
            sync_item.message = str(exc)
            db.add(sync_item)
            db.commit()
            results.append(
                ImportItemResult(
                    material_external_id=external_id,
                    status="failed",
                    message=str(exc),
                )
            )

    job.imported_count = imported_count
    job.skipped_count = skipped_count
    job.failed_count = failed_count
    job.status = "failed" if failed_count and imported_count == 0 else "completed"
    job.completed_at = datetime.now(timezone.utc)
    db.add(job)
    db.commit()

    return ImportResponse(
        provider=provider_name,
        job_id=job.id,
        imported_count=imported_count,
        skipped_count=skipped_count,
        failed_count=failed_count,
        results=results,
    )


@router.get("/providers", response_model=list[ProviderStatus])
def get_providers() -> list[ProviderStatus]:
    statuses: list[ProviderStatus] = []
    for provider_name in list_supported_providers():
        configured = False
        enabled = provider_name == "canvas"
        if provider_name == "canvas":
            configured = get_provider("canvas").is_configured()
        statuses.append(ProviderStatus(name=provider_name, configured=configured, enabled=enabled))
    return statuses


@router.post("/{provider}/connections/check", response_model=IntegrationConnectionResponse)
def check_connection(
    provider: str,
    user_id: int = Query(...),
    db: Session = Depends(get_db),
):
    p = _resolve_provider(provider)
    courses = p.list_courses()
    provider_user_name = "Connected User"
    if courses:
        provider_user_name = courses[0].title

    connection = db.query(IntegrationConnection).filter(
        IntegrationConnection.provider == provider,
        IntegrationConnection.user_id == user_id,
    ).first()
    if not connection:
        connection = IntegrationConnection(provider=provider, user_id=user_id)
        db.add(connection)

    connection.status = "active"
    connection.provider_user_name = provider_user_name
    connection.last_checked_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(connection)

    return IntegrationConnectionResponse(
        id=connection.id,
        provider=connection.provider,
        user_id=connection.user_id,
        status=connection.status,
        provider_user_id=connection.provider_user_id,
        provider_user_name=connection.provider_user_name,
        last_checked_at=connection.last_checked_at,
    )


@router.get("/{provider}/connections", response_model=list[IntegrationConnectionResponse])
def list_connections(
    provider: str,
    user_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    _resolve_provider(provider)
    q = db.query(IntegrationConnection).filter(IntegrationConnection.provider == provider)
    if user_id is not None:
        q = q.filter(IntegrationConnection.user_id == user_id)
    records = q.order_by(IntegrationConnection.updated_at.desc()).all()
    return [
        IntegrationConnectionResponse(
            id=r.id,
            provider=r.provider,
            user_id=r.user_id,
            status=r.status,
            provider_user_id=r.provider_user_id,
            provider_user_name=r.provider_user_name,
            last_checked_at=r.last_checked_at,
        )
        for r in records
    ]


@router.get("/{provider}/courses", response_model=list[ExternalCourseResponse])
def list_external_courses(provider: str):
    p = _resolve_provider(provider)
    return [ExternalCourseResponse(**course.__dict__) for course in p.list_courses()]


@router.get("/{provider}/courses/{course_external_id}/materials", response_model=list[ExternalMaterialResponse])
def list_external_materials(provider: str, course_external_id: str):
    p = _resolve_provider(provider)
    return [ExternalMaterialResponse(**m.__dict__) for m in p.list_materials(course_external_id)]


@router.get("/{provider}/mappings", response_model=list[MappingResponse])
def list_mappings(
    provider: str,
    target_course_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    _resolve_provider(provider)
    q = db.query(IntegrationCourseMapping).filter(
        IntegrationCourseMapping.provider == provider,
        IntegrationCourseMapping.is_active.is_(True),
    )
    if target_course_id is not None:
        q = q.filter(IntegrationCourseMapping.target_course_id == target_course_id)
    mappings = q.order_by(IntegrationCourseMapping.updated_at.desc()).all()
    return [
        MappingResponse(
            id=m.id,
            provider=m.provider,
            external_course_id=m.external_course_id,
            external_course_name=m.external_course_name,
            target_course_id=m.target_course_id,
            created_by=m.created_by,
            is_active=m.is_active,
            created_at=m.created_at,
            updated_at=m.updated_at,
        )
        for m in mappings
    ]


@router.post("/{provider}/mappings", response_model=MappingResponse)
def create_mapping(
    provider: str,
    request: MappingRequest,
    db: Session = Depends(get_db),
):
    _resolve_provider(provider)
    _validate_target(db, request.target_course_id, None)

    mapping = db.query(IntegrationCourseMapping).filter(
        IntegrationCourseMapping.provider == provider,
        IntegrationCourseMapping.external_course_id == request.source_course_external_id,
        IntegrationCourseMapping.target_course_id == request.target_course_id,
    ).first()

    if not mapping:
        mapping = IntegrationCourseMapping(
            provider=provider,
            external_course_id=request.source_course_external_id,
            target_course_id=request.target_course_id,
        )
        db.add(mapping)

    mapping.external_course_name = request.source_course_name
    mapping.created_by = request.created_by
    mapping.is_active = True
    db.commit()
    db.refresh(mapping)

    return MappingResponse(
        id=mapping.id,
        provider=mapping.provider,
        external_course_id=mapping.external_course_id,
        external_course_name=mapping.external_course_name,
        target_course_id=mapping.target_course_id,
        created_by=mapping.created_by,
        is_active=mapping.is_active,
        created_at=mapping.created_at,
        updated_at=mapping.updated_at,
    )


@router.get("/sync-jobs", response_model=list[SyncJobResponse])
def list_sync_jobs(
    provider: Optional[str] = Query(None),
    target_course_id: Optional[int] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    q = db.query(IntegrationSyncJob)
    if provider:
        q = q.filter(IntegrationSyncJob.provider == provider)
    if target_course_id:
        q = q.filter(IntegrationSyncJob.target_course_id == target_course_id)
    jobs = q.order_by(IntegrationSyncJob.created_at.desc()).limit(limit).all()
    return [
        SyncJobResponse(
            id=j.id,
            provider=j.provider,
            source_course_external_id=j.source_course_external_id,
            target_course_id=j.target_course_id,
            target_session_id=j.target_session_id,
            triggered_by=j.triggered_by,
            status=j.status,
            requested_count=j.requested_count,
            imported_count=j.imported_count,
            skipped_count=j.skipped_count,
            failed_count=j.failed_count,
            error_message=j.error_message,
            started_at=j.started_at,
            completed_at=j.completed_at,
            created_at=j.created_at,
        )
        for j in jobs
    ]


@router.post("/{provider}/import", response_model=ImportResponse)
def import_materials(
    provider: str,
    request: ImportRequest,
    user_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    p = _resolve_provider(provider)
    if not request.material_external_ids:
        raise HTTPException(status_code=400, detail="material_external_ids cannot be empty.")
    _validate_target(db, request.target_course_id, request.target_session_id)

    actor_id = request.uploaded_by if request.uploaded_by is not None else user_id
    return _import_with_tracking(db, provider, p, request, actor_id, request.material_external_ids)


@router.post("/{provider}/sync", response_model=ImportResponse)
def sync_materials(
    provider: str,
    request: SyncRequest,
    user_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    p = _resolve_provider(provider)
    _validate_target(db, request.target_course_id, request.target_session_id)

    if request.mapping_id is not None:
        mapping = db.query(IntegrationCourseMapping).filter(
            IntegrationCourseMapping.id == request.mapping_id,
            IntegrationCourseMapping.provider == provider,
            IntegrationCourseMapping.is_active.is_(True),
        ).first()
        if not mapping:
            raise HTTPException(status_code=404, detail="Mapping not found.")
        request.source_course_external_id = mapping.external_course_id
        request.target_course_id = mapping.target_course_id

    external_ids = request.material_external_ids
    if not external_ids:
        materials = p.list_materials(request.source_course_external_id)
        external_ids = [m.external_id for m in materials]

    import_request = ImportRequest(
        target_course_id=request.target_course_id,
        source_course_external_id=request.source_course_external_id,
        material_external_ids=external_ids,
        target_session_id=request.target_session_id,
        uploaded_by=request.uploaded_by,
        overwrite_title_prefix=request.overwrite_title_prefix,
    )
    actor_id = request.uploaded_by if request.uploaded_by is not None else user_id
    return _import_with_tracking(db, provider, p, import_request, actor_id, external_ids)
