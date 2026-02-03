"""
Session-related MCP tools.

Tools for listing, creating, and managing class sessions.
"""

import logging
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from api.models.session import Session as SessionModel, SessionStatus
from api.models.course import Course
from api.models.post import Post

logger = logging.getLogger(__name__)


def list_sessions(
    db: Session,
    course_id: int,
    status: Optional[str] = None,
) -> Dict[str, Any]:
    """
    List all sessions for a course.
    """
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        return {"error": f"Course {course_id} not found"}
    
    query = db.query(SessionModel).filter(SessionModel.course_id == course_id)
    
    if status:
        try:
            status_enum = SessionStatus(status)
            query = query.filter(SessionModel.status == status_enum)
        except ValueError:
            return {"error": f"Invalid status: {status}. Use: draft, scheduled, live, completed"}
    
    sessions = query.order_by(SessionModel.created_at.desc()).all()
    
    if not sessions:
        filter_msg = f" with status '{status}'" if status else ""
        return {
            "message": f"No sessions found for '{course.title}'{filter_msg}.",
            "sessions": [],
            "count": 0,
            "course_title": course.title,
        }
    
    session_list = []
    live_sessions = []
    
    for s in sessions:
        status_val = s.status.value if hasattr(s.status, 'value') else str(s.status)
        post_count = db.query(Post).filter(Post.session_id == s.id).count()
        
        session_list.append({
            "id": s.id,
            "title": s.title,
            "status": status_val,
            "post_count": post_count,
            "has_plan": bool(s.plan_json),
            "copilot_active": s.copilot_active == 1,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        })
        
        if status_val == "live":
            live_sessions.append(s.title)
    
    # Voice-friendly summary
    message = f"Found {len(sessions)} session{'s' if len(sessions) != 1 else ''} for '{course.title}'. "
    if live_sessions:
        message += f"Currently live: {', '.join(live_sessions)}. "
    
    return {
        "message": message,
        "sessions": session_list,
        "count": len(sessions),
        "course_title": course.title,
        "live_sessions": live_sessions,
    }


def get_session(db: Session, session_id: int) -> Dict[str, Any]:
    """
    Get detailed information about a session.
    """
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    
    if not session:
        return {"error": f"Session {session_id} not found"}
    
    course = db.query(Course).filter(Course.id == session.course_id).first()
    status_val = session.status.value if hasattr(session.status, 'value') else str(session.status)
    post_count = db.query(Post).filter(Post.session_id == session_id).count()
    
    # Voice-friendly summary
    message = f"Session: {session.title}. Status: {status_val}. "
    message += f"It has {post_count} posts. "
    if session.copilot_active == 1:
        message += "The AI copilot is currently active. "
    if session.plan_json:
        topics = session.plan_json.get("topics", [])
        if topics:
            message += f"Topics include: {', '.join(topics[:3])}."
    
    return {
        "message": message,
        "id": session.id,
        "title": session.title,
        "status": status_val,
        "course_id": session.course_id,
        "course_title": course.title if course else None,
        "post_count": post_count,
        "copilot_active": session.copilot_active == 1,
        "has_plan": bool(session.plan_json),
        "created_at": session.created_at.isoformat() if session.created_at else None,
    }


def get_session_plan(db: Session, session_id: int) -> Dict[str, Any]:
    """
    Get the AI-generated session plan with topics, goals, and discussion prompts.
    """
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    
    if not session:
        return {"error": f"Session {session_id} not found"}
    
    if not session.plan_json:
        return {
            "message": f"Session '{session.title}' doesn't have a generated plan yet.",
            "session_id": session_id,
            "session_title": session.title,
            "has_plan": False,
        }
    
    plan = session.plan_json
    
    # Extract key elements
    topics = plan.get("topics", [])
    goals = plan.get("learning_goals", plan.get("goals", []))
    discussion_prompts = plan.get("discussion_prompts", [])
    case = plan.get("case_prompt", plan.get("case", ""))
    key_takeaways = plan.get("key_takeaways", [])
    
    # Voice-friendly summary
    message = f"Plan for '{session.title}': "
    if topics:
        message += f"Topics are {', '.join(topics[:3])}. "
    if goals and isinstance(goals, list):
        message += f"Main goal: {goals[0]}. " if goals else ""
    if case:
        case_preview = case[:200] if isinstance(case, str) else str(case)[:200]
        message += f"Case study: {case_preview}"
    
    return {
        "message": message,
        "session_id": session_id,
        "session_title": session.title,
        "has_plan": True,
        "topics": topics,
        "goals": goals,
        "discussion_prompts": discussion_prompts,
        "case_prompt": case,
        "key_takeaways": key_takeaways,
        "full_plan": plan,
    }


def create_session(db: Session, course_id: int, title: str) -> Dict[str, Any]:
    """
    Create a new session in a course.
    """
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        return {"error": f"Course {course_id} not found"}
    
    try:
        session = SessionModel(
            course_id=course_id,
            title=title,
            status=SessionStatus.draft,
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        
        message = f"Created session '{title}' in course '{course.title}'. "
        message += f"Session ID is {session.id}. Status is draft."
        
        return {
            "message": message,
            "id": session.id,
            "title": session.title,
            "course_id": course_id,
            "course_title": course.title,
            "status": "draft",
            "success": True,
        }
        
    except Exception as e:
        db.rollback()
        logger.exception(f"Failed to create session: {e}")
        return {"error": f"Failed to create session: {str(e)}"}


def update_session_status(db: Session, session_id: int, status: str) -> Dict[str, Any]:
    """
    Update session status.
    """
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    
    if not session:
        return {"error": f"Session {session_id} not found"}
    
    try:
        new_status = SessionStatus(status)
        old_status = session.status.value if hasattr(session.status, 'value') else str(session.status)
        session.status = new_status
        db.commit()
        db.refresh(session)
        
        message = f"Updated session '{session.title}' from {old_status} to {status}."
        
        return {
            "message": message,
            "id": session.id,
            "title": session.title,
            "old_status": old_status,
            "new_status": status,
            "success": True,
        }
        
    except ValueError:
        return {"error": f"Invalid status: {status}. Use: draft, scheduled, live, completed"}
    except Exception as e:
        db.rollback()
        logger.exception(f"Failed to update session status: {e}")
        return {"error": f"Failed to update status: {str(e)}"}


def go_live(db: Session, session_id: int) -> Dict[str, Any]:
    """
    Shortcut to set a session to 'live' status.
    """
    return update_session_status(db, session_id, "live")


def end_session(db: Session, session_id: int) -> Dict[str, Any]:
    """
    Shortcut to set a session to 'completed' status.
    """
    return update_session_status(db, session_id, "completed")
