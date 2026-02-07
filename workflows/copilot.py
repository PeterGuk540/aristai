"""
Live Copilot Workflow: Real-time Instructor Suggestions

This workflow analyzes ongoing discussion and generates instructor interventions.
Uses LangGraph for orchestration.

Each iteration:
1. Fetches last N posts (configurable)
2. Includes session plan/topics for context alignment
3. Generates structured interventions with:
   - Rolling summary
   - Top 3 confusion points / misconceptions
   - 2-3 instructor prompts
   - 1 re-engagement activity
   - Optional poll suggestion
4. Includes evidence_post_ids for citations
5. Tracks token usage and cost (Milestone 6)
6. Sends proactive voice alerts for critical conditions
"""
import logging
import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests

from sqlalchemy.orm import Session

from api.core.database import SessionLocal
from api.models.session import Session as SessionModel
from api.models.course import Course
from api.models.post import Post
from api.models.user import User
from api.models.intervention import Intervention
from workflows.llm_utils import (
    get_llm_with_tracking,
    invoke_llm_with_metrics,
    parse_json_response,
    format_posts_for_prompt,
    create_rolling_summary,
    LLMMetrics,
)
from workflows.prompts.copilot_prompts import COPILOT_ANALYSIS_PROMPT

logger = logging.getLogger(__name__)

# Configuration for continuous copilot
COPILOT_INTERVAL_SECONDS = 90  # Run analysis every 90 seconds
COPILOT_MAX_DURATION_SECONDS = 3600  # Max 1 hour runtime
MIN_POSTS_FOR_ANALYSIS = 1  # Minimum posts needed to generate interventions
DEFAULT_POSTS_LIMIT = 20  # Default number of recent posts to analyze

# Proactive alerts configuration
PROACTIVE_ALERTS_ENABLED = True
LOW_PARTICIPATION_THRESHOLD = 0.3  # Alert if participation < 30%
CONFUSION_ALERT_THRESHOLD = 2  # Alert if confusion points >= 2
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")


# ============ Proactive Voice Alerts ============

def send_voice_alert(
    user_id: int,
    message: str,
    alert_type: str = "info",
    priority: str = "normal",
) -> bool:
    """
    Send a proactive voice alert to the instructor.

    This pushes a UI action that the frontend can use to speak the alert
    via the voice assistant.

    Args:
        user_id: The instructor's user ID
        message: The alert message to speak
        alert_type: Type of alert (info, warning, critical)
        priority: Priority level (normal, high)

    Returns:
        True if alert was sent successfully
    """
    if not PROACTIVE_ALERTS_ENABLED:
        return False

    try:
        # Publish a UI action for voice alert
        response = requests.post(
            f"{API_BASE_URL}/api/ui-actions/publish",
            json={
                "user_id": user_id,
                "type": "voice.alert",
                "payload": {
                    "message": message,
                    "alert_type": alert_type,
                    "priority": priority,
                    "speak": True,
                },
            },
            headers={"Authorization": "Bearer internal-worker"},
            timeout=5,
        )
        if response.status_code == 200:
            logger.info(f"Voice alert sent to user {user_id}: {message[:50]}...")
            return True
        else:
            logger.warning(f"Failed to send voice alert: {response.status_code}")
            return False
    except Exception as e:
        logger.warning(f"Error sending voice alert: {e}")
        return False


