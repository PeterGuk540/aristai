"""Routes for LMS integrations (Canvas first, extensible to Blackboard)."""

from __future__ import annotations

import hashlib
import io
import json
import os
import hmac
import base64
import re
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import quote_plus

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.core.database import get_db
from api.models.course import Course, generate_join_code
from api.models.course_material import CourseMaterial
from api.models.enrollment import Enrollment
from api.models.integration import (
    IntegrationConnection,
    IntegrationCourseMapping,
    IntegrationMaterialLink,
    IntegrationProviderConnection,
    IntegrationSessionLink,
    IntegrationSyncItem,
    IntegrationSyncJob,
)
from api.models.session import Session as SessionModel
from api.models.session import SessionStatus
from api.models.user import AuthProvider, User, UserRole
from api.services.integrations.registry import get_provider, list_supported_providers
from api.services.integrations.secrets import decrypt_secret, encrypt_secret
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


class ExternalSessionResponse(BaseModel):
    provider: str
    external_id: str
    course_external_id: str
    title: str
    week_number: Optional[int] = None
    description: Optional[str] = None


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
    session_external_id: Optional[str] = None


class IntegrationConnectionResponse(BaseModel):
    id: int
    provider: str
    user_id: int
    status: str
    provider_user_id: Optional[str] = None
    provider_user_name: Optional[str] = None
    last_checked_at: Optional[datetime] = None


class ProviderConnectionRequest(BaseModel):
    label: str
    api_base_url: str
    api_token: Optional[str] = ""
    is_default: bool = False
    created_by: Optional[int] = None


class ProviderOAuthStartRequest(BaseModel):
    label: str
    api_base_url: str
    created_by: Optional[int] = None
    redirect_uri: str


class ProviderOAuthStartResponse(BaseModel):
    authorization_url: str
    state: str


class ProviderOAuthExchangeRequest(BaseModel):
    code: str
    state: str
    redirect_uri: str


class ProviderConnectionResponse(BaseModel):
    id: int
    provider: str
    label: str
    api_base_url: str
    token_masked: str
    is_active: bool
    is_default: bool
    created_by: Optional[int] = None
    last_tested_at: Optional[datetime] = None
    last_test_status: Optional[str] = None
    last_test_error: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ImportCourseRequest(BaseModel):
    source_connection_id: Optional[int] = None
    created_by: Optional[int] = None
    source_course_name: Optional[str] = None


class ImportCourseResponse(BaseModel):
    provider: str
    source_connection_id: Optional[int] = None
    source_course_external_id: str
    target_course_id: int
    target_course_title: str
    mapping_id: int
    created: bool


class SyncRosterRequest(BaseModel):
    target_course_id: Optional[int] = None
    source_course_external_id: str
    source_connection_id: Optional[int] = None
    mapping_id: Optional[int] = None
    created_by: Optional[int] = None


class SyncRosterResponse(BaseModel):
    provider: str
    source_connection_id: Optional[int] = None
    source_course_external_id: str
    target_course_id: int
    scanned_count: int
    enrolled_count: int
    created_users_count: int
    skipped_count: int
    missing_email_count: int


class MappingRequest(BaseModel):
    target_course_id: int
    source_course_external_id: str
    source_course_name: Optional[str] = None
    source_connection_id: Optional[int] = None
    created_by: Optional[int] = None


class MappingResponse(BaseModel):
    id: int
    provider: str
    external_course_id: str
    external_course_name: Optional[str] = None
    source_connection_id: Optional[int] = None
    target_course_id: int
    created_by: Optional[int] = None
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ImportRequest(BaseModel):
    target_course_id: Optional[int] = Field(None, description="AristAI course id")
    source_course_external_id: str = Field(..., description="External provider course id")
    material_external_ids: list[str] = Field(default_factory=list, description="External material ids to import")
    source_connection_id: Optional[int] = Field(None, description="Optional provider connection id")
    target_session_id: Optional[int] = Field(None, description="Optional AristAI session id")
    uploaded_by: Optional[int] = Field(None, description="Optional AristAI user id")
    overwrite_title_prefix: Optional[str] = Field(None, description="Optional prefix added to imported title")


class SyncRequest(BaseModel):
    target_course_id: Optional[int] = Field(None, description="AristAI course id")
    source_course_external_id: str = Field(..., description="External provider course id")
    source_connection_id: Optional[int] = Field(None, description="Optional provider connection id")
    target_session_id: Optional[int] = Field(None, description="Optional AristAI session id")
    uploaded_by: Optional[int] = Field(None, description="Optional AristAI user id")
    overwrite_title_prefix: Optional[str] = Field(None, description="Optional prefix added to imported title")
    mapping_id: Optional[int] = Field(None, description="Optional course mapping id")
    material_external_ids: list[str] = Field(default_factory=list, description="Optional material ids. Empty = sync all.")


class AsyncSyncResponse(BaseModel):
    """Response for async sync - returns job ID immediately."""
    job_id: int
    task_id: str
    status: str = "queued"
    message: str = "Sync job queued for background processing"


class ImportItemResult(BaseModel):
    material_external_id: str
    status: str
    message: str
    created_material_id: Optional[int] = None


class ImportResponse(BaseModel):
    provider: str
    job_id: int
    target_course_id: Optional[int] = None
    target_course_title: Optional[str] = None
    created_target_course: bool = False
    imported_count: int
    skipped_count: int
    failed_count: int
    results: list[ImportItemResult]


class SyncJobResponse(BaseModel):
    id: int
    provider: str
    source_course_external_id: str
    source_connection_id: Optional[int] = None
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


def _mask_token(token: str) -> str:
    if not token:
        return ""
    if len(token) <= 6:
        return "*" * len(token)
    return f"{token[:3]}...{token[-3:]}"


def _provider_display_name(provider: str) -> str:
    p = (provider or "").strip().lower()
    if p == "upp":
        return "UPP"
    return p.title()


def _is_admin(db: Session, user_id: Optional[int]) -> bool:
    if user_id is None:
        return False
    user = db.query(User).filter(User.id == user_id).first()
    return bool(user and user.is_admin)


