from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from typing import List, Optional
from pydantic import BaseModel
from api.core.database import get_db
from api.models.session import Session as SessionModel, Case
from api.models.intervention import Intervention
from api.models.integration import IntegrationCanvasPush, IntegrationProviderConnection, IntegrationCourseMapping
from api.schemas.session import (
    SessionCreate,
    SessionResponse,
    SessionStatusUpdate,
    SessionUpdate,
    CaseCreate,
    CaseResponse,
)
from api.models.course import Course
from api.models.user import User
from api.schemas.intervention import InterventionResponse
from api.models.session import SessionStatus

router = APIRouter()


# ============ Canvas Push Schemas ============

class CanvasPushRequest(BaseModel):
    """Request to push session summary to Canvas."""
    connection_id: int
    external_course_id: str
    push_type: str = "announcement"  # announcement or assignment
    custom_title: Optional[str] = None


class CanvasPushResponse(BaseModel):
    """Response for canvas push request."""
    push_id: int
    task_id: str
    status: str
    message: str


class CanvasPushHistoryItem(BaseModel):
    """Single canvas push history item."""
    id: int
    push_type: str
    title: str
    status: str
    external_id: Optional[str]
    external_course_id: str
    error_message: Optional[str]
    model_name: Optional[str]
    total_tokens: Optional[int]
    estimated_cost_usd: Optional[str]
    execution_time_seconds: Optional[str]
    created_at: str
    completed_at: Optional[str]

    class Config:
        from_attributes = True


@router.get("/{session_id}/cases", response_model=List[CaseResponse])
def get_session_cases(session_id: int, db: Session = Depends(get_db)):
    """Get all cases for a session."""
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return session.cases


@router.post("/", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
def create_session(session: SessionCreate, db: Session = Depends(get_db)):
    """Create a new session."""
    try:
        db_session = SessionModel(**session.model_dump())
        db.add(db_session)
        db.commit()
        db.refresh(db_session)
        return db_session
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.get("/{session_id}", response_model=SessionResponse)
def get_session(session_id: int, db: Session = Depends(get_db)):
    """Get a session by ID."""
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.put("/{session_id}", response_model=SessionResponse)
def update_session(
    session_id: int,
    session_update: SessionUpdate,
    user_id: int,
    db: Session = Depends(get_db),
):
    """
    Update a session.
    - Admin: Can update any session
    - Instructor: Can only update sessions in courses they created
    """
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Get the parent course to check ownership
    course = db.query(Course).filter(Course.id == session.course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Parent course not found")

    # Check permissions
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not user.is_admin and course.created_by != user_id:
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to edit this session"
        )

    try:
        # Update only provided fields
        update_data = session_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if field == "status" and value is not None:
                # Convert status string to enum
                session.status = SessionStatus(value)
            else:
                setattr(session, field, value)

        db.commit()
        db.refresh(session)
        return session
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid value: {str(e)}")
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(
    session_id: int,
    user_id: int,
    db: Session = Depends(get_db),
):
    """
    Delete a session.
    - Admin: Can delete any session
    - Instructor: Can only delete sessions in courses they created
    """
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Get the parent course to check ownership
    course = db.query(Course).filter(Course.id == session.course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Parent course not found")

    # Check permissions
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not user.is_admin and course.created_by != user_id:
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to delete this session"
        )

    try:
        db.delete(session)
        db.commit()
        return None
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.patch("/{session_id}/status", response_model=SessionResponse)
def update_session_status(
    session_id: int,
    status_update: SessionStatusUpdate,
    db: Session = Depends(get_db),
):
    """
    Update session status.

    Valid transitions:
    - draft -> scheduled (session is ready but not yet live)
    - draft -> live (start session immediately)
    - scheduled -> live (go live)
    - live -> completed (end session)
    - Any status -> draft (reset to draft for editing)
    """
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    try:
        new_status = SessionStatus(status_update.status)
        session.status = new_status
        db.commit()
        db.refresh(session)
        return session
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status: {status_update.status}. Must be one of: draft, scheduled, live, completed",
        )
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.post(
    "/{session_id}/case",
    response_model=CaseResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_case(session_id: int, case: CaseCreate, db: Session = Depends(get_db)):
    """Post a case/problem for discussion."""
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    try:
        db_case = Case(session_id=session_id, **case.model_dump())
        db.add(db_case)
        db.commit()
        db.refresh(db_case)
        return db_case
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.post("/{session_id}/start_live_copilot", status_code=status.HTTP_202_ACCEPTED)
def start_live_copilot(session_id: int, db: Session = Depends(get_db)):
    """Start the live instructor copilot for a session."""
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Check if copilot is already running
    if session.copilot_active == 1:
        return {
            "status": "copilot_already_running",
            "session_id": session_id,
            "task_id": session.copilot_task_id,
        }

    from worker.tasks import start_live_copilot_task

    task = start_live_copilot_task.delay(session_id)

    # Store the task ID in the session
    session.copilot_task_id = task.id
    db.commit()

    return {"task_id": task.id, "status": "copilot_started"}


@router.post("/{session_id}/stop_live_copilot")
def stop_live_copilot(session_id: int, db: Session = Depends(get_db)):
    """Stop the live instructor copilot for a session."""
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    from workflows.copilot import stop_copilot

    result = stop_copilot(session_id)
    return result


@router.get("/{session_id}/copilot_status")
def get_copilot_status(session_id: int, db: Session = Depends(get_db)):
    """Check if the copilot is currently running for a session."""
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "session_id": session_id,
        "copilot_active": session.copilot_active == 1,
        "task_id": session.copilot_task_id,
    }


