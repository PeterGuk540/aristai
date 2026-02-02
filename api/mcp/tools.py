"""
MCP Tool Registry for Voice Assistant.

Each tool is a plain function: (db: Session, **kwargs) -> dict
Tools are registered in TOOL_REGISTRY with metadata (args_schema, mode).
"""
import logging
from typing import Any, Dict

from sqlalchemy.orm import Session

from api.models.course import Course, generate_join_code
from api.models.session import Session as SessionModel, SessionStatus, Case
from api.models.poll import Poll
from api.models.report import Report
from api.schemas.voice import (
    ListCoursesArgs,
    ListSessionsArgs,
    GetSessionArgs,
    GetReportArgs,
    CreateCourseArgs,
    CreateSessionArgs,
    UpdateSessionStatusArgs,
    GenerateSessionPlanArgs,
    PostCaseArgs,
    CreatePollArgs,
)

logger = logging.getLogger(__name__)


# ---- READ TOOLS ----

def list_courses(db: Session, skip: int = 0, limit: int = 100) -> dict:
    """List all courses."""
    courses = db.query(Course).offset(skip).limit(limit).all()
    return {
        "courses": [
            {"id": c.id, "title": c.title, "created_at": str(c.created_at)}
            for c in courses
        ]
    }


def list_sessions(db: Session, course_id: int) -> dict:
    """List sessions for a course."""
    sessions = (
        db.query(SessionModel)
        .filter(SessionModel.course_id == course_id)
        .order_by(SessionModel.created_at.desc())
        .all()
    )
    return {
        "sessions": [
            {
                "id": s.id,
                "title": s.title,
                "status": s.status.value if hasattr(s.status, "value") else s.status,
                "created_at": str(s.created_at),
            }
            for s in sessions
        ]
    }


def get_session(db: Session, session_id: int) -> dict:
    """Get a single session with plan."""
    s = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not s:
        return {"error": "Session not found"}
    return {
        "id": s.id,
        "title": s.title,
        "status": s.status.value if hasattr(s.status, "value") else s.status,
        "plan_json": s.plan_json,
        "created_at": str(s.created_at),
    }


def get_report(db: Session, session_id: int) -> dict:
    """Get the latest report for a session."""
    report = (
        db.query(Report)
        .filter(Report.session_id == session_id)
        .order_by(Report.created_at.desc())
        .first()
    )
    if not report:
        return {"error": "Report not found"}
    return {
        "id": report.id,
        "session_id": report.session_id,
        "version": report.version,
        "report_md": report.report_md[:500] if report.report_md else None,
        "created_at": str(report.created_at),
    }


# ---- WRITE TOOLS ----

def create_course(
    db: Session,
    title: str,
    syllabus_text: str = None,
    objectives_json: list = None,
) -> dict:
    """Create a new course."""
    join_code = generate_join_code()
    while db.query(Course).filter(Course.join_code == join_code).first():
        join_code = generate_join_code()
    c = Course(
        title=title,
        syllabus_text=syllabus_text,
        objectives_json=objectives_json,
        join_code=join_code,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return {"id": c.id, "title": c.title, "join_code": c.join_code}


def create_session(db: Session, course_id: int, title: str) -> dict:
    """Create a new session in a course."""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        return {"error": "Course not found"}
    s = SessionModel(course_id=course_id, title=title)
    db.add(s)
    db.commit()
    db.refresh(s)
    return {"id": s.id, "title": s.title, "course_id": s.course_id}


def update_session_status(db: Session, session_id: int, status: str) -> dict:
    """Update session status (draft/scheduled/live/completed)."""
    s = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not s:
        return {"error": "Session not found"}
    s.status = SessionStatus(status)
    db.commit()
    db.refresh(s)
    return {"id": s.id, "status": s.status.value}


def generate_session_plan(db: Session, course_id: int) -> dict:
    """Trigger async session plan generation via Celery."""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        return {"error": "Course not found"}
    from worker.tasks import generate_plans_task
    task = generate_plans_task.delay(course_id)
    return {"task_id": task.id, "status": "queued", "course_id": course_id}


def post_case(db: Session, session_id: int, prompt: str) -> dict:
    """Post a case study to a session."""
    s = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not s:
        return {"error": "Session not found"}
    c = Case(session_id=session_id, prompt=prompt)
    db.add(c)
    db.commit()
    db.refresh(c)
    return {"id": c.id, "session_id": c.session_id, "prompt": c.prompt}


def create_poll(
    db: Session, session_id: int, question: str, options_json: list
) -> dict:
    """Create a poll in a session."""
    s = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not s:
        return {"error": "Session not found"}
    p = Poll(session_id=session_id, question=question, options_json=options_json)
    db.add(p)
    db.commit()
    db.refresh(p)
    return {"id": p.id, "question": p.question, "options": p.options_json}


# ---- TOOL REGISTRY ----

TOOL_REGISTRY: Dict[str, Dict[str, Any]] = {
    "list_courses": {
        "fn": list_courses,
        "args_schema": ListCoursesArgs,
        "mode": "read",
    },
    "list_sessions": {
        "fn": list_sessions,
        "args_schema": ListSessionsArgs,
        "mode": "read",
    },
    "get_session": {
        "fn": get_session,
        "args_schema": GetSessionArgs,
        "mode": "read",
    },
    "get_report": {
        "fn": get_report,
        "args_schema": GetReportArgs,
        "mode": "read",
    },
    "create_course": {
        "fn": create_course,
        "args_schema": CreateCourseArgs,
        "mode": "write",
    },
    "create_session": {
        "fn": create_session,
        "args_schema": CreateSessionArgs,
        "mode": "write",
    },
    "update_session_status": {
        "fn": update_session_status,
        "args_schema": UpdateSessionStatusArgs,
        "mode": "write",
    },
    "generate_session_plan": {
        "fn": generate_session_plan,
        "args_schema": GenerateSessionPlanArgs,
        "mode": "write",
    },
    "post_case": {
        "fn": post_case,
        "args_schema": PostCaseArgs,
        "mode": "write",
    },
    "create_poll": {
        "fn": create_poll,
        "args_schema": CreatePollArgs,
        "mode": "write",
    },
}


def get_tool_descriptions() -> str:
    """Generate tool descriptions for LLM prompt."""
    lines = []
    for name, entry in TOOL_REGISTRY.items():
        schema = entry["args_schema"]
        fields = []
        for field_name, field_info in schema.model_fields.items():
            annotation = field_info.annotation
            type_name = getattr(annotation, "__name__", str(annotation))
            fields.append(f"{field_name}: {type_name}")
        fields_str = ", ".join(fields)
        lines.append(f"- {name}({fields_str}) [mode={entry['mode']}]")
    return "\n".join(lines)