def check_and_send_alerts(
    session_id: int,
    intervention_data: Dict[str, Any],
    db: Session,
    instructor_user_id: Optional[int] = None,
) -> List[str]:
    """
    Check intervention data for alert conditions and send proactive alerts.

    Args:
        session_id: The session being monitored
        intervention_data: The generated intervention data
        db: Database session
        instructor_user_id: Override instructor user ID (otherwise looked up from course)

    Returns:
        List of alert messages that were sent
    """
    alerts_sent = []

    if not PROACTIVE_ALERTS_ENABLED:
        return alerts_sent

    # Get instructor user ID if not provided
    if not instructor_user_id:
        session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
        if session:
            course = db.query(Course).filter(Course.id == session.course_id).first()
            if course:
                instructor_user_id = course.instructor_id

    if not instructor_user_id:
        logger.warning("No instructor user ID found for alerts")
        return alerts_sent

    # Check for critical confusion points
    confusion_points = intervention_data.get("confusion_points", [])
    if len(confusion_points) >= CONFUSION_ALERT_THRESHOLD:
        issues = [cp.get("issue", "Unknown") for cp in confusion_points[:2]]
        message = f"Alert: {len(confusion_points)} areas of confusion detected. Top issues: {'; '.join(issues)}"
        if send_voice_alert(instructor_user_id, message, "warning", "high"):
            alerts_sent.append(message)

    # Check overall assessment for low engagement
    assessment = intervention_data.get("overall_assessment", {})
    engagement_level = assessment.get("engagement_level", "").lower()
    if engagement_level in ["low", "very_low", "minimal"]:
        message = f"Alert: Student engagement is {engagement_level}. Consider using a re-engagement activity."
        if send_voice_alert(instructor_user_id, message, "warning", "normal"):
            alerts_sent.append(message)

    # Check for low understanding
    understanding_level = assessment.get("understanding_level", "").lower()
    if understanding_level in ["low", "struggling", "confused"]:
        message = f"Alert: Class understanding appears {understanding_level}. You may want to clarify key concepts."
        if send_voice_alert(instructor_user_id, message, "warning", "normal"):
            alerts_sent.append(message)

    return alerts_sent


# ============ Data Formatting ============

def format_session_plan(plan_json: Optional[Dict[str, Any]]) -> str:
    """Format session plan for inclusion in prompts."""
    if not plan_json:
        return "No session plan available."

    parts = []

    if plan_json.get("topics"):
        parts.append(f"Topics: {', '.join(plan_json['topics'])}")

    if plan_json.get("goals"):
        if isinstance(plan_json["goals"], list):
            parts.append(f"Goals: {'; '.join(plan_json['goals'])}")
        else:
            parts.append(f"Goals: {plan_json['goals']}")

    if plan_json.get("key_concepts"):
        parts.append(f"Key Concepts: {', '.join(plan_json['key_concepts'])}")

    if plan_json.get("discussion_prompts"):
        prompts = plan_json["discussion_prompts"]
        if isinstance(prompts, list) and prompts:
            parts.append(f"Discussion Prompts: {prompts[0]}")

    if plan_json.get("case"):
        case_info = plan_json["case"]
        if isinstance(case_info, dict):
            parts.append(f"Case: {case_info.get('title', case_info.get('scenario', ''))}")
        else:
            parts.append(f"Case: {case_info}")

    return "\n".join(parts) if parts else "Session plan details not available."


def get_posts_data(posts: List[Post], db: Session) -> List[Dict[str, Any]]:
    """Convert Post models to dictionaries with user roles."""
    posts_data = []
    user_cache = {}

    for post in posts:
        # Get user role (with caching)
        if post.user_id not in user_cache:
            user = db.query(User).filter(User.id == post.user_id).first()
            user_cache[post.user_id] = user.role.value if user else "student"

        posts_data.append({
            "post_id": post.id,
            "user_id": post.user_id,
            "author_role": user_cache[post.user_id],
            "content": post.content,
            "timestamp": post.created_at.strftime("%H:%M:%S") if post.created_at else "",
            "pinned": post.pinned,
            "labels": post.labels_json or [],
        })

    return posts_data


def extract_evidence_post_ids(analysis: Dict[str, Any]) -> List[int]:
    """Extract all post IDs cited as evidence in the analysis."""
    evidence_ids = set()

    # From confusion points
    for cp in analysis.get("confusion_points", []):
        if cp.get("evidence_post_ids"):
            evidence_ids.update(cp["evidence_post_ids"])

    return list(evidence_ids)


# ============ Fallback Generation ============