@router.get("/{session_id}/interventions", response_model=List[InterventionResponse])
def get_interventions(session_id: int, db: Session = Depends(get_db)):
    """Get all interventions for a session."""
    interventions = (
        db.query(Intervention)
        .filter(Intervention.session_id == session_id)
        .order_by(Intervention.created_at.desc())
        .all()
    )
    return interventions


# ============ Canvas Push Endpoints ============

@router.post("/{session_id}/push-to-canvas", response_model=CanvasPushResponse, status_code=status.HTTP_202_ACCEPTED)
def push_session_to_canvas(
    session_id: int,
    request: CanvasPushRequest,
    db: Session = Depends(get_db),
):
    """
    Push session summary to Canvas as an announcement or assignment.

    This endpoint:
    1. Creates a push record
    2. Starts a background task to generate summary and push to Canvas
    3. Returns immediately with task ID for polling

    Args:
        session_id: ID of the session to push
        request: Push configuration (connection_id, external_course_id, push_type)
    """
    # Verify session exists
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Verify connection exists and is Canvas
    connection = db.query(IntegrationProviderConnection).filter(
        IntegrationProviderConnection.id == request.connection_id
    ).first()

    if not connection:
        raise HTTPException(status_code=404, detail="Canvas connection not found")

    if connection.provider != "canvas":
        raise HTTPException(status_code=400, detail="Connection is not a Canvas connection")

    # Validate push_type
    if request.push_type not in ("announcement", "assignment"):
        raise HTTPException(status_code=400, detail="push_type must be 'announcement' or 'assignment'")

    # Create push record
    push = IntegrationCanvasPush(
        session_id=session_id,
        connection_id=request.connection_id,
        external_course_id=request.external_course_id,
        push_type=request.push_type,
        title=request.custom_title or f"Session Summary: {session.title}",
        status="queued",
    )
    db.add(push)
    db.commit()
    db.refresh(push)

    # Start background task
    from worker.tasks import push_to_canvas_task

    task = push_to_canvas_task.delay(
        push_id=push.id,
        session_id=session_id,
        connection_id=request.connection_id,
        external_course_id=request.external_course_id,
        push_type=request.push_type,
        custom_title=request.custom_title,
    )

    # Update push record with task ID
    push.celery_task_id = task.id
    db.commit()

    return CanvasPushResponse(
        push_id=push.id,
        task_id=task.id,
        status="queued",
        message=f"Canvas {request.push_type} push queued for background processing",
    )


@router.get("/{session_id}/canvas-pushes", response_model=List[CanvasPushHistoryItem])
def get_canvas_push_history(session_id: int, db: Session = Depends(get_db)):
    """Get history of Canvas pushes for a session."""
    # Verify session exists
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    pushes = (
        db.query(IntegrationCanvasPush)
        .filter(IntegrationCanvasPush.session_id == session_id)
        .order_by(IntegrationCanvasPush.created_at.desc())
        .all()
    )

    return [
        CanvasPushHistoryItem(
            id=p.id,
            push_type=p.push_type,
            title=p.title,
            status=p.status,
            external_id=p.external_id,
            external_course_id=p.external_course_id,
            error_message=p.error_message,
            model_name=p.model_name,
            total_tokens=p.total_tokens,
            estimated_cost_usd=p.estimated_cost_usd,
            execution_time_seconds=p.execution_time_seconds,
            created_at=p.created_at.isoformat() if p.created_at else "",
            completed_at=p.completed_at.isoformat() if p.completed_at else None,
        )
        for p in pushes
    ]


@router.get("/canvas-pushes/{push_id}")
def get_canvas_push_status(push_id: int, db: Session = Depends(get_db)):
    """Get status of a specific Canvas push."""
    push = db.query(IntegrationCanvasPush).filter(IntegrationCanvasPush.id == push_id).first()
    if not push:
        raise HTTPException(status_code=404, detail="Push not found")

    return {
        "id": push.id,
        "session_id": push.session_id,
        "push_type": push.push_type,
        "title": push.title,
        "status": push.status,
        "external_id": push.external_id,
        "external_course_id": push.external_course_id,
        "content_summary": push.content_summary,
        "error_message": push.error_message,
        "model_name": push.model_name,
        "total_tokens": push.total_tokens,
        "estimated_cost_usd": push.estimated_cost_usd,
        "execution_time_seconds": push.execution_time_seconds,
        "created_at": push.created_at.isoformat() if push.created_at else None,
        "started_at": push.started_at.isoformat() if push.started_at else None,
        "completed_at": push.completed_at.isoformat() if push.completed_at else None,
    }


@router.get("/{session_id}/canvas-mappings")
def get_canvas_mappings_for_session(session_id: int, db: Session = Depends(get_db)):
    """
    Get available Canvas course mappings for this session's course.

    Returns list of Canvas connections and their mapped courses.
    """
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Get all Canvas connections
    connections = (
        db.query(IntegrationProviderConnection)
        .filter(
            IntegrationProviderConnection.provider == "canvas",
            IntegrationProviderConnection.is_active == True,
        )
        .all()
    )

    result = []
    for conn in connections:
        # Find mappings for this course using this connection
        mapping = (
            db.query(IntegrationCourseMapping)
            .filter(
                IntegrationCourseMapping.target_course_id == session.course_id,
                IntegrationCourseMapping.provider == "canvas",
                IntegrationCourseMapping.source_connection_id == conn.id,
                IntegrationCourseMapping.is_active == True,
            )
            .first()
        )

        result.append({
            "connection_id": conn.id,
            "connection_label": conn.label,
            "api_base_url": conn.api_base_url,
            "has_mapping": mapping is not None,
            "external_course_id": mapping.external_course_id if mapping else None,
            "external_course_name": mapping.external_course_name if mapping else None,
        })

    return result
