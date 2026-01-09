"""
Planning Workflow: Syllabus → Session Plans

This workflow generates structured session plans from a course syllabus.
Uses LangGraph for orchestration.
"""
from typing import Any, Dict
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.course import Course
from app.models.session import Session as SessionModel


def run_planning_workflow(course_id: int) -> Dict[str, Any]:
    """
    Generate session plans from course syllabus.

    Workflow steps:
    1. Parse syllabus & objectives
    2. Generate session-by-session topics & suggested readings
    3. For each session: propose case study prompt and discussion prompts
    4. Design instructional flow: intro → theory → case → discussion → wrap-up
    5. Insert interaction checkpoints (polls, quick writes, small-group prompts)
    6. Consistency check: ensure objectives are covered
    7. Persist plans + version metadata

    Returns:
        Dict with generated plans and metadata
    """
    db: Session = SessionLocal()
    try:
        course = db.query(Course).filter(Course.id == course_id).first()
        if not course:
            return {"error": "Course not found", "course_id": course_id}

        # Idempotency: delete existing generated sessions for this course
        db.query(SessionModel).filter(SessionModel.course_id == course_id).delete()

        # TODO: Implement LangGraph workflow
        # For now, return a placeholder structure
        plans = {
            "course_id": course_id,
            "course_title": course.title,
            "sessions": [
                {
                    "session_number": 1,
                    "title": "Introduction and Overview",
                    "topics": ["Course introduction", "Learning objectives overview"],
                    "readings": [],
                    "case_prompt": "Placeholder case study prompt",
                    "discussion_prompts": ["What are your expectations?"],
                    "flow": ["intro", "theory", "discussion", "wrap-up"],
                    "checkpoints": [{"type": "poll", "question": "What topic interests you most?"}],
                }
            ],
            "model_name": "placeholder",
            "prompt_version": "v0.1",
        }

        # Create session records in DB (status defaults to "draft")
        for plan in plans["sessions"]:
            db_session = SessionModel(
                course_id=course_id,
                title=plan["title"],
                plan_json=plan,
                plan_version="v0.1",
                model_name="placeholder",
                prompt_version="v0.1",
            )
            db.add(db_session)

        db.commit()
        return plans

    except Exception as e:
        db.rollback()
        return {"error": str(e), "course_id": course_id}

    finally:
        db.close()
