"""
Canvas Push Workflow: Push session summaries to Canvas as announcements or assignments.

This workflow:
1. Gathers session content (posts, polls, cases, plan)
2. Generates an LLM summary of the session
3. Pushes the content to Canvas via the Canvas API

Supports push types:
- announcement: Creates a Canvas announcement with the session summary
- assignment: Creates a Canvas assignment (for reflection/follow-up)
"""
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

from api.core.database import SessionLocal
from api.models.session import Session as SessionModel
from api.models.course import Course
from api.models.post import Post
from api.models.user import User
from api.models.poll import Poll, PollVote
from api.models.integration import IntegrationCanvasPush, IntegrationProviderConnection, IntegrationCourseMapping
from api.core.secrets import decrypt_secret
from workflows.llm_utils import (
    get_llm_with_tracking,
    invoke_llm_with_metrics,
    format_posts_for_prompt,
    LLMMetrics,
)

logger = logging.getLogger(__name__)


# ============ Prompts ============

SUMMARIZE_SESSION_PROMPT = """You are a helpful teaching assistant. Generate a concise summary of this class discussion session for students.

Session: {session_title}
Topics: {topics}

Discussion Posts:
{posts_formatted}

Poll Results:
{poll_results}

Generate a summary that includes:
1. Key discussion themes (2-3 sentences)
2. Main takeaways from the discussion (bullet points)
3. Areas that may need review based on the discussion
4. (Optional) Follow-up questions for reflection

Keep the summary under 500 words. Write in an encouraging, educational tone.
Format as HTML suitable for a Canvas announcement (use <p>, <ul>, <li>, <strong>, <em> tags).
"""

SUMMARIZE_FOR_ASSIGNMENT_PROMPT = """You are a helpful teaching assistant. Create a reflection assignment based on this class discussion session.

Session: {session_title}
Topics: {topics}

Discussion Posts:
{posts_formatted}

Poll Results:
{poll_results}

Generate an assignment that asks students to:
1. Reflect on what they learned from the discussion
2. Address any misconceptions or areas of confusion
3. Connect the discussion to course concepts

Include:
- Assignment description (2-3 paragraphs)
- 2-3 specific reflection questions

Keep the total under 400 words. Write in an encouraging, educational tone.
Format as HTML suitable for Canvas (use <p>, <ul>, <li>, <strong>, <em> tags).
"""


# ============ Canvas API Helpers ============

def create_canvas_announcement(
    api_base_url: str,
    api_token: str,
    course_id: str,
    title: str,
    message: str,
) -> Dict[str, Any]:
    """Create an announcement in a Canvas course."""
    url = f"{api_base_url}/api/v1/courses/{course_id}/discussion_topics"
    headers = {"Authorization": f"Bearer {api_token}"}

    data = {
        "title": title,
        "message": message,
        "is_announcement": True,
        "published": True,
    }

    with httpx.Client(timeout=30.0, headers=headers) as client:
        response = client.post(url, data=data)
        response.raise_for_status()
        return response.json()


def create_canvas_assignment(
    api_base_url: str,
    api_token: str,
    course_id: str,
    title: str,
    description: str,
    points_possible: int = 10,
    submission_types: List[str] = None,
) -> Dict[str, Any]:
    """Create an assignment in a Canvas course."""
    url = f"{api_base_url}/api/v1/courses/{course_id}/assignments"
    headers = {"Authorization": f"Bearer {api_token}"}

    if submission_types is None:
        submission_types = ["online_text_entry"]

    data = {
        "assignment[name]": title,
        "assignment[description]": description,
        "assignment[points_possible]": points_possible,
        "assignment[submission_types][]": submission_types,
        "assignment[published]": True,
    }

    with httpx.Client(timeout=30.0, headers=headers) as client:
        response = client.post(url, data=data)
        response.raise_for_status()
        return response.json()


# ============ Data Gathering ============

