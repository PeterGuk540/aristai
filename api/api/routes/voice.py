"""
Voice Assistant API routes.

Endpoints:
    POST /api/voice/transcribe  - audio -> transcript
    POST /api/voice/plan        - transcript -> action plan
    POST /api/voice/execute     - plan + confirmation -> results + summary
    GET  /api/voice/audit       - audit trail
"""
import hashlib
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from api.core.database import get_db
from api.core.config import get_settings
from api.models.voice_audit import VoiceAudit
from mcp_server.server import TOOL_REGISTRY
from api.schemas.voice import (
    TranscribeResponse,
    PlanRequest,
    PlanResponse,
    ExecuteRequest,
    ExecuteResponse,
    StepResult,
    VoiceAuditListResponse,
)
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from api.core.database import get_db
from api.core.config import get_settings
from api.models.voice_audit import VoiceAudit
from mcp_server.server import TOOL_REGISTRY
from api.schemas.voice import (
    TranscribeResponse,
    PlanRequest,
    PlanResponse,
    ExecuteRequest,
    ExecuteResponse,
    StepResult,
    VoiceAuditListResponse,
    )
from api.services import asr, tts


@router.post("/synthesize", response_model=None)
async def voice_synthesize(request: Request):
    """Standard TTS endpoint for frontend voice components."""
    try:
        data = await request.json()
        text = data.get("text", "")
        if not text:
            raise HTTPException(status_code=400, detail="Text is required")
        
        result = tts.synthesize(text)
        
        return Response(
            content=result.audio_bytes,
            media_type=result.content_type,
            headers={"Cache-Control": "no-cache"}
        )
    except Exception as e:
        logger.exception(f"TTS synthesis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/transcribe", response_model=TranscribeResponse, status_code=status.HTTP_200_OK)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/transcribe", response_model=TranscribeResponse, status_code=status.HTTP_200_OK)
async def transcribe_audio(
    file: UploadFile = File(...),
):
    """Transcribe uploaded audio to text via configured ASR provider."""
    settings = get_settings()
    max_mb = settings.voice_max_mb

    contents = await file.read()
    size_mb = len(contents) / (1024 * 1024)
    if size_mb > max_mb:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size {size_mb:.1f}MB exceeds {max_mb}MB limit",
        )

    try:
        result = asr.transcribe(contents, file.content_type or "audio/webm")
        return TranscribeResponse(
            transcript=result.transcript,
            language=result.language,
            duration_seconds=result.duration_seconds,
        )
    except Exception as e:
        logger.exception("ASR transcription failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Transcription failed: {str(e)}",
        )


@router.post("/plan", response_model=PlanResponse, status_code=status.HTTP_200_OK)
def create_plan(request: PlanRequest):
    """Convert transcript to action plan using LLM voice orchestrator."""
    from workflows.voice_orchestrator import run_voice_orchestrator

    if not request.transcript.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Transcript cannot be empty",
        )

    result = run_voice_orchestrator(request.transcript)

    if result.get("error") and not result.get("plan", {}).get("steps"):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result["error"],
        )

    return PlanResponse(
        plan=result["plan"],
        transcript=request.transcript,
    )


def _validate_tool_args(tool_name: str, args: dict, schema: dict) -> Optional[str]:
    required = schema.get("required", [])
    properties = schema.get("properties", {})

    for field in required:
        if field not in args:
            return f"Missing required field '{field}' for tool '{tool_name}'"

    for field, value in args.items():
        expected = properties.get(field, {}).get("type")
        if not expected:
            continue
        if expected == "integer" and not isinstance(value, int):
            return f"Field '{field}' must be integer"
        if expected == "string" and not isinstance(value, str):
            return f"Field '{field}' must be string"
        if expected == "array" and not isinstance(value, list):
            return f"Field '{field}' must be array"
        if expected == "boolean" and not isinstance(value, bool):
            return f"Field '{field}' must be boolean"
    return None


@router.post("/execute", response_model=ExecuteResponse, status_code=status.HTTP_200_OK)
def execute_plan(
    request: ExecuteRequest,
    user_id: int = Query(default=1, description="Instructor user ID"),
    db: Session = Depends(get_db),
):
    """
    Execute an action plan.

    Read tools run immediately. Write tools require confirmed=True,
    otherwise they are skipped with a reason.
    """
    plan = request.plan
    results: List[StepResult] = []

    for step in plan.steps:
        tool_entry = TOOL_REGISTRY.get(step.tool_name)
        if not tool_entry:
            results.append(StepResult(
                tool_name=step.tool_name,
                success=False,
                error=f"Unknown tool: {step.tool_name}",
            ))
            continue

        # Block writes without confirmation
        if step.mode == "write" and not request.confirmed:
            results.append(StepResult(
                tool_name=step.tool_name,
                success=False,
                skipped=True,
                skipped_reason="Write tool requires confirmation",
            ))
            continue

        # Validate args against schema
        error = _validate_tool_args(step.tool_name, step.args, tool_entry.get("parameters", {}))
        if error:
            results.append(StepResult(
                tool_name=step.tool_name,
                success=False,
                error=error,
            ))
            continue

        # Execute tool
        try:
            tool_result = tool_entry["handler"](db, **step.args)
            results.append(StepResult(
                tool_name=step.tool_name,
                success=True,
                result=tool_result,
            ))
        except Exception as e:
            db.rollback()
            logger.exception(f"Tool execution failed: {step.tool_name}")
            results.append(StepResult(
                tool_name=step.tool_name,
                success=False,
                error=str(e),
            ))

    # Generate TTS-friendly summary
    from workflows.voice_orchestrator import generate_summary
    summary = generate_summary([r.model_dump() for r in results])

    # Write audit log
    transcript_hash = hashlib.sha256(plan.intent.encode()).hexdigest()
    try:
        audit = VoiceAudit(
            user_id=user_id,
            transcript_hash=transcript_hash,
            plan_json=plan.model_dump(),
            tool_calls=[r.model_dump() for r in results],
        )
        db.add(audit)
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Failed to write voice audit log")

    return ExecuteResponse(results=results, summary=summary, audio_url=None)


@router.get("/audit", response_model=VoiceAuditListResponse, status_code=status.HTTP_200_OK)
def get_audit_trail(
    user_id: int = Query(default=1, description="Instructor user ID"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """Get voice assistant audit trail for an instructor."""
    query = db.query(VoiceAudit).filter(VoiceAudit.user_id == user_id)
    total = query.count()
    audits = (
        query.order_by(VoiceAudit.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return VoiceAuditListResponse(audits=audits, total=total)
