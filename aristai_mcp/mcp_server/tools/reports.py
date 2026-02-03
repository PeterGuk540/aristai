"""
Report-related MCP tools.

Tools for generating and viewing feedback reports.
"""

import logging
from typing import Any, Dict

from sqlalchemy.orm import Session
from sqlalchemy import func

from api.models.session import Session as SessionModel
from api.models.course import Course
from api.models.report import Report
from api.models.post import Post
from api.models.user import User, UserRole
from api.models.enrollment import Enrollment

logger = logging.getLogger(__name__)


def get_report(db: Session, session_id: int) -> Dict[str, Any]:
    """
    Get the feedback report for a session.
    """
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        return {"error": f"Session {session_id} not found"}
    
    report = (
        db.query(Report)
        .filter(Report.session_id == session_id)
        .order_by(Report.created_at.desc())
        .first()
    )
    
    if not report:
        return {
            "message": f"No report has been generated for session '{session.title}' yet. Use generate_report to create one.",
            "session_id": session_id,
            "session_title": session.title,
            "has_report": False,
        }
    
    report_json = report.report_json or {}
    
    # Voice-friendly summary
    summary = report_json.get("summary", {})
    message = f"Report for '{session.title}'. "
    message += f"Posts analyzed: {summary.get('total_posts', 0)}. "
    message += f"Discussion quality: {summary.get('discussion_quality', 'unknown')}. "
    
    # Mention key findings
    misconceptions = report_json.get("misconceptions", [])
    if misconceptions:
        message += f"Found {len(misconceptions)} misconception{'s' if len(misconceptions) != 1 else ''}. "
    
    themes = report_json.get("theme_clusters", [])
    if themes:
        theme_names = [t.get("theme", "") for t in themes[:3]]
        message += f"Themes: {', '.join(theme_names)}."
    
    return {
        "message": message,
        "session_id": session_id,
        "session_title": session.title,
        "has_report": True,
        "report_id": report.id,
        "version": report.version,
        "summary": summary,
        "themes": themes,
        "misconceptions": misconceptions,
        "objectives_alignment": report_json.get("learning_objectives_alignment", []),
        "best_practice_answer": report_json.get("best_practice_answer", {}),
        "student_summary": report_json.get("student_summary", {}),
        "answer_scores": report_json.get("answer_scores", {}),
        "participation": report_json.get("participation", {}),
        "created_at": report.created_at.isoformat() if report.created_at else None,
    }


def get_report_summary(db: Session, session_id: int) -> Dict[str, Any]:
    """
    Get a concise voice-friendly summary of the report.
    """
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        return {"error": f"Session {session_id} not found"}
    
    report = (
        db.query(Report)
        .filter(Report.session_id == session_id)
        .order_by(Report.created_at.desc())
        .first()
    )
    
    if not report:
        return {
            "message": f"No report available for session '{session.title}'.",
            "session_id": session_id,
            "has_report": False,
        }
    
    report_json = report.report_json or {}
    
    # Build a comprehensive voice summary
    parts = []
    
    # Basic stats
    summary = report_json.get("summary", {})
    parts.append(f"Session '{session.title}' had {summary.get('total_posts', 0)} posts.")
    parts.append(f"Discussion quality was {summary.get('discussion_quality', 'not assessed')}.")
    
    # Participation
    participation = report_json.get("participation", {})
    if participation.get("total_enrolled_students", 0) > 0:
        rate = participation.get("participation_rate", 0)
        parts.append(f"Participation rate was {rate}%.")
        non_participants = participation.get("non_participation_count", 0)
        if non_participants > 0:
            parts.append(f"{non_participants} student{'s' if non_participants != 1 else ''} did not participate.")
    
    # Themes
    themes = report_json.get("theme_clusters", [])
    if themes:
        theme_names = [t.get("theme", "") for t in themes[:3]]
        parts.append(f"Main themes discussed: {', '.join(theme_names)}.")
    
    # Misconceptions
    misconceptions = report_json.get("misconceptions", [])
    if misconceptions:
        parts.append(f"Identified {len(misconceptions)} misconception{'s' if len(misconceptions) != 1 else ''}.")
        first_misc = misconceptions[0]
        parts.append(f"Key misconception: {first_misc.get('misconception', 'unknown')[:100]}.")
    
    # Objectives coverage
    alignment = report_json.get("learning_objectives_alignment", [])
    if alignment:
        fully_covered = sum(1 for a in alignment if a.get("coverage") == "fully")
        total = len(alignment)
        parts.append(f"{fully_covered} of {total} learning objectives were fully covered.")
    
    # Scores
    scores = report_json.get("answer_scores", {})
    stats = scores.get("class_statistics", {})
    if stats.get("average_score"):
        parts.append(f"Average student score was {stats['average_score']} out of 100.")
        closest = scores.get("closest_to_correct", {})
        if closest.get("user_name"):
            parts.append(f"Best response from {closest['user_name']} with score {closest['score']}.")
    
    message = " ".join(parts)
    
    return {
        "message": message,
        "session_id": session_id,
        "session_title": session.title,
        "has_report": True,
        "total_posts": summary.get("total_posts", 0),
        "discussion_quality": summary.get("discussion_quality"),
        "participation_rate": participation.get("participation_rate"),
        "theme_count": len(themes),
        "misconception_count": len(misconceptions),
        "average_score": stats.get("average_score"),
    }