def generate_fallback_intervention(
    session_id: int,
    posts_data: List[Dict[str, Any]],
    session_plan: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Generate a basic intervention when LLM is not available."""
    post_ids = [p["post_id"] for p in posts_data[:5]]

    return {
        "rolling_summary": f"Discussion is ongoing with {len(posts_data)} recent posts.",
        "confusion_points": [],
        "instructor_prompts": [
            {
                "prompt": "Can someone summarize the key points we've discussed so far?",
                "purpose": "Check understanding and encourage synthesis",
                "target": "whole_class"
            },
            {
                "prompt": "What questions do you still have about this topic?",
                "purpose": "Surface remaining confusion",
                "target": "whole_class"
            }
        ],
        "reengagement_activity": {
            "type": "think_pair_share",
            "description": "Take 30 seconds to formulate your main takeaway, then share with a neighbor.",
            "estimated_time": "2 minutes"
        },
        "poll_suggestion": None,
        "overall_assessment": {
            "engagement_level": "medium",
            "understanding_level": "developing",
            "discussion_quality": "on_track",
            "recommendation": "Continue monitoring discussion and intervene if needed."
        },
        "evidence_post_ids": post_ids,
        "model_name": "fallback",
        "generated_at": datetime.utcnow().isoformat(),
    }


# ============ Main Analysis Function ============

def run_copilot_single_iteration(
    session_id: int,
    db: Session,
    posts_limit: int = DEFAULT_POSTS_LIMIT,
) -> Dict[str, Any]:
    """
    Run a single iteration of copilot analysis.

    Workflow steps:
    1. Fetch session context (plan, objectives, course info)
    2. Fetch last N posts
    3. Invoke LLM for comprehensive analysis
    4. Parse response and structure intervention data
    5. Save intervention to database with observability metrics

    Args:
        session_id: The session to analyze
        db: Database session
        posts_limit: Number of recent posts to analyze (default: 20)

    Returns:
        Dict with generated interventions and metadata
    """
    start_time = time.time()

    # Get session with course info
    session = (
        db.query(SessionModel)
        .filter(SessionModel.id == session_id)
        .first()
    )
    if not session:
        return {"session_id": session_id, "error": "Session not found"}

    # Get course for objectives
    course = db.query(Course).filter(Course.id == session.course_id).first()
    objectives = course.objectives_json if course and course.objectives_json else []
    if isinstance(objectives, list):
        objectives_text = "\n".join(f"- {obj}" for obj in objectives)
    else:
        objectives_text = str(objectives) if objectives else "No specific objectives defined."

    # Get recent posts (ordered by creation time, most recent first)
    posts = (
        db.query(Post)
        .filter(Post.session_id == session_id)
        .order_by(Post.created_at.desc())
        .limit(posts_limit)
        .all()
    )

    if len(posts) < MIN_POSTS_FOR_ANALYSIS:
        return {
            "session_id": session_id,
            "interventions": [],
            "message": "Not enough posts to analyze",
            "posts_count": len(posts),
        }

    # Reverse to get chronological order for analysis
    posts = list(reversed(posts))
    posts_data = get_posts_data(posts, db)

    # Apply rolling summary for token control (Milestone 6)
    recent_posts, older_summary = create_rolling_summary(posts_data, max_posts=posts_limit)
    posts_text = format_posts_for_prompt(recent_posts)
    if older_summary:
        posts_text = older_summary + "\n\n" + posts_text

    session_plan_text = format_session_plan(session.plan_json)

    # Get LLM
    llm, model_name = get_llm_with_tracking()
    metrics = LLMMetrics(model_name=model_name or "fallback")

    if llm is None:
        # No LLM available - use fallback
        logger.warning("No LLM API key configured, using fallback intervention")
        intervention_data = generate_fallback_intervention(
            session_id, posts_data, session.plan_json
        )
        model_name = "fallback"
        metrics.used_fallback = True
        metrics.execution_time_seconds = round(time.time() - start_time, 3)
    else:
        # Build prompt
        prompt = COPILOT_ANALYSIS_PROMPT.format(
            session_title=session.title,
            session_plan=session_plan_text,
            objectives=objectives_text,
            post_count=len(recent_posts),
            posts_text=posts_text,
        )

        # Invoke LLM with metrics tracking
        logger.info(f"Invoking LLM for copilot analysis on session {session_id}")
        response = invoke_llm_with_metrics(llm, prompt, model_name)
        metrics = response.metrics

        if not response.success or not response.content:
            logger.error("LLM returned empty response, using fallback")
            intervention_data = generate_fallback_intervention(
                session_id, posts_data, session.plan_json
            )
            model_name = "fallback"
            metrics.used_fallback = True
        else:
            # Parse LLM response
            parsed = parse_json_response(response.content)
            if not parsed:
                logger.error("Failed to parse LLM response, using fallback")
                intervention_data = generate_fallback_intervention(
                    session_id, posts_data, session.plan_json
                )
                model_name = "fallback"
                metrics.used_fallback = True
            else:
                # Successful LLM analysis
                intervention_data = parsed
                intervention_data["model_name"] = model_name
                intervention_data["generated_at"] = datetime.utcnow().isoformat()

    # Extract evidence post IDs
    evidence_post_ids = extract_evidence_post_ids(intervention_data)
    if not evidence_post_ids:
        # If no evidence cited, use recent post IDs
        evidence_post_ids = [p["post_id"] for p in posts_data[:5]]
    intervention_data["evidence_post_ids"] = evidence_post_ids

    # Determine intervention type based on content
    if intervention_data.get("confusion_points"):
        intervention_type = "clarification_flag"
    elif intervention_data.get("poll_suggestion"):
        intervention_type = "poll_suggestion"
    elif intervention_data.get("reengagement_activity"):
        intervention_type = "activity"
    else:
        intervention_type = "prompt"

    # Calculate final execution time
    execution_time = round(time.time() - start_time, 3)

    # Save intervention to DB with observability fields
    db_intervention = Intervention(
        session_id=session_id,
        intervention_type=intervention_type,
        suggestion_json=intervention_data,
        model_name=model_name,
        prompt_version="v1.0",
        evidence_post_ids=evidence_post_ids,
        # Observability fields (Milestone 6)
        execution_time_seconds=execution_time,
        total_tokens=metrics.total_tokens,
        prompt_tokens=metrics.prompt_tokens,
        completion_tokens=metrics.completion_tokens,
        estimated_cost_usd=metrics.estimated_cost_usd,
        error_message=metrics.error_message,
        used_fallback=1 if metrics.used_fallback else 0,
        posts_analyzed=len(posts_data),
    )
    db.add(db_intervention)
    db.commit()
    db.refresh(db_intervention)

    # Send proactive voice alerts for critical conditions
    alerts_sent = check_and_send_alerts(session_id, intervention_data, db)
    if alerts_sent:
        logger.info(f"Sent {len(alerts_sent)} proactive alerts for session {session_id}")

    logger.info(
        f"Copilot iteration complete for session {session_id}: "
        f"type={intervention_type}, evidence_posts={len(evidence_post_ids)}, "
        f"tokens={metrics.total_tokens}, cost=${metrics.estimated_cost_usd:.4f}"
    )

    return {
        "session_id": session_id,
        "intervention_id": db_intervention.id,
        "intervention_type": intervention_type,
        "posts_analyzed": len(posts_data),
        "evidence_post_ids": evidence_post_ids,
        "model_name": model_name,
        "observability": {
            "execution_time_seconds": execution_time,
            "total_tokens": metrics.total_tokens,
            "estimated_cost_usd": metrics.estimated_cost_usd,
            "used_fallback": metrics.used_fallback,
        },
    }


# ============ Continuous Workflow ============

def run_copilot_workflow(
    session_id: int,
    posts_limit: int = DEFAULT_POSTS_LIMIT,
) -> Dict[str, Any]:
    """
    Run continuous copilot analysis for a session.

    This runs in a loop, generating interventions every COPILOT_INTERVAL_SECONDS
    until the session's copilot_active flag is set to 0 or max duration is reached.

    Args:
        session_id: The session to monitor
        posts_limit: Number of recent posts to analyze each iteration

    Returns:
        Dict with final status and total interventions generated
    """
    db: Session = SessionLocal()
    total_interventions = 0
    iterations = 0
    start_time = time.time()
    total_tokens = 0
    total_cost = 0.0

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
                result = run_copilot_single_iteration(session_id, db, posts_limit)
                if result.get("intervention_id"):
                    total_interventions += 1
                    # Accumulate observability metrics
                    obs = result.get("observability", {})
                    total_tokens += obs.get("total_tokens", 0)
                    total_cost += obs.get("estimated_cost_usd", 0)
                iterations += 1
                logger.info(
                    f"Copilot iteration {iterations} complete for session {session_id}, "
                    f"total interventions: {total_interventions}"
                )
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
            "observability": {
                "total_tokens": total_tokens,
                "total_cost_usd": round(total_cost, 4),
            },
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
        return {"error": str(e), "session_id": session_id}

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