def gather_session_content(db, session_id: int) -> Dict[str, Any]:
    """Gather all session content for summarization."""
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise ValueError(f"Session {session_id} not found")

    course = db.query(Course).filter(Course.id == session.course_id).first()
    if not course:
        raise ValueError(f"Course for session {session_id} not found")

    # Get posts with users
    posts_with_users = (
        db.query(Post, User)
        .join(User, Post.user_id == User.id)
        .filter(Post.session_id == session_id)
        .order_by(Post.created_at.asc())
        .all()
    )

    posts_data = [
        {
            "post_id": post.id,
            "author_role": user.role.value if user.role else "student",
            "content": post.content,
            "timestamp": post.created_at.isoformat() if post.created_at else "",
            "pinned": post.pinned,
            "labels": post.labels_json or [],
        }
        for post, user in posts_with_users
    ]

    # Get polls
    polls = db.query(Poll).filter(Poll.session_id == session_id).all()
    poll_data = []
    for poll in polls:
        votes = db.query(PollVote).filter(PollVote.poll_id == poll.id).all()
        options = poll.options_json or []
        vote_counts = [0] * len(options)
        for v in votes:
            if 0 <= v.option_index < len(options):
                vote_counts[v.option_index] += 1

        poll_data.append({
            "question": poll.question,
            "options": options,
            "vote_counts": vote_counts,
            "total_votes": len(votes),
        })

    # Get topics from plan
    topics = []
    if session.plan_json:
        topics = session.plan_json.get("topics", [])

    return {
        "session": session,
        "course": course,
        "posts": posts_data,
        "polls": poll_data,
        "topics": topics,
    }


def format_poll_results(polls: List[Dict[str, Any]]) -> str:
    """Format poll results for the LLM prompt."""
    if not polls:
        return "No polls conducted during this session."

    lines = []
    for poll in polls:
        lines.append(f"Q: {poll['question']}")
        total = poll['total_votes'] or 1
        for opt, count in zip(poll['options'], poll['vote_counts']):
            pct = (count / total * 100) if total > 0 else 0
            lines.append(f"  - {opt}: {count} votes ({pct:.0f}%)")
        lines.append("")
    return "\n".join(lines)


# ============ Main Workflow ============

