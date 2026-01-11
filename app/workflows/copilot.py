"""
Live Copilot Workflow: Real-time Instructor Suggestions

This workflow analyzes ongoing discussion and generates instructor interventions.
Uses LangGraph for orchestration.
"""
import logging
import time
from typing import Any, Dict
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.session import Session as SessionModel
from app.models.post import Post
from app.models.intervention import Intervention

logger = logging.getLogger(__name__)

# Configuration for continuous copilot
COPILOT_INTERVAL_SECONDS = 90  # Run analysis every 90 seconds
COPILOT_MAX_DURATION_SECONDS = 3600  # Max 1 hour runtime
MIN_POSTS_FOR_ANALYSIS = 1  # Minimum posts needed to generate interventions


def run_copilot_single_iteration(session_id: int, db: Session) -> Dict[str, Any]:
    """
    Run a single iteration of copilot analysis.

    Workflow steps:
    1. Rolling summarization of last N posts
    2. Detect confusion, misconceptions, off-topic drift, stalled debate
    3. Generate 1-3 next-step instructor prompts
    4. Suggest 1 quick re-engagement activity (poll, quick write, compare answers)
    5. Log suggestions + rationale + evidence references (quote post ids)

    Returns:
        Dict with generated interventions
    """
    # Get recent posts
    posts = (
        db.query(Post)
        .filter(Post.session_id == session_id)
        .order_by(Post.created_at.desc())
        .limit(20)
        .all()
    )

    if len(posts) < MIN_POSTS_FOR_ANALYSIS:
        return {"session_id": session_id, "interventions": [], "message": "Not enough posts to analyze"}

    # TODO: Implement LangGraph workflow with LLM analysis
    # For now, return a placeholder intervention
    intervention_data = {
        "type": "prompt",
        "suggestion": "Consider asking students to elaborate on their reasoning.",
        "rationale": "Discussion has been active but lacks depth.",
        "evidence_post_ids": [p.id for p in posts[:3]],
    }

    # Save intervention to DB
    db_intervention = Intervention(
        session_id=session_id,
        intervention_type=intervention_data["type"],
        suggestion_json=intervention_data,
        model_name="placeholder",
        prompt_version="v0.1",
        evidence_post_ids=intervention_data["evidence_post_ids"],
    )
    db.add(db_intervention)
    db.commit()

    return {
        "session_id": session_id,
        "interventions": [intervention_data],
        "posts_analyzed": len(posts),
    }


def run_copilot_workflow(session_id: int) -> Dict[str, Any]:
    """
    Run continuous copilot analysis for a session.

    This runs in a loop, generating interventions every COPILOT_INTERVAL_SECONDS
    until the session's copilot_active flag is set to 0 or max duration is reached.

    Returns:
        Dict with final status and total interventions generated
    """
    db: Session = SessionLocal()
    total_interventions = 0
    iterations = 0
    start_time = time.time()

    try:
        # Mark session as having active copilot
        session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
        if not session:
            return {"error": "Session not found", "session_id": session_id}

        session.copilot_active = 1
        db.commit()

        logger.info(f"Starting continuous copilot for session {session_id}")

        while True:
            # Check if we should stop
            db.refresh(session)  # Reload session state from DB

            elapsed = time.time() - start_time
            if session.copilot_active == 0:
                logger.info(f"Copilot stopped by user for session {session_id}")
                break

            if elapsed >= COPILOT_MAX_DURATION_SECONDS:
                logger.info(f"Copilot max duration reached for session {session_id}")
                break

            # Run single iteration
            try:
                result = run_copilot_single_iteration(session_id, db)
                if result.get("interventions"):
                    total_interventions += len(result["interventions"])
                iterations += 1
                logger.info(f"Copilot iteration {iterations} complete for session {session_id}")
            except Exception as e:
                logger.exception(f"Error in copilot iteration for session {session_id}: {e}")

            # Wait before next iteration
            time.sleep(COPILOT_INTERVAL_SECONDS)

        # Mark copilot as inactive
        session.copilot_active = 0
        session.copilot_task_id = None
        db.commit()

        return {
            "session_id": session_id,
            "status": "completed",
            "total_interventions": total_interventions,
            "iterations": iterations,
            "duration_seconds": int(time.time() - start_time),
        }

    except Exception as e:
        db.rollback()
        logger.exception(f"Copilot workflow failed for session {session_id}")
        # Try to mark copilot as inactive on error
        try:
            session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
            if session:
                session.copilot_active = 0
                session.copilot_task_id = None
                db.commit()
        except Exception:
            pass
        return {"error": "Workflow failed", "session_id": session_id}

    finally:
        db.close()


def stop_copilot(session_id: int) -> Dict[str, Any]:
    """
    Stop the copilot for a session by setting copilot_active to 0.
    The running task will check this flag and exit gracefully.
    """
    db: Session = SessionLocal()
    try:
        session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
        if not session:
            return {"error": "Session not found", "session_id": session_id}

        was_active = session.copilot_active == 1
        session.copilot_active = 0
        db.commit()

        return {
            "session_id": session_id,
            "status": "stop_requested",
            "was_active": was_active,
        }

    except Exception as e:
        db.rollback()
        logger.exception(f"Failed to stop copilot for session {session_id}")
        return {"error": str(e), "session_id": session_id}

    finally:
        db.close()