def get_participation_stats(db: Session, session_id: int) -> Dict[str, Any]:
    """
    Get participation statistics for a session.
    """
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        return {"error": f"Session {session_id} not found"}
    
    course = db.query(Course).filter(Course.id == session.course_id).first()
    if not course:
        return {"error": "Course not found"}
    
    # Get enrolled students
    enrolled_students = (
        db.query(User)
        .join(Enrollment, User.id == Enrollment.user_id)
        .filter(
            Enrollment.course_id == course.id,
            User.role == UserRole.student
        )
        .all()
    )
    
    enrolled_ids = {s.id for s in enrolled_students}
    enrolled_count = len(enrolled_ids)
    
    if enrolled_count == 0:
        return {
            "message": "No students are enrolled in this course.",
            "session_id": session_id,
            "enrolled_count": 0,
            "participation_rate": 0,
        }
    
    # Get students who posted
    posts_by_student = (
        db.query(
            Post.user_id,
            User.name,
            func.count(Post.id).label('post_count')
        )
        .join(User, Post.user_id == User.id)
        .filter(
            Post.session_id == session_id,
            User.role == UserRole.student
        )
        .group_by(Post.user_id, User.name)
        .all()
    )
    
    participated_ids = {p.user_id for p in posts_by_student}
    
    participants = [
        {"user_id": p.user_id, "name": p.name, "post_count": p.post_count}
        for p in posts_by_student
    ]
    
    non_participants = [
        {"user_id": s.id, "name": s.name}
        for s in enrolled_students if s.id not in participated_ids
    ]
    
    participation_rate = (len(participated_ids) / enrolled_count * 100) if enrolled_count > 0 else 0
    participation_rate = round(participation_rate, 1)
    
    # Voice-friendly message
    message = f"Session '{session.title}': "
    message += f"{len(participants)} of {enrolled_count} students participated ({participation_rate}%). "
    
    if non_participants:
        names = [s["name"] for s in non_participants[:5]]
        message += f"Students who didn't participate: {', '.join(names)}"
        if len(non_participants) > 5:
            message += f" and {len(non_participants) - 5} more."
    
    return {
        "message": message,
        "session_id": session_id,
        "session_title": session.title,
        "enrolled_count": enrolled_count,
        "participated_count": len(participants),
        "non_participated_count": len(non_participants),
        "participation_rate": participation_rate,
        "participants": participants,
        "non_participants": non_participants,
    }


def get_student_scores(db: Session, session_id: int) -> Dict[str, Any]:
    """
    Get answer scores for students in a session.
    """
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        return {"error": f"Session {session_id} not found"}
    
    report = (
        db.query(Report)
        .filter(Report.session_id == session_id)
        .order_by(Report.created_at.desc())
        .first()
    )
    
    if not report:
        return {
            "message": f"No report with scores available for session '{session.title}'.",
            "session_id": session_id,
            "has_scores": False,
        }
    
    report_json = report.report_json or {}
    scores = report_json.get("answer_scores", {})
    
    if not scores or not scores.get("student_scores"):
        return {
            "message": f"Report exists but no scores were generated for session '{session.title}'.",
            "session_id": session_id,
            "has_scores": False,
        }
    
    student_scores = scores.get("student_scores", [])
    stats = scores.get("class_statistics", {})
    closest = scores.get("closest_to_correct", {})
    furthest = scores.get("furthest_from_correct", {})
    
    # Sort by score descending
    sorted_scores = sorted(student_scores, key=lambda x: x.get("score", 0), reverse=True)
    
    # Voice-friendly message
    message = f"Scores for session '{session.title}': "
    message += f"Average score is {stats.get('average_score', 0)} out of 100. "
    
    if closest.get("user_name"):
        message += f"Best: {closest['user_name']} with {closest['score']}. "
    if furthest.get("user_name"):
        message += f"Lowest: {furthest['user_name']} with {furthest['score']}."
    
    return {
        "message": message,
        "session_id": session_id,
        "session_title": session.title,
        "has_scores": True,
        "average_score": stats.get("average_score"),
        "highest_score": stats.get("highest_score"),
        "lowest_score": stats.get("lowest_score"),
        "score_distribution": stats.get("score_distribution", {}),
        "closest_to_correct": closest,
        "furthest_from_correct": furthest,
        "student_scores": sorted_scores,
    }


def generate_report(db: Session, session_id: int) -> Dict[str, Any]:
    """
    Generate a new feedback report for a session.
    """
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        return {"error": f"Session {session_id} not found"}
    
    # Check if there are posts to analyze
    post_count = db.query(Post).filter(Post.session_id == session_id).count()
    if post_count == 0:
        return {
            "message": f"Session '{session.title}' has no posts to analyze.",
            "session_id": session_id,
            "post_count": 0,
        }
    
    try:
        from worker.tasks import generate_report_task
        task = generate_report_task.delay(session_id)
        
        message = f"Started generating report for session '{session.title}' with {post_count} posts. "
        message += "This may take a minute. Check back soon to see the report."
        
        return {
            "message": message,
            "session_id": session_id,
            "session_title": session.title,
            "task_id": task.id,
            "post_count": post_count,
            "status": "queued",
            "success": True,
        }
        
    except Exception as e:
        logger.exception(f"Failed to queue report generation: {e}")
        return {"error": f"Failed to start report generation: {str(e)}"}
