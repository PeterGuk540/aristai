from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.report import Report
from app.models.session import Session as SessionModel
from app.schemas.report import ReportResponse

router = APIRouter()


@router.post("/session/{session_id}/generate", status_code=status.HTTP_202_ACCEPTED)
def generate_report(session_id: int, db: Session = Depends(get_db)):
    """Trigger async job to generate a feedback report for a session."""
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    from worker.tasks import generate_report_task

    task = generate_report_task.delay(session_id)
    return {"task_id": task.id, "status": "queued"}


@router.get("/session/{session_id}", response_model=ReportResponse)
def get_session_report(session_id: int, version: str = "latest", db: Session = Depends(get_db)):
    """Get the feedback report for a session."""
    # Check session exists for consistency with generate_report
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    query = db.query(Report).filter(Report.session_id == session_id)

    if version == "latest":
        report = query.order_by(Report.created_at.desc()).first()
    else:
        report = query.filter(Report.version == version).first()

    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    return report
