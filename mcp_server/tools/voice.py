"""
Voice-first macro MCP tools.

Multi-step tools for common voice commands.
"""

from __future__ import annotations

import csv
import io
import logging
from typing import Any, Dict, Iterable, List, Optional

import httpx
from sqlalchemy.orm import Session

from api.models.user import User
from api.services.action_preview import build_action_preview
from api.services.action_store import ActionStore
from mcp_server.tools import navigation, resolve

logger = logging.getLogger(__name__)


def _collect_emails(*sources: Optional[Iterable[str]]) -> List[str]:
    emails: List[str] = []
    for source in sources:
        if not source:
            continue
        if isinstance(source, str):
            emails.extend([e.strip() for e in source.split(",") if e.strip()])
        else:
            emails.extend([e.strip() for e in source if e and str(e).strip()])
    return [email.lower() for email in emails if "@" in email]


def _parse_csv_emails(text: str) -> List[str]:
    emails: List[str] = []
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames:
        fieldnames = {f.lower(): f for f in reader.fieldnames}
        email_key = fieldnames.get("email")
        if email_key:
            for row in reader:
                value = row.get(email_key, "").strip()
                if value:
                    emails.append(value)
            return _collect_emails(emails)
    # Fallback: one email per line
    return _collect_emails(text.splitlines())


def _resolve_course_id(db: Session, course_query: Optional[str]) -> Optional[int]:
    if not course_query:
        return None
    candidates = resolve.resolve_course(db, course_query).get("candidates", [])
    return candidates[0]["course_id"] if candidates else None


def _resolve_session_id(db: Session, course_id: int, session_query: str) -> Optional[int]:
    candidates = resolve.resolve_session(db, course_id, session_query).get("candidates", [])
    return candidates[0]["session_id"] if candidates else None


def voice_open_page(
    db: Session,
    target: str,
    course_query: Optional[str] = None,
    session_query: str = "latest",
    auto_open: bool = True,
    **kwargs: Any,
) -> Dict[str, Any]:
    if target in {"course", "courses"} and course_query:
        course_id = _resolve_course_id(db, course_query)
        if course_id:
            path = f"/courses/{course_id}"
            return {
                "success": True,
                "message": f"Opening course {course_query}.",
                "path": path,
                "ui_actions": [{"type": "ui.navigate", "payload": {"path": path}}],
            }
    if target in {"session", "sessions"} and course_query:
        course_id = _resolve_course_id(db, course_query)
        if course_id:
            session_id = _resolve_session_id(db, course_id, session_query)
            if session_id:
                path = f"/sessions/{session_id}"
                return {
                    "success": True,
                    "message": f"Opening session {session_query}.",
                    "path": path,
                    "ui_actions": [{"type": "ui.navigate", "payload": {"path": path}}],
                }
    if auto_open:
        return navigation.navigate_to_page(db, page=target)
    return {"success": False, "error": "Unable to resolve target for navigation."}


def voice_create_poll(
    db: Session,
    course_query: Optional[str] = None,
    session_query: str = "latest",
    question: Optional[str] = None,
    options: Optional[List[str]] = None,
    auto_open: bool = True,
    user_id: Optional[int] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    if not question or not options:
        return {
            "success": False,
            "error": "Poll question and options are required.",
            "missing_fields": [
                field for field, value in {"question": question, "options": options}.items() if not value
            ],
        }

    course_id = _resolve_course_id(db, course_query) if course_query else None
    if not course_id:
        return {"success": False, "error": "Unable to resolve course for poll."}

    session_id = _resolve_session_id(db, course_id, session_query)
    if not session_id:
        return {"success": False, "error": "Unable to resolve session for poll."}

    args = {"session_id": session_id, "question": question, "options_json": options}
    preview = build_action_preview("create_poll", args, db=db)
    action = ActionStore().create_action(user_id=user_id, tool_name="create_poll", args=args, preview=preview)
    response = {
        "success": True,
        "action_id": action.action_id,
        "requires_confirmation": True,
        "preview": preview,
        "message": "Poll is ready to create. Confirm to proceed.",
    }
    if auto_open:
        response["ui_actions"] = [{"type": "ui.navigate", "payload": {"path": f"/sessions/{session_id}"}}]
    return response


def voice_generate_report(
    db: Session,
    course_query: Optional[str] = None,
    session_query: str = "latest",
    auto_open: bool = True,
    user_id: Optional[int] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    course_id = _resolve_course_id(db, course_query) if course_query else None
    if not course_id:
        return {"success": False, "error": "Unable to resolve course for report."}
    session_id = _resolve_session_id(db, course_id, session_query)
    if not session_id:
        return {"success": False, "error": "Unable to resolve session for report."}

    args = {"session_id": session_id}
    preview = build_action_preview("generate_report", args, db=db)
    action = ActionStore().create_action(user_id=user_id, tool_name="generate_report", args=args, preview=preview)
    response = {
        "success": True,
        "action_id": action.action_id,
        "requires_confirmation": True,
        "preview": preview,
        "message": "Report generation is ready. Confirm to proceed.",
    }
    if auto_open:
        response["ui_actions"] = [{"type": "ui.navigate", "payload": {"path": "/reports"}}]
    return response


def voice_enroll_students(
    db: Session,
    course_query: Optional[str] = None,
    emails: Optional[List[str]] = None,
    csv_text: Optional[str] = None,
    csv_url: Optional[str] = None,
    role: str = "student",
    auto_open: bool = True,
    user_id: Optional[int] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    if role != "student":
        return {"success": False, "error": "Only student enrollment is supported."}

    course_id = _resolve_course_id(db, course_query) if course_query else None
    if not course_id:
        return {"success": False, "error": "Unable to resolve course for enrollment."}

    csv_emails: List[str] = []
    if csv_text:
        csv_emails = _parse_csv_emails(csv_text)
    if csv_url:
        try:
            response = httpx.get(csv_url, timeout=10.0)
            response.raise_for_status()
            csv_emails.extend(_parse_csv_emails(response.text))
        except Exception as exc:
            logger.exception("Failed to fetch CSV URL: %s", exc)
            return {"success": False, "error": "Unable to fetch CSV URL."}

    all_emails = _collect_emails(emails, csv_emails)
    if not all_emails:
        return {"success": False, "error": "No student emails provided."}

    users = db.query(User).filter(User.email.in_(all_emails)).all()
    user_ids = [user.id for user in users]
    unresolved = [email for email in all_emails if email not in {u.email for u in users}]

    if not user_ids:
        return {"success": False, "error": "No matching users found for enrollment.", "unresolved": unresolved}

    args = {"course_id": course_id, "user_ids": user_ids}
    preview = build_action_preview("bulk_enroll_students", args, db=db)
    action = ActionStore().create_action(user_id=user_id, tool_name="bulk_enroll_students", args=args, preview=preview)
    response = {
        "success": True,
        "action_id": action.action_id,
        "requires_confirmation": True,
        "preview": preview,
        "message": "Enrollment is ready. Confirm to proceed.",
        "unresolved": unresolved,
    }
    if auto_open:
        response["ui_actions"] = [{"type": "ui.navigate", "payload": {"path": f"/courses/{course_id}/enrollment"}}]
    return response