def run_canvas_push_workflow(
    push_id: int,
    session_id: int,
    connection_id: int,
    external_course_id: str,
    push_type: str,  # "announcement" or "assignment"
    custom_title: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Run the Canvas push workflow.

    Args:
        push_id: ID of the IntegrationCanvasPush record
        session_id: ID of the session to summarize
        connection_id: ID of the Canvas connection to use
        external_course_id: Canvas course ID to push to
        push_type: "announcement" or "assignment"
        custom_title: Optional custom title for the announcement/assignment

    Returns:
        Dict with result and metrics
    """
    db = SessionLocal()
    start_time = time.time()
    metrics = LLMMetrics()

    try:
        # Update push record to running
        push = db.query(IntegrationCanvasPush).filter(IntegrationCanvasPush.id == push_id).first()
        if not push:
            return {"error": "Push record not found", "push_id": push_id}

        push.status = "running"
        push.started_at = datetime.now(timezone.utc)
        db.commit()

        # Get Canvas connection
        connection = db.query(IntegrationProviderConnection).filter(
            IntegrationProviderConnection.id == connection_id
        ).first()

        if not connection:
            raise ValueError(f"Canvas connection {connection_id} not found")

        if connection.provider != "canvas":
            raise ValueError(f"Connection {connection_id} is not a Canvas connection")

        api_base_url = connection.api_base_url.rstrip("/")
        api_token = decrypt_secret(connection.api_token_encrypted)

        # Gather session content
        content = gather_session_content(db, session_id)
        session = content["session"]

        # Format posts for LLM
        posts_formatted = format_posts_for_prompt(content["posts"][:50])  # Limit to 50 posts
        poll_results_formatted = format_poll_results(content["polls"])
        topics_str = ", ".join(content["topics"]) if content["topics"] else "General discussion"

        # Generate summary using LLM
        llm, model_name = get_llm_with_tracking()

        if not llm:
            raise RuntimeError("No LLM configured. Set OPENAI_API_KEY or ANTHROPIC_API_KEY.")

        # Choose prompt based on push type
        if push_type == "assignment":
            prompt = SUMMARIZE_FOR_ASSIGNMENT_PROMPT.format(
                session_title=session.title,
                topics=topics_str,
                posts_formatted=posts_formatted,
                poll_results=poll_results_formatted,
            )
        else:
            prompt = SUMMARIZE_SESSION_PROMPT.format(
                session_title=session.title,
                topics=topics_str,
                posts_formatted=posts_formatted,
                poll_results=poll_results_formatted,
            )

        response = invoke_llm_with_metrics(llm, prompt, model_name)
        metrics = response.metrics

        if not response.success:
            raise RuntimeError(f"LLM summarization failed: {metrics.error_message}")

        summary_content = response.content

        # Generate title
        if custom_title:
            title = custom_title
        else:
            date_str = datetime.now().strftime("%B %d, %Y")
            if push_type == "assignment":
                title = f"Reflection: {session.title}"
            else:
                title = f"Session Summary: {session.title} ({date_str})"

        # Push to Canvas
        if push_type == "assignment":
            result = create_canvas_assignment(
                api_base_url=api_base_url,
                api_token=api_token,
                course_id=external_course_id,
                title=title,
                description=summary_content,
                points_possible=10,
            )
            external_id = str(result.get("id", ""))
        else:
            result = create_canvas_announcement(
                api_base_url=api_base_url,
                api_token=api_token,
                course_id=external_course_id,
                title=title,
                message=summary_content,
            )
            external_id = str(result.get("id", ""))

        # Update push record with success
        execution_time = round(time.time() - start_time, 2)

        push.status = "completed"
        push.completed_at = datetime.now(timezone.utc)
        push.external_id = external_id
        push.title = title
        push.content_summary = summary_content[:2000]  # Truncate for storage
        push.model_name = model_name
        push.prompt_tokens = metrics.prompt_tokens
        push.completion_tokens = metrics.completion_tokens
        push.total_tokens = metrics.total_tokens
        push.estimated_cost_usd = str(metrics.estimated_cost_usd)
        push.execution_time_seconds = str(execution_time)
        db.commit()

        logger.info(f"Canvas push completed: {push_type} '{title}' to course {external_course_id}")

        return {
            "push_id": push_id,
            "status": "completed",
            "push_type": push_type,
            "external_id": external_id,
            "title": title,
            "canvas_course_id": external_course_id,
            "execution_time_seconds": execution_time,
            "model_name": model_name,
            "total_tokens": metrics.total_tokens,
            "estimated_cost_usd": metrics.estimated_cost_usd,
        }

    except Exception as e:
        error_message = str(e)
        logger.exception(f"Canvas push workflow failed: {error_message}")

        # Update push record with error
        try:
            push = db.query(IntegrationCanvasPush).filter(IntegrationCanvasPush.id == push_id).first()
            if push:
                push.status = "failed"
                push.completed_at = datetime.now(timezone.utc)
                push.error_message = error_message
                push.execution_time_seconds = str(round(time.time() - start_time, 2))
                db.commit()
        except Exception:
            pass

        return {
            "push_id": push_id,
            "status": "failed",
            "error": error_message,
        }

    finally:
        db.close()


def get_canvas_course_for_session(db, session_id: int, connection_id: int) -> Optional[str]:
    """
    Find the Canvas course ID mapped to this session's course.

    Returns the external course ID if a mapping exists, None otherwise.
    """
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        return None

    # Look for a course mapping
    mapping = db.query(IntegrationCourseMapping).filter(
        IntegrationCourseMapping.target_course_id == session.course_id,
        IntegrationCourseMapping.provider == "canvas",
        IntegrationCourseMapping.source_connection_id == connection_id,
        IntegrationCourseMapping.is_active == True,
    ).first()

    if mapping:
        return mapping.external_course_id

    return None
