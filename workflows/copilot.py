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
"""
import json
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from api.core.config import get_settings
from api.core.database import SessionLocal
from api.models.session import Session as SessionModel
from api.models.course import Course
from api.models.post import Post
from api.models.user import User
from api.models.intervention import Intervention
from workflows.prompts.copilot_prompts import COPILOT_ANALYSIS_PROMPT

logger = logging.getLogger(__name__)

# Configuration for continuous copilot
COPILOT_INTERVAL_SECONDS = 90  # Run analysis every 90 seconds
COPILOT_MAX_DURATION_SECONDS = 3600  # Max 1 hour runtime
MIN_POSTS_FOR_ANALYSIS = 1  # Minimum posts needed to generate interventions
DEFAULT_POSTS_LIMIT = 20  # Default number of recent posts to analyze


# ============ LLM Helpers ============

def get_llm():
    """Get the appropriate LLM based on available API keys."""
    settings = get_settings()

    if settings.openai_api_key:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model="gpt-4o-mini",
            api_key=settings.openai_api_key,
            temperature=0.7,
        ), "gpt-4o-mini"
    elif settings.anthropic_api_key:
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model="claude-3-haiku-20240307",
            api_key=settings.anthropic_api_key,
            temperature=0.7,
        ), "claude-3-haiku"
    else:
        return None, None


def invoke_llm(llm, prompt: str) -> Optional[str]:
    """Invoke LLM and return text response."""
    try:
        response = llm.invoke(prompt)
        return response.content
    except Exception as e:
        logger.exception(f"LLM invocation failed: {e}")
        return None


def parse_json_response(response: str) -> Optional[Dict[str, Any]]:
    """Parse JSON from LLM response, handling markdown code blocks."""
    if not response:
        return None

    text = response.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON: {e}\nResponse: {text[:500]}")
        return None


# ============ Data Formatting ============

def format_posts_for_prompt(posts: List[Dict[str, Any]]) -> str:
    """Format posts for inclusion in prompts."""
    if not posts:
        return "No posts in this discussion yet."

    lines = []
    for p in posts:
        role_label = "INSTRUCTOR" if p["author_role"] == "instructor" else "STUDENT"
        pinned = " [PINNED]" if p.get("pinned") else ""
        labels = f" [{', '.join(p.get('labels', []))}]" if p.get("labels") else ""
        lines.append(f"[Post #{p['post_id']}] ({role_label}{pinned}{labels}) {p['timestamp']}")
        lines.append(f"  {p['content']}")
        lines.append("")
    return "\n".join(lines)


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
    5. Save intervention to database

    Args:
        session_id: The session to analyze
        db: Database session
        posts_limit: Number of recent posts to analyze (default: 20)

    Returns:
        Dict with generated interventions and metadata
    """
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
    posts_text = format_posts_for_prompt(posts_data)
    session_plan_text = format_session_plan(session.plan_json)

    # Get LLM
    llm, model_name = get_llm()

    if llm is None:
        # No LLM available - use fallback
        logger.warning("No LLM API key configured, using fallback intervention")
        intervention_data = generate_fallback_intervention(
            session_id, posts_data, session.plan_json
        )
        model_name = "fallback"
    else:
        # Build prompt
        prompt = COPILOT_ANALYSIS_PROMPT.format(
            session_title=session.title,
            session_plan=session_plan_text,
            objectives=objectives_text,
            post_count=len(posts_data),
            posts_text=posts_text,
        )

        # Invoke LLM
        logger.info(f"Invoking LLM for copilot analysis on session {session_id}")
        response = invoke_llm(llm, prompt)

        if not response:
            logger.error("LLM returned empty response, using fallback")
            intervention_data = generate_fallback_intervention(
                session_id, posts_data, session.plan_json
            )
            model_name = "fallback"
        else:
            # Parse LLM response
            parsed = parse_json_response(response)
            if not parsed:
                logger.error("Failed to parse LLM response, using fallback")
                intervention_data = generate_fallback_intervention(
                    session_id, posts_data, session.plan_json
                )
                model_name = "fallback"
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

    # Save intervention to DB
    db_intervention = Intervention(
        session_id=session_id,
        intervention_type=intervention_type,
        suggestion_json=intervention_data,
        model_name=model_name,
        prompt_version="v1.0",
        evidence_post_ids=evidence_post_ids,
    )
    db.add(db_intervention)
    db.commit()
    db.refresh(db_intervention)

    logger.info(
        f"Copilot iteration complete for session {session_id}: "
        f"type={intervention_type}, evidence_posts={len(evidence_post_ids)}"
    )

    return {
        "session_id": session_id,
        "intervention_id": db_intervention.id,
        "intervention_type": intervention_type,
        "posts_analyzed": len(posts_data),
        "evidence_post_ids": evidence_post_ids,
        "model_name": model_name,
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
