from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from typing import List
from api.core.database import get_db
from api.models.session import Session as SessionModel, Case
from api.models.intervention import Intervention
from api.schemas.session import (
    SessionCreate,
    SessionResponse,
    SessionStatusUpdate,
    CaseCreate,
    CaseResponse,
)
from api.schemas.intervention import InterventionResponse
from api.models.session import SessionStatus

router = APIRouter()


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
