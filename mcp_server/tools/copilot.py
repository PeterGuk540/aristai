"""
Copilot-related MCP tools.

Tools for controlling the AI instructor copilot.
"""

import logging
from typing import Any, Dict

from sqlalchemy.orm import Session

from api.models.session import Session as SessionModel
from api.models.intervention import Intervention

logger = logging.getLogger(__name__)


def get_copilot_status(db: Session, session_id: int) -> Dict[str, Any]:
    """
    Check if the AI copilot is running for a session.
    """
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        return {"error": f"Session {session_id} not found"}
    
    is_active = session.copilot_active == 1
    
    # Count interventions
    intervention_count = db.query(Intervention).filter(Intervention.session_id == session_id).count()
    
    if is_active:
        message = f"The AI copilot is active for session '{session.title}'. "
        message += f"It has generated {intervention_count} suggestions so far."
    else:
        message = f"The AI copilot is not running for session '{session.title}'."
        if intervention_count > 0:
            message += f" There are {intervention_count} previous suggestions available."
    
    return {
        "message": message,
        "session_id": session_id,
        "session_title": session.title,
        "copilot_active": is_active,
        "task_id": session.copilot_task_id,
        "intervention_count": intervention_count,
    }


def get_copilot_suggestions(
    db: Session,
    session_id: int,
    count: int = 3,
) -> Dict[str, Any]:
    """
    Get the latest AI copilot suggestions.
    """
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        return {"error": f"Session {session_id} not found"}
    
    interventions = (
        db.query(Intervention)
        .filter(Intervention.session_id == session_id)
        .order_by(Intervention.created_at.desc())
        .limit(count)
        .all()
    )
    
    if not interventions:
        return {
            "message": "No copilot suggestions yet. Start the copilot to generate suggestions.",
            "suggestions": [],
            "count": 0,
        }
    
    suggestion_list = []
    for i in interventions:
        suggestion = i.suggestion_json or {}
        
        # Extract key elements
        summary = suggestion.get("rolling_summary", "")
        confusion_points = suggestion.get("confusion_points", [])
        prompts = suggestion.get("instructor_prompts", [])
        activity = suggestion.get("reengagement_activity")
        poll_suggestion = suggestion.get("poll_suggestion")
        assessment = suggestion.get("overall_assessment", {})
        
        suggestion_list.append({
            "id": i.id,
            "type": i.intervention_type,
            "summary": summary,
            "confusion_points": confusion_points,
            "instructor_prompts": prompts,
            "reengagement_activity": activity,
            "poll_suggestion": poll_suggestion,
            "engagement_level": assessment.get("engagement_level"),
            "understanding_level": assessment.get("understanding_level"),
            "recommendation": assessment.get("recommendation"),
            "created_at": i.created_at.isoformat() if i.created_at else None,
        })
    
    # Voice-friendly summary of latest suggestion
    latest = suggestion_list[0]
    message = ""
    
    if latest.get("summary"):
        message += f"Summary: {latest['summary'][:200]} "
    
    if latest.get("confusion_points"):
        cp_count = len(latest["confusion_points"])
        message += f"Found {cp_count} confusion point{'s' if cp_count != 1 else ''}. "
        # Read the first confusion point
        if cp_count > 0:
            first_cp = latest["confusion_points"][0]
            message += f"Top issue: {first_cp.get('issue', 'Unknown')}. "
    
    if latest.get("instructor_prompts"):
        prompt_count = len(latest["instructor_prompts"])
        message += f"Suggested {prompt_count} prompt{'s' if prompt_count != 1 else ''}. "
        # Read the first prompt
        if prompt_count > 0:
            first_prompt = latest["instructor_prompts"][0]
            message += f"Try asking: {first_prompt.get('prompt', '')[:100]}"
    
    if latest.get("recommendation"):
        message += f" Recommendation: {latest['recommendation']}"
    
    if not message:
        message = f"Latest suggestion from {latest.get('created_at', 'recently')}."
    
    return {
        "message": message,
        "suggestions": suggestion_list,
        "count": len(interventions),
        "latest": suggestion_list[0] if suggestion_list else None,
    }


def start_copilot(db: Session, session_id: int) -> Dict[str, Any]:
    """
    Start the AI copilot for a session.
    """
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        return {"error": f"Session {session_id} not found"}
    
    if session.copilot_active == 1:
        return {
            "message": f"The copilot is already running for session '{session.title}'.",
            "session_id": session_id,
            "task_id": session.copilot_task_id,
            "already_active": True,
        }
    
    try:
        from worker.tasks import start_live_copilot_task
        task = start_live_copilot_task.delay(session_id)
        
        # Store task ID
        session.copilot_task_id = task.id
        db.commit()
        
        message = f"Started the AI copilot for session '{session.title}'. "
        message += "It will analyze the discussion every 90 seconds and provide suggestions."
        
        return {
            "message": message,
            "session_id": session_id,
            "task_id": task.id,
            "status": "started",
            "success": True,
        }
        
    except Exception as e:
        db.rollback()
        logger.exception(f"Failed to start copilot: {e}")
        return {"error": f"Failed to start copilot: {str(e)}"}


def stop_copilot(db: Session, session_id: int) -> Dict[str, Any]:
    """
    Stop the AI copilot for a session.
    """
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        return {"error": f"Session {session_id} not found"}
    
    if session.copilot_active == 0:
        return {
            "message": f"The copilot is not running for session '{session.title}'.",
            "session_id": session_id,
            "already_stopped": True,
        }
    
    try:
        from workflows.copilot import stop_copilot as workflow_stop_copilot
        result = workflow_stop_copilot(session_id)
        
        message = f"Requested copilot stop for session '{session.title}'. "
        message += "It will stop after the current analysis completes."
        
        return {
            "message": message,
            "session_id": session_id,
            "status": "stop_requested",
            "success": True,
        }
        
    except Exception as e:
        logger.exception(f"Failed to stop copilot: {e}")
        return {"error": f"Failed to stop copilot: {str(e)}"}
