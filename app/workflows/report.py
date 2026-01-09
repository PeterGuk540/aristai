"""
Report Workflow: Post-Discussion Feedback Generation

This workflow generates structured feedback reports after a session ends.
Uses LangGraph for orchestration.
"""
import logging
from datetime import datetime
from typing import Any, Dict
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.session import Session as SessionModel
from app.models.post import Post
from app.models.poll import Poll, PollVote
from app.models.report import Report

logger = logging.getLogger(__name__)


def run_report_workflow(session_id: int) -> Dict[str, Any]:
    """
    Generate post-discussion feedback report.

    Workflow steps:
    1. Segment discussion into themes/clusters
    2. Align themes to learning objectives
    3. Identify strong contributions (with citations: post ids)
    4. Identify misconceptions and explain why they're incorrect
    5. Produce "best practice / correct answer" section tied to readings/objectives
    6. Create student-facing "What you did well / What to improve" summary
    7. Export as markdown + JSON

    Returns:
        Dict with generated report
    """
    db: Session = SessionLocal()
    try:
        session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
        if not session:
            return {"error": "Session not found", "session_id": session_id}

        # Get all posts for the session
        posts = (
            db.query(Post)
            .filter(Post.session_id == session_id)
            .order_by(Post.created_at.asc())
            .all()
        )

        # Get polls and results
        polls = db.query(Poll).filter(Poll.session_id == session_id).all()

        # Build strong contributions list (empty list if no posts)
        strong_contributions = []
        if posts:
            strong_contributions.append({"post_id": posts[0].id, "reason": "Good insight"})

        # TODO: Implement LangGraph workflow with LLM analysis
        # For now, return a placeholder report
        report_json = {
            "session_id": session_id,
            "session_title": session.title,
            "summary": {
                "total_posts": len(posts),
                "total_polls": len(polls),
                "themes": ["Theme 1: Placeholder", "Theme 2: Placeholder"],
            },
            "learning_objectives_alignment": {
                "covered": ["Objective 1"],
                "partially_covered": ["Objective 2"],
                "not_covered": [],
            },
            "strong_contributions": strong_contributions,
            "misconceptions": [
                {"description": "Common misconception placeholder", "correction": "Correct explanation"}
            ],
            "best_practice_answer": "Placeholder for ideal answer based on course materials.",
            "student_summary": {
                "what_you_did_well": ["Active participation", "Good questions"],
                "what_to_improve": ["Deeper analysis", "Connect to readings"],
            },
            "poll_results": [
                {
                    "poll_id": p.id,
                    "question": p.question,
                    "total_votes": db.query(PollVote).filter(PollVote.poll_id == p.id).count(),
                }
                for p in polls
            ],
        }

        # Generate markdown version
        report_md = f"""# Session Report: {session.title}

## Summary
- Total posts: {len(posts)}
- Total polls: {len(polls)}

## Themes Identified
{chr(10).join(f'- {t}' for t in report_json['summary']['themes'])}

## Learning Objectives Alignment
### Covered
{chr(10).join(f'- {o}' for o in report_json['learning_objectives_alignment']['covered'])}

## Strong Contributions
{chr(10).join(f'- Post #{c.get("post_id", "N/A")}: {c.get("reason", "")}' for c in strong_contributions)}

## Areas for Improvement
{chr(10).join(f'- {i}' for i in report_json['student_summary']['what_to_improve'])}

## Best Practice Answer
{report_json['best_practice_answer']}
"""

        # Timestamp-based version to avoid collision under concurrent runs
        version = f"v_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

        # Save report to DB
        db_report = Report(
            session_id=session_id,
            version=version,
            report_md=report_md,
            report_json=report_json,
            model_name="placeholder",
            prompt_version="v0.1",
        )
        db.add(db_report)
        db.commit()

        return {
            "session_id": session_id,
            "version": version,
            "report_json": report_json,
        }

    except Exception as e:
        db.rollback()
        logger.exception(f"Report workflow failed for session {session_id}")
        return {"error": "Workflow failed", "session_id": session_id}

    finally:
        db.close()
