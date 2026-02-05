"""
Context and resolve MCP tools.

Tools for resolving user-provided text into IDs and managing active context.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from difflib import SequenceMatcher
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy.orm import Session

from api.models.course import Course
from api.models.session import Session as SessionModel, SessionStatus
from api.models.user import User
from api.services.context_store import ContextStore


@dataclass
class RankedCandidate:
    id: int
    label: str
    confidence: float


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def rank_candidates(items: Iterable[tuple[int, str]], query: str, limit: int = 5) -> List[RankedCandidate]:
    scored = [
        RankedCandidate(item_id, label, _similarity(query, label))
        for item_id, label in items
    ]
    scored.sort(key=lambda item: item.confidence, reverse=True)
    return scored[:limit]


def resolve_course(db: Session, query: str, limit: int = 5) -> Dict[str, Any]:
    courses = (
        db.query(Course)
        .filter(Course.title.ilike(f"%{query}%"))
        .order_by(Course.created_at.desc())
        .limit(limit)
        .all()
    )
    items = [(course.id, course.title) for course in courses]
    ranked = rank_candidates(items, query, limit=limit)
    return {
        "success": True,
        "candidates": [
            {"course_id": item.id, "title": item.label, "confidence": item.confidence}
            for item in ranked
        ],
    }


def resolve_session(
    db: Session,
    course_id: int,
    query: str = "latest",
    limit: int = 5,
) -> Dict[str, Any]:
    if query in {"latest", "recent"}:
        sessions = (
            db.query(SessionModel)
            .filter(SessionModel.course_id == course_id)
            .order_by(SessionModel.created_at.desc())
            .limit(limit)
            .all()
        )
    elif query == "live":
        sessions = (
            db.query(SessionModel)
            .filter(SessionModel.course_id == course_id, SessionModel.status == SessionStatus.live)
            .order_by(SessionModel.created_at.desc())
            .limit(limit)
            .all()
        )
    elif query == "today":
        today = date.today()
        sessions = (
            db.query(SessionModel)
            .filter(SessionModel.course_id == course_id)
            .order_by(SessionModel.created_at.desc())
            .all()
        )
        sessions = [s for s in sessions if s.created_at.date() == today][:limit]
    else:
        sessions = (
            db.query(SessionModel)
            .filter(SessionModel.course_id == course_id, SessionModel.title.ilike(f"%{query}%"))
            .order_by(SessionModel.created_at.desc())
            .limit(limit)
            .all()
        )
    items = [(session.id, session.title or f"Session {session.id}") for session in sessions]
    ranked = rank_candidates(items, query, limit=limit)
    return {
        "success": True,
        "candidates": [
            {"session_id": item.id, "title": item.label, "confidence": item.confidence}
            for item in ranked
        ],
    }


def resolve_user(db: Session, email_or_name: str, limit: int = 5) -> Dict[str, Any]:
    users = (
        db.query(User)
        .filter(
            (User.email.ilike(f"%{email_or_name}%"))
            | (User.name.ilike(f"%{email_or_name}%"))
        )
        .order_by(User.created_at.desc())
        .limit(limit)
        .all()
    )
    items = [(user.id, user.email or user.name or f"user-{user.id}") for user in users]
    ranked = rank_candidates(items, email_or_name, limit=limit)
    return {
        "success": True,
        "candidates": [
            {"user_id": item.id, "label": item.label, "confidence": item.confidence}
            for item in ranked
        ],
    }


def get_current_context(
    db: Optional[Session] = None,
    user_id: Optional[int] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    store = ContextStore()
    context = store.get_context(user_id)
    return {"success": True, "context": context}


def set_active_course(
    db: Optional[Session] = None,
    course_id: int = 0,
    user_id: Optional[int] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    store = ContextStore()
    context = store.update_context(user_id, active_course_id=course_id)
    return {"success": True, "context": context}


def set_active_session(
    db: Optional[Session] = None,
    session_id: int = 0,
    user_id: Optional[int] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    store = ContextStore()
    context = store.update_context(user_id, active_session_id=session_id)
    return {"success": True, "context": context}