def _assert_connection_access(
    db: Session,
    connection: IntegrationProviderConnection,
    actor_user_id: Optional[int],
) -> None:
    if actor_user_id is None:
        raise HTTPException(status_code=403, detail="user_id is required for provider connection access.")
    if _is_admin(db, actor_user_id):
        return
    if connection.created_by != actor_user_id:
        raise HTTPException(status_code=403, detail="You do not have access to this provider connection.")


def _oauth_state_secret() -> str:
    return os.getenv("INTEGRATIONS_SECRET_KEY", "aristai-integrations-dev-key-change-me")


def _sign_oauth_state(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    body = base64.urlsafe_b64encode(raw).decode("utf-8")
    sig = hmac.new(_oauth_state_secret().encode("utf-8"), body.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{body}.{sig}"


def _verify_oauth_state(token: str) -> dict[str, Any]:
    try:
        body, sig = token.rsplit(".", 1)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid OAuth state format.") from exc
    expected = hmac.new(_oauth_state_secret().encode("utf-8"), body.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        raise HTTPException(status_code=400, detail="Invalid OAuth state signature.")
    try:
        payload = json.loads(base64.urlsafe_b64decode(body.encode("utf-8")).decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail="Invalid OAuth state payload.") from exc
    return payload


def _canvas_site_root(api_base_url: str) -> str:
    base = api_base_url.strip().rstrip("/")
    if base.endswith("/api/v1"):
        return base[:-7]
    return base


def _connection_to_response(record: IntegrationProviderConnection) -> ProviderConnectionResponse:
    token_plain = decrypt_secret(record.api_token_encrypted)
    return ProviderConnectionResponse(
        id=record.id,
        provider=record.provider,
        label=record.label,
        api_base_url=record.api_base_url,
        token_masked=_mask_token(token_plain),
        is_active=record.is_active,
        is_default=record.is_default,
        created_by=record.created_by,
        last_tested_at=record.last_tested_at,
        last_test_status=record.last_test_status,
        last_test_error=record.last_test_error,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _resolve_config_connection(
    db: Session,
    provider: str,
    connection_id: Optional[int],
    actor_user_id: Optional[int] = None,
) -> Optional[IntegrationProviderConnection]:
    if connection_id is not None:
        row = db.query(IntegrationProviderConnection).filter(
            IntegrationProviderConnection.id == connection_id,
            IntegrationProviderConnection.provider == provider,
            IntegrationProviderConnection.is_active.is_(True),
        ).first()
        if not row:
            raise HTTPException(status_code=404, detail="Provider connection not found.")
        _assert_connection_access(db, row, actor_user_id)
        return row

    q = db.query(IntegrationProviderConnection).filter(
        IntegrationProviderConnection.provider == provider,
        IntegrationProviderConnection.is_active.is_(True),
        IntegrationProviderConnection.is_default.is_(True),
    )
    if actor_user_id is not None and not _is_admin(db, actor_user_id):
        q = q.filter(IntegrationProviderConnection.created_by == actor_user_id)
    row = q.first()
    if row is not None and actor_user_id is not None:
        _assert_connection_access(db, row, actor_user_id)
    return row


def _resolve_provider(
    provider: str,
    db: Optional[Session] = None,
    connection_id: Optional[int] = None,
    require_configured: bool = True,
    actor_user_id: Optional[int] = None,
):
    config: dict[str, Any] | None = None
    if db is not None:
        cfg = _resolve_config_connection(db, provider, connection_id, actor_user_id=actor_user_id)
        if cfg is not None:
            config = {
                "api_base_url": cfg.api_base_url,
                "api_token": decrypt_secret(cfg.api_token_encrypted),
            }

    try:
        p = get_provider(provider, config=config)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if require_configured and not p.is_configured():
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


def _ensure_target_course(
    db: Session,
    provider: str,
    provider_obj,
    source_course_external_id: str,
    source_connection_id: Optional[int],
    target_course_id: Optional[int],
    created_by: Optional[int],
) -> tuple[int, str, bool]:
    """
    Ensure a local target course exists.
    Returns: (target_course_id, title, created_target_course)
    """
    if target_course_id is not None:
        target = db.query(Course).filter(Course.id == target_course_id).first()
        if not target:
            raise HTTPException(status_code=404, detail="Target course not found.")
        return target.id, target.title, False

    existing_mapping = db.query(IntegrationCourseMapping).filter(
        IntegrationCourseMapping.provider == provider,
        IntegrationCourseMapping.external_course_id == source_course_external_id,
        IntegrationCourseMapping.source_connection_id == source_connection_id,
        IntegrationCourseMapping.is_active.is_(True),
    ).order_by(IntegrationCourseMapping.updated_at.desc()).first()
    if existing_mapping:
        mapped_course = db.query(Course).filter(Course.id == existing_mapping.target_course_id).first()
        if mapped_course:
            return mapped_course.id, mapped_course.title, False

    source_title: Optional[str] = None
    try:
        for c in provider_obj.list_courses():
            if c.external_id == source_course_external_id:
                source_title = c.title
                break
    except Exception:
        source_title = None

    title = source_title or f"Imported {_provider_display_name(provider)} Course {source_course_external_id}"
    join_code = generate_join_code()
    while db.query(Course).filter(Course.join_code == join_code).first():
        join_code = generate_join_code()

    new_course = Course(title=title, created_by=created_by, join_code=join_code)
    db.add(new_course)
    db.flush()

    materials_session = SessionModel(
        course_id=new_course.id,
        title="Course Materials",
        status=SessionStatus.completed,
        plan_json={
            "is_materials_session": True,
            "description": "Repository for course readings, documents, and other materials.",
        },
    )
    db.add(materials_session)
    db.flush()

    mapping = IntegrationCourseMapping(
        provider=provider,
        external_course_id=source_course_external_id,
        external_course_name=title,
        source_connection_id=source_connection_id,
        target_course_id=new_course.id,
        created_by=created_by,
        is_active=True,
    )
    db.add(mapping)
    db.commit()
    db.refresh(new_course)
    return new_course.id, new_course.title, True


def _sync_sessions_from_external(
    db: Session,
    provider: str,
    provider_obj: Any,
    source_course_external_id: str,
    source_connection_id: Optional[int],
    target_course_id: int,
) -> dict[str, int]:
    """Sync sessions (e.g., Semanas) from external course to AristAI sessions.

    Returns a mapping of external_session_id -> target_session_id for associating materials.
    Creates sessions in AristAI if they don't exist, even if they have no materials.
    """
    session_mapping: dict[str, int] = {}

    try:
        external_sessions = provider_obj.list_sessions(source_course_external_id)
    except Exception:
        # Provider doesn't support sessions or error occurred
        return session_mapping

    if not external_sessions:
        return session_mapping

    for ext_session in external_sessions:
        # Check if this session is already linked
        existing_link = db.query(IntegrationSessionLink).filter(
            IntegrationSessionLink.provider == provider,
            IntegrationSessionLink.external_session_id == ext_session.external_id,
            IntegrationSessionLink.target_course_id == target_course_id,
            IntegrationSessionLink.source_connection_id == source_connection_id,
        ).first()

        if existing_link:
            # Session already imported, use existing mapping
            session_mapping[ext_session.external_id] = existing_link.target_session_id
            continue

        # Create a new session in AristAI
        new_session = SessionModel(
            course_id=target_course_id,
            title=ext_session.title,
            status=SessionStatus.draft,
            plan_json={
                "is_imported_session": True,
                "external_provider": provider,
                "external_session_id": ext_session.external_id,
                "week_number": ext_session.week_number,
                "description": ext_session.description or f"Imported from {provider.upper()}",
            },
        )
        db.add(new_session)
        db.flush()

        # Create the link record
        session_link = IntegrationSessionLink(
            provider=provider,
            external_session_id=ext_session.external_id,
            external_course_id=source_course_external_id,
            external_session_title=ext_session.title,
            week_number=ext_session.week_number,
            source_connection_id=source_connection_id,
            target_course_id=target_course_id,
            target_session_id=new_session.id,
        )
        db.add(session_link)
        db.flush()

        session_mapping[ext_session.external_id] = new_session.id

    db.commit()
    return session_mapping


def _import_materials_batch(
    db: Session,
    job: IntegrationSyncJob,
    provider_name: str,
    provider_obj,
    source_course_external_id: str,
    source_connection_id: Optional[int],
    target_course_id: int,
    target_session_id: Optional[int],
    actor_id: Optional[int],
    material_external_ids: list[str],
    session_mapping: Optional[dict[str, int]] = None,
    material_session_map: Optional[dict[str, str]] = None,
    overwrite_title_prefix: Optional[str] = None,
    material_title_map: Optional[dict[str, str]] = None,
) -> dict:
    """Import materials in batch, updating the provided job record.

    Returns dict with imported_count, skipped_count, failed_count, results.
    This function is used by both sync endpoint and Celery background task.
    """
    s3_service = get_s3_service()
    if not s3_service.is_enabled():
        raise RuntimeError("S3 is not configured. Cannot import materials.")

    prefix = overwrite_title_prefix.strip() if overwrite_title_prefix else ""

    results: list[dict] = []
    imported_count = 0
    skipped_count = 0
    failed_count = 0

    for external_id in material_external_ids:
        # Determine target session for this material
        resolved_target_session_id = target_session_id
        if session_mapping and material_session_map:
            mat_session_ext_id = material_session_map.get(external_id)
            if mat_session_ext_id and mat_session_ext_id in session_mapping:
                resolved_target_session_id = session_mapping[mat_session_ext_id]

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
                IntegrationMaterialLink.target_course_id == target_course_id,
                IntegrationMaterialLink.target_session_id == resolved_target_session_id,
                IntegrationMaterialLink.source_connection_id == source_connection_id,
            ).first()
            if existing_link:
                # Update title of existing material if a better title is now available
                if material_title_map and existing_link.course_material_id:
                    new_title_raw = material_title_map.get(external_id, "")
                    if new_title_raw:
                        new_title = f"{prefix}{new_title_raw}" if prefix else new_title_raw
                        existing_mat = db.query(CourseMaterial).filter(
                            CourseMaterial.id == existing_link.course_material_id
                        ).first()
                        if existing_mat and existing_mat.title:
                            old_looks_like_filename = bool(re.search(
                                r'\.\w{2,5}$', existing_mat.title.strip()
                            ))
                            new_looks_like_filename = bool(re.search(
                                r'\.\w{2,5}$', new_title.strip()
                            ))
                            if old_looks_like_filename and not new_looks_like_filename:
                                existing_mat.title = new_title
                                db.commit()

                skipped_count += 1
                msg = f"Already imported as material id {existing_link.course_material_id}."
                sync_item.status = "skipped"
                sync_item.message = msg
                sync_item.course_material_id = existing_link.course_material_id
                db.commit()
                results.append({
                    "material_external_id": external_id,
                    "status": "skipped",
                    "message": msg,
                    "created_material_id": existing_link.course_material_id,
                })
                continue

            content_bytes, material_meta = provider_obj.download_material(external_id)
            if not content_bytes:
                raise RuntimeError("Downloaded file is empty.")

            # Pick the best title available. download_material() may return
            # a Content-Disposition filename (good) or a URL-derived name (bad).
            # list_materials() may return a DOM-extracted name (good) or also
            # a URL-derived name (bad). Prefer whichever looks more human-readable.
            if material_title_map:
                map_title = material_title_map.get(external_id, "")
                if map_title:
                    dl_title = material_meta.title or ""
                    # A hash-like name has mostly hex/digits separated by underscores/spaces
                    map_looks_like_hash = bool(re.match(
                        r'^[\da-fA-F_ \-]{10,}', map_title.strip()
                    ))
                    dl_looks_like_hash = bool(re.match(
                        r'^[\da-fA-F_ \-]{10,}', dl_title.strip()
                    ))
                    # Only override if map_title is better than download title
                    if not map_looks_like_hash and dl_looks_like_hash:
                        material_meta.title = map_title
                    elif map_looks_like_hash == dl_looks_like_hash and len(map_title) > len(dl_title):
                        material_meta.title = map_title

            checksum = hashlib.sha256(content_bytes).hexdigest()

            s3_key = s3_service.generate_s3_key(
                target_course_id,
                material_meta.filename,
                resolved_target_session_id,
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
                course_id=target_course_id,
                session_id=resolved_target_session_id,
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
                    external_course_id=source_course_external_id,
                    source_connection_id=source_connection_id,
                    target_course_id=target_course_id,
                    target_session_id=resolved_target_session_id,
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
            results.append({
                "material_external_id": external_id,
                "status": "imported",
                "message": "Imported successfully.",
                "created_material_id": course_material.id,
            })
        except Exception as exc:
            db.rollback()
            failed_count += 1
            sync_item.status = "failed"
            sync_item.message = str(exc)
            db.add(sync_item)
            db.commit()
            results.append({
                "material_external_id": external_id,
                "status": "failed",
                "message": str(exc),
            })

    return {
        "imported_count": imported_count,
        "skipped_count": skipped_count,
        "failed_count": failed_count,
        "results": results,
    }


def _import_with_tracking(
    db: Session,
    provider_name: str,
    provider_obj,
    request: ImportRequest,
    actor_id: Optional[int],
    material_external_ids: list[str],
    session_mapping: Optional[dict[str, int]] = None,
    material_session_map: Optional[dict[str, str]] = None,
    material_title_map: Optional[dict[str, str]] = None,
) -> ImportResponse:
    """Synchronous import with tracking - creates job and imports materials."""
    s3_service = get_s3_service()
    if not s3_service.is_enabled():
        raise HTTPException(status_code=503, detail="S3 is not configured. Cannot import materials.")

    # Create job record
    job = IntegrationSyncJob(
        provider=provider_name,
        source_course_external_id=request.source_course_external_id,
        source_connection_id=request.source_connection_id,
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

    # Use shared batch import function
    result = _import_materials_batch(
        db=db,
        job=job,
        provider_name=provider_name,
        provider_obj=provider_obj,
        source_course_external_id=request.source_course_external_id,
        source_connection_id=request.source_connection_id,
        target_course_id=request.target_course_id,
        target_session_id=request.target_session_id,
        actor_id=actor_id,
        material_external_ids=material_external_ids,
        session_mapping=session_mapping,
        material_session_map=material_session_map,
        overwrite_title_prefix=request.overwrite_title_prefix,
        material_title_map=material_title_map,
    )

    # Update job completion
    job.imported_count = result["imported_count"]
    job.skipped_count = result["skipped_count"]
    job.failed_count = result["failed_count"]
    job.status = "failed" if result["failed_count"] and result["imported_count"] == 0 else "completed"
    job.completed_at = datetime.now(timezone.utc)
    db.add(job)
    db.commit()

    # Convert dict results to ImportItemResult
    results = [
        ImportItemResult(
            material_external_id=r["material_external_id"],
            status=r["status"],
            message=r["message"],
            created_material_id=r.get("created_material_id"),
        )
        for r in result["results"]
    ]

    return ImportResponse(
        provider=provider_name,
        job_id=job.id,
        imported_count=result["imported_count"],
        skipped_count=result["skipped_count"],
        failed_count=result["failed_count"],
        results=results,
    )


@router.get("/providers", response_model=list[ProviderStatus])
def get_providers() -> list[ProviderStatus]:
    statuses: list[ProviderStatus] = []
    for provider_name in list_supported_providers():
        provider_obj = get_provider(provider_name)
        configured = provider_obj.is_configured()
        enabled = True
        statuses.append(ProviderStatus(name=provider_name, configured=configured, enabled=enabled))
    return statuses


def _oauth_config_for_provider(provider: str, api_base_url: str) -> dict[str, str]:
    p = provider.strip().lower()
    base = api_base_url.strip().rstrip("/")
    if p == "canvas":
        site_root = _canvas_site_root(base)
        return {
            "client_id": os.getenv("CANVAS_OAUTH_CLIENT_ID", "").strip(),
            "client_secret": os.getenv("CANVAS_OAUTH_CLIENT_SECRET", "").strip(),
            "authorize_url": f"{site_root}/login/oauth2/auth",
            "token_url": f"{site_root}/login/oauth2/token",
            "scope": os.getenv("CANVAS_OAUTH_SCOPE", "").strip(),
        }

    upper = p.upper()
    authorize_url = os.getenv(f"{upper}_OAUTH_AUTHORIZE_URL", "").strip()
    token_url = os.getenv(f"{upper}_OAUTH_TOKEN_URL", "").strip()
    client_id = os.getenv(f"{upper}_OAUTH_CLIENT_ID", "").strip()
    client_secret = os.getenv(f"{upper}_OAUTH_CLIENT_SECRET", "").strip()
    scope = os.getenv(f"{upper}_OAUTH_SCOPE", "").strip()

    if not authorize_url:
        authorize_url = f"{base}/oauth/authorize"
    if not token_url:
        token_url = f"{base}/oauth/token"

    return {
        "client_id": client_id,
        "client_secret": client_secret,
        "authorize_url": authorize_url,
        "token_url": token_url,
        "scope": scope,
    }


@router.post("/{provider}/oauth/start", response_model=ProviderOAuthStartResponse)
def start_provider_oauth(provider: str, request: ProviderOAuthStartRequest):
    if provider not in list_supported_providers():
        raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}")

    oauth_cfg = _oauth_config_for_provider(provider, request.api_base_url)
    client_id = oauth_cfg.get("client_id", "")
    if not client_id:
        raise HTTPException(status_code=400, detail=f"{provider.upper()} OAuth client id is not configured.")

    state = _sign_oauth_state(
        {
            "provider": provider,
            "label": request.label,
            "api_base_url": request.api_base_url.strip().rstrip("/"),
            "created_by": request.created_by,
            "iat": int(datetime.now(timezone.utc).timestamp()),
        }
    )
    auth_url = (
        f"{oauth_cfg['authorize_url']}"
        f"?client_id={quote_plus(client_id)}"
        f"&response_type=code"
        f"&redirect_uri={quote_plus(request.redirect_uri)}"
        f"&state={quote_plus(state)}"
    )
    scope = oauth_cfg.get("scope", "")
    if scope:
        auth_url += f"&scope={quote_plus(scope)}"
    return ProviderOAuthStartResponse(authorization_url=auth_url, state=state)


@router.post("/{provider}/oauth/exchange", response_model=ProviderConnectionResponse)
def exchange_provider_oauth(
    provider: str,
    request: ProviderOAuthExchangeRequest,
    db: Session = Depends(get_db),
):
    if provider not in list_supported_providers():
        raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}")

    payload = _verify_oauth_state(request.state)
    state_provider = str(payload.get("provider", "")).strip().lower()
    if state_provider and state_provider != provider:
        raise HTTPException(status_code=400, detail="OAuth state provider mismatch.")

    api_base_url = str(payload.get("api_base_url", "")).strip().rstrip("/")
    oauth_cfg = _oauth_config_for_provider(provider, api_base_url)
    client_id = oauth_cfg.get("client_id", "")
    client_secret = oauth_cfg.get("client_secret", "")
    if not client_id:
        raise HTTPException(status_code=400, detail=f"{provider.upper()} OAuth client id is not configured.")

    api_base_url = str(payload.get("api_base_url", "")).strip().rstrip("/")
    label = str(payload.get("label", "")).strip() or f"{_provider_display_name(provider)} Connection"
    created_by = payload.get("created_by")
    token_url = oauth_cfg["token_url"]

    try:
        with httpx.Client(timeout=30) as client:
            token_data = {
                "grant_type": "authorization_code",
                "client_id": client_id,
                "redirect_uri": request.redirect_uri,
                "code": request.code,
            }
            if client_secret:
                token_data["client_secret"] = client_secret
            response = client.post(
                token_url,
                data=token_data,
            )
            response.raise_for_status()
            token_payload = response.json()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"{_provider_display_name(provider)} OAuth exchange failed: {exc}") from exc

    access_token = str(
        token_payload.get("access_token")
        or token_payload.get("token")
        or token_payload.get("id_token")
        or ""
    ).strip()
    if not access_token:
        raise HTTPException(status_code=400, detail=f"{_provider_display_name(provider)} OAuth response missing access token.")

    row = db.query(IntegrationProviderConnection).filter(
        IntegrationProviderConnection.provider == provider,
        IntegrationProviderConnection.label == label,
    ).first()
    if row is None:
        row = IntegrationProviderConnection(provider=provider, label=label)
        db.add(row)

    existing_count = db.query(IntegrationProviderConnection).filter(
        IntegrationProviderConnection.provider == provider,
        IntegrationProviderConnection.is_active.is_(True),
    ).count()

    row.api_base_url = api_base_url
    row.api_token_encrypted = encrypt_secret(access_token)
    row.is_active = True
    row.is_default = existing_count == 0
    row.created_by = created_by
    row.last_tested_at = datetime.now(timezone.utc)
    row.last_test_status = "ok"
    row.last_test_error = None
    db.add(row)
    db.commit()
    db.refresh(row)
    return _connection_to_response(row)


@router.get("/{provider}/config-connections", response_model=list[ProviderConnectionResponse])
def list_provider_connections(
    provider: str,
    user_id: int = Query(...),
    db: Session = Depends(get_db),
):
    q = db.query(IntegrationProviderConnection).filter(
        IntegrationProviderConnection.provider == provider,
        IntegrationProviderConnection.is_active.is_(True),
    )
    if not _is_admin(db, user_id):
        q = q.filter(IntegrationProviderConnection.created_by == user_id)
    records = q.order_by(IntegrationProviderConnection.is_default.desc(), IntegrationProviderConnection.updated_at.desc()).all()
    return [_connection_to_response(r) for r in records]


@router.post("/{provider}/config-connections", response_model=ProviderConnectionResponse)
def create_provider_connection(
    provider: str,
    request: ProviderConnectionRequest,
    user_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    if provider not in list_supported_providers():
        raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}")

    actor_user_id = request.created_by if request.created_by is not None else user_id
    if actor_user_id is None:
        raise HTTPException(status_code=400, detail="user_id is required to create provider connections.")
    if (
        request.created_by is not None
        and user_id is not None
        and request.created_by != user_id
        and not _is_admin(db, user_id)
    ):
        raise HTTPException(status_code=403, detail="You cannot create provider connections for another user.")

    if request.is_default:
        db.query(IntegrationProviderConnection).filter(
            IntegrationProviderConnection.provider == provider
        ).update({"is_default": False})

    row = IntegrationProviderConnection(
        provider=provider,
        label=request.label.strip(),
        api_base_url=request.api_base_url.strip().rstrip("/"),
        api_token_encrypted=encrypt_secret((request.api_token or "").strip()),
        is_active=True,
        is_default=request.is_default,
        created_by=actor_user_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _connection_to_response(row)


@router.post("/{provider}/config-connections/{connection_id}/activate", response_model=ProviderConnectionResponse)
def activate_provider_connection(
    provider: str,
    connection_id: int,
    user_id: int = Query(...),
    db: Session = Depends(get_db),
):
    row = _resolve_config_connection(db, provider, connection_id, actor_user_id=user_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Provider connection not found.")

    update_q = db.query(IntegrationProviderConnection).filter(IntegrationProviderConnection.provider == provider)
    if not _is_admin(db, user_id):
        update_q = update_q.filter(IntegrationProviderConnection.created_by == user_id)
    update_q.update({"is_default": False})
    row.is_default = True
    row.is_active = True
    db.add(row)
    db.commit()
    db.refresh(row)
    return _connection_to_response(row)


@router.post("/{provider}/config-connections/{connection_id}/test", response_model=ProviderConnectionResponse)
def test_provider_connection(
    provider: str,
    connection_id: int,
    user_id: int = Query(...),
    db: Session = Depends(get_db),
):
    row = _resolve_config_connection(db, provider, connection_id, actor_user_id=user_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Provider connection not found.")

    row.last_tested_at = datetime.now(timezone.utc)
    try:
        p = _resolve_provider(provider, db=db, connection_id=connection_id, actor_user_id=user_id)
        p.list_courses()
        row.last_test_status = "ok"
        row.last_test_error = None
    except Exception as exc:
        row.last_test_status = "error"
        row.last_test_error = str(exc)
    db.add(row)
    db.commit()
    db.refresh(row)
    return _connection_to_response(row)


@router.post("/{provider}/connections/check", response_model=IntegrationConnectionResponse)
def check_connection(
    provider: str,
    user_id: int = Query(...),
    connection_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    p = _resolve_provider(provider, db=db, connection_id=connection_id, actor_user_id=user_id)
    try:
        courses = p.list_courses()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
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
    user_id: int = Query(...),
    db: Session = Depends(get_db),
):
    _resolve_provider(provider, db=db, require_configured=False)
    q = db.query(IntegrationConnection).filter(IntegrationConnection.provider == provider)
    if not _is_admin(db, user_id):
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
def list_external_courses(
    provider: str,
    connection_id: Optional[int] = Query(None),
    user_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    p = _resolve_provider(provider, db=db, connection_id=connection_id, actor_user_id=user_id)
    try:
        courses = p.list_courses()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return [ExternalCourseResponse(**course.__dict__) for course in courses]


@router.get("/{provider}/courses/{course_external_id}/sessions", response_model=list[ExternalSessionResponse])
def list_external_sessions(
    provider: str,
    course_external_id: str,
    connection_id: Optional[int] = Query(None),
    user_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    """List sessions/weeks for an external course."""
    p = _resolve_provider(provider, db=db, connection_id=connection_id, actor_user_id=user_id)
    try:
        sessions = p.list_sessions(course_external_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return [ExternalSessionResponse(**s.__dict__) for s in sessions]


@router.get("/{provider}/courses/{course_external_id}/materials", response_model=list[ExternalMaterialResponse])
def list_external_materials(
    provider: str,
    course_external_id: str,
    connection_id: Optional[int] = Query(None),
    user_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    p = _resolve_provider(provider, db=db, connection_id=connection_id, actor_user_id=user_id)
    try:
        materials = p.list_materials(course_external_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return [ExternalMaterialResponse(**m.__dict__) for m in materials]


@router.post("/{provider}/courses/{course_external_id}/import-course", response_model=ImportCourseResponse)
def import_external_course(
    provider: str,
    course_external_id: str,
    request: ImportCourseRequest,
    user_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    actor_user_id = request.created_by if request.created_by is not None else user_id
    p = _resolve_provider(
        provider,
        db=db,
        connection_id=request.source_connection_id,
        actor_user_id=actor_user_id,
    )

    existing_mapping = db.query(IntegrationCourseMapping).filter(
        IntegrationCourseMapping.provider == provider,
        IntegrationCourseMapping.external_course_id == course_external_id,
        IntegrationCourseMapping.source_connection_id == request.source_connection_id,
        IntegrationCourseMapping.is_active.is_(True),
    ).first()
    if existing_mapping:
        existing_course = db.query(Course).filter(Course.id == existing_mapping.target_course_id).first()
        if existing_course:
            return ImportCourseResponse(
                provider=provider,
                source_connection_id=request.source_connection_id,
                source_course_external_id=course_external_id,
                target_course_id=existing_course.id,
                target_course_title=existing_course.title,
                mapping_id=existing_mapping.id,
                created=False,
            )

    course_name = request.source_course_name
    if not course_name:
        try:
            courses = p.list_courses()
            course_name = next((c.title for c in courses if c.external_id == course_external_id), None)
        except Exception:  # noqa: BLE001
            course_name = None
    if not course_name:
        course_name = f"Imported {_provider_display_name(provider)} Course {course_external_id}"

    join_code = generate_join_code()
    while db.query(Course).filter(Course.join_code == join_code).first():
        join_code = generate_join_code()

    new_course = Course(
        title=course_name,
        created_by=actor_user_id,
        join_code=join_code,
    )
    db.add(new_course)
    db.flush()

    materials_session = SessionModel(
        course_id=new_course.id,
        title="Course Materials",
        status=SessionStatus.completed,
        plan_json={
            "is_materials_session": True,
            "description": "Repository for course readings, documents, and other materials.",
        },
    )
    db.add(materials_session)
    db.flush()

    mapping = IntegrationCourseMapping(
        provider=provider,
        external_course_id=course_external_id,
        external_course_name=course_name,
        source_connection_id=request.source_connection_id,
        target_course_id=new_course.id,
        created_by=actor_user_id,
        is_active=True,
    )
    db.add(mapping)
    db.commit()
    db.refresh(new_course)
    db.refresh(mapping)

    return ImportCourseResponse(
        provider=provider,
        source_connection_id=request.source_connection_id,
        source_course_external_id=course_external_id,
        target_course_id=new_course.id,
        target_course_title=new_course.title,
        mapping_id=mapping.id,
        created=True,
    )


@router.get("/{provider}/mappings", response_model=list[MappingResponse])
def list_mappings(
    provider: str,
    target_course_id: Optional[int] = Query(None),
    source_connection_id: Optional[int] = Query(None),
    user_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    _resolve_provider(
        provider,
        db=db,
        connection_id=source_connection_id,
        require_configured=False,
        actor_user_id=user_id,
    )
    q = db.query(IntegrationCourseMapping).filter(
        IntegrationCourseMapping.provider == provider,
        IntegrationCourseMapping.is_active.is_(True),
    )
    if target_course_id is not None:
        q = q.filter(IntegrationCourseMapping.target_course_id == target_course_id)
    if source_connection_id is not None:
        q = q.filter(IntegrationCourseMapping.source_connection_id == source_connection_id)
    if user_id is not None and not _is_admin(db, user_id):
        q = q.filter(IntegrationCourseMapping.created_by == user_id)
    mappings = q.order_by(IntegrationCourseMapping.updated_at.desc()).all()
    return [
        MappingResponse(
            id=m.id,
            provider=m.provider,
            external_course_id=m.external_course_id,
            external_course_name=m.external_course_name,
            source_connection_id=m.source_connection_id,
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
    user_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    actor_user_id = request.created_by if request.created_by is not None else user_id
    _resolve_provider(provider, db=db, connection_id=request.source_connection_id, actor_user_id=actor_user_id)
    _validate_target(db, request.target_course_id, None)

    mapping = db.query(IntegrationCourseMapping).filter(
        IntegrationCourseMapping.provider == provider,
        IntegrationCourseMapping.external_course_id == request.source_course_external_id,
        IntegrationCourseMapping.target_course_id == request.target_course_id,
        IntegrationCourseMapping.source_connection_id == request.source_connection_id,
    ).first()

    if not mapping:
        mapping = IntegrationCourseMapping(
            provider=provider,
            external_course_id=request.source_course_external_id,
            source_connection_id=request.source_connection_id,
            target_course_id=request.target_course_id,
        )
        db.add(mapping)

    mapping.external_course_name = request.source_course_name
    mapping.created_by = actor_user_id
    mapping.is_active = True
    db.commit()
    db.refresh(mapping)

    return MappingResponse(
        id=mapping.id,
        provider=mapping.provider,
        external_course_id=mapping.external_course_id,
        external_course_name=mapping.external_course_name,
        source_connection_id=mapping.source_connection_id,
        target_course_id=mapping.target_course_id,
        created_by=mapping.created_by,
        is_active=mapping.is_active,
        created_at=mapping.created_at,
        updated_at=mapping.updated_at,
    )


@router.get("/sync-jobs", response_model=list[SyncJobResponse])
def list_sync_jobs(
    provider: Optional[str] = Query(None),
    source_connection_id: Optional[int] = Query(None),
    target_course_id: Optional[int] = Query(None),
    user_id: Optional[int] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    q = db.query(IntegrationSyncJob)
    if provider:
        q = q.filter(IntegrationSyncJob.provider == provider)
    if source_connection_id is not None:
        q = q.filter(IntegrationSyncJob.source_connection_id == source_connection_id)
    if target_course_id:
        q = q.filter(IntegrationSyncJob.target_course_id == target_course_id)
    if user_id is not None and not _is_admin(db, user_id):
        q = q.filter(IntegrationSyncJob.triggered_by == user_id)
    jobs = q.order_by(IntegrationSyncJob.created_at.desc()).limit(limit).all()
    return [
        SyncJobResponse(
            id=j.id,
            provider=j.provider,
            source_course_external_id=j.source_course_external_id,
            source_connection_id=j.source_connection_id,
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


@router.get("/sync-jobs/{job_id}", response_model=SyncJobResponse)
def get_sync_job(
    job_id: int,
    db: Session = Depends(get_db),
):
    """Get status of a specific sync job by ID."""
    job = db.query(IntegrationSyncJob).filter(IntegrationSyncJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Sync job not found.")
    return SyncJobResponse(
        id=job.id,
        provider=job.provider,
        source_course_external_id=job.source_course_external_id,
        source_connection_id=job.source_connection_id,
        target_course_id=job.target_course_id,
        target_session_id=job.target_session_id,
        triggered_by=job.triggered_by,
        status=job.status,
        requested_count=job.requested_count,
        imported_count=job.imported_count,
        skipped_count=job.skipped_count,
        failed_count=job.failed_count,
        error_message=job.error_message,
        started_at=job.started_at,
        completed_at=job.completed_at,
        created_at=job.created_at,
    )


@router.post("/{provider}/import", response_model=ImportResponse)
def import_materials(
    provider: str,
    request: ImportRequest,
    user_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    actor_id = request.uploaded_by if request.uploaded_by is not None else user_id
    p = _resolve_provider(provider, db=db, connection_id=request.source_connection_id, actor_user_id=actor_id)
    if not request.material_external_ids:
        raise HTTPException(status_code=400, detail="material_external_ids cannot be empty.")
    resolved_target_course_id, resolved_target_title, created_target_course = _ensure_target_course(
        db=db,
        provider=provider,
        provider_obj=p,
        source_course_external_id=request.source_course_external_id,
        source_connection_id=request.source_connection_id,
        target_course_id=request.target_course_id,
        created_by=actor_id,
    )
    request.target_course_id = resolved_target_course_id
    _validate_target(db, resolved_target_course_id, request.target_session_id)

    result = _import_with_tracking(db, provider, p, request, actor_id, request.material_external_ids)
    result.target_course_id = resolved_target_course_id
    result.target_course_title = resolved_target_title
    result.created_target_course = created_target_course
    return result


@router.post("/{provider}/sync", response_model=ImportResponse)
def sync_materials(
    provider: str,
    request: SyncRequest,
    user_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    actor_id = request.uploaded_by if request.uploaded_by is not None else user_id
    p = _resolve_provider(provider, db=db, connection_id=request.source_connection_id, actor_user_id=actor_id)

    if request.mapping_id is not None:
        mapping = db.query(IntegrationCourseMapping).filter(
            IntegrationCourseMapping.id == request.mapping_id,
            IntegrationCourseMapping.provider == provider,
            IntegrationCourseMapping.is_active.is_(True),
        ).first()
        if not mapping:
            raise HTTPException(status_code=404, detail="Mapping not found.")
        request.source_course_external_id = mapping.external_course_id
        request.source_connection_id = mapping.source_connection_id
        request.target_course_id = mapping.target_course_id

    resolved_target_course_id, resolved_target_title, created_target_course = _ensure_target_course(
        db=db,
        provider=provider,
        provider_obj=p,
        source_course_external_id=request.source_course_external_id,
        source_connection_id=request.source_connection_id,
        target_course_id=request.target_course_id,
        created_by=actor_id,
    )
    request.target_course_id = resolved_target_course_id
    _validate_target(db, resolved_target_course_id, request.target_session_id)

    # Sync sessions first (e.g., Semanas from UPP) to create session records
    # This creates sessions in AristAI even if they have no materials
    session_mapping = _sync_sessions_from_external(
        db=db,
        provider=provider,
        provider_obj=p,
        source_course_external_id=request.source_course_external_id,
        source_connection_id=request.source_connection_id,
        target_course_id=resolved_target_course_id,
    )

    # Fetch materials and build a map of material_external_id -> session_external_id
    external_ids = request.material_external_ids
    material_session_map: dict[str, str] = {}
    material_title_map: dict[str, str] = {}
    if not external_ids:
        try:
            materials = p.list_materials(request.source_course_external_id)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        external_ids = [m.external_id for m in materials]
        # Build the mapping from material to its session and title
        for m in materials:
            if m.session_external_id:
                material_session_map[m.external_id] = m.session_external_id
            if m.title:
                material_title_map[m.external_id] = m.title

    import_request = ImportRequest(
        target_course_id=request.target_course_id,
        source_course_external_id=request.source_course_external_id,
        source_connection_id=request.source_connection_id,
        material_external_ids=external_ids,
        target_session_id=request.target_session_id,
        uploaded_by=request.uploaded_by,
        overwrite_title_prefix=request.overwrite_title_prefix,
    )
    result = _import_with_tracking(
        db, provider, p, import_request, actor_id, external_ids,
        session_mapping=session_mapping,
        material_session_map=material_session_map,
        material_title_map=material_title_map,
    )
    result.target_course_id = resolved_target_course_id
    result.target_course_title = resolved_target_title
    result.created_target_course = created_target_course
    return result


@router.post("/{provider}/sync-async", response_model=AsyncSyncResponse)
def sync_materials_async(
    provider: str,
    request: SyncRequest,
    user_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    """Queue a background sync job for materials import.

    This endpoint returns immediately with a job_id that can be polled
    for status via GET /integrations/sync-jobs/{job_id}.
    """
    from worker.tasks import sync_integration_materials_task

    actor_id = request.uploaded_by if request.uploaded_by is not None else user_id

    # Resolve mapping if provided
    if request.mapping_id is not None:
        mapping = db.query(IntegrationCourseMapping).filter(
            IntegrationCourseMapping.id == request.mapping_id,
            IntegrationCourseMapping.provider == provider,
            IntegrationCourseMapping.is_active.is_(True),
        ).first()
        if not mapping:
            raise HTTPException(status_code=404, detail="Mapping not found.")
        request.source_course_external_id = mapping.external_course_id
        request.source_connection_id = mapping.source_connection_id
        request.target_course_id = mapping.target_course_id

    # Ensure target course exists
    p = _resolve_provider(provider, db=db, connection_id=request.source_connection_id, actor_user_id=actor_id)
    resolved_target_course_id, _, _ = _ensure_target_course(
        db=db,
        provider=provider,
        provider_obj=p,
        source_course_external_id=request.source_course_external_id,
        source_connection_id=request.source_connection_id,
        target_course_id=request.target_course_id,
        created_by=actor_id,
    )
    _validate_target(db, resolved_target_course_id, request.target_session_id)

    # Create job record in "queued" state
    job = IntegrationSyncJob(
        provider=provider,
        source_course_external_id=request.source_course_external_id,
        source_connection_id=request.source_connection_id,
        target_course_id=resolved_target_course_id,
        target_session_id=request.target_session_id,
        triggered_by=actor_id,
        status="queued",
        requested_count=0,  # Will be updated by worker
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # Queue Celery task
    task = sync_integration_materials_task.delay(
        job_id=job.id,
        provider=provider,
        source_course_external_id=request.source_course_external_id,
        source_connection_id=request.source_connection_id,
        target_course_id=resolved_target_course_id,
        target_session_id=request.target_session_id,
        actor_id=actor_id,
        overwrite_title_prefix=request.overwrite_title_prefix,
    )

    return AsyncSyncResponse(
        job_id=job.id,
        task_id=task.id,
        status="queued",
        message="Sync job queued for background processing. Poll /integrations/sync-jobs for status.",
    )


@router.post("/{provider}/sync-roster", response_model=SyncRosterResponse)
def sync_roster(
    provider: str,
    request: SyncRosterRequest,
    user_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    actor_id = request.created_by if request.created_by is not None else user_id
    p = _resolve_provider(provider, db=db, connection_id=request.source_connection_id, actor_user_id=actor_id)

    if request.mapping_id is not None:
        mapping = db.query(IntegrationCourseMapping).filter(
            IntegrationCourseMapping.id == request.mapping_id,
            IntegrationCourseMapping.provider == provider,
            IntegrationCourseMapping.is_active.is_(True),
        ).first()
        if not mapping:
            raise HTTPException(status_code=404, detail="Mapping not found.")
        request.source_course_external_id = mapping.external_course_id
        request.source_connection_id = mapping.source_connection_id
        request.target_course_id = mapping.target_course_id

    resolved_target_course_id, _, _ = _ensure_target_course(
        db=db,
        provider=provider,
        provider_obj=p,
        source_course_external_id=request.source_course_external_id,
        source_connection_id=request.source_connection_id,
        target_course_id=request.target_course_id,
        created_by=actor_id,
    )
    request.target_course_id = resolved_target_course_id
    _validate_target(db, resolved_target_course_id, None)

    external_enrollments = p.list_enrollments(request.source_course_external_id)
    scanned_count = len(external_enrollments)
    enrolled_count = 0
    created_users_count = 0
    skipped_count = 0
    missing_email_count = 0

    for record in external_enrollments:
        email = (record.email or "").strip().lower()
        if not email:
            missing_email_count += 1
            skipped_count += 1
            continue

        user = db.query(User).filter(
            User.email == email,
            User.auth_provider == AuthProvider.cognito,
        ).first()
        if user is None:
            user = User(
                name=(record.name or email.split("@")[0]).strip() or email,
                email=email,
                role=UserRole.student,
                auth_provider=AuthProvider.cognito,
            )
            db.add(user)
            db.flush()
            created_users_count += 1

        existing = db.query(Enrollment).filter(
            Enrollment.user_id == user.id,
            Enrollment.course_id == resolved_target_course_id,
        ).first()
        if existing:
            skipped_count += 1
            continue

        db.add(Enrollment(user_id=user.id, course_id=resolved_target_course_id))
        enrolled_count += 1

    db.commit()

    return SyncRosterResponse(
        provider=provider,
        source_connection_id=request.source_connection_id,
        source_course_external_id=request.source_course_external_id,
        target_course_id=resolved_target_course_id,
        scanned_count=scanned_count,
        enrolled_count=enrolled_count,
        created_users_count=created_users_count,
        skipped_count=skipped_count,
        missing_email_count=missing_email_count,
    )
