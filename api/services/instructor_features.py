"""
Instructor Feature Services.

Implements all the new instructor enhancement features:
1. Real-Time Student Engagement Heatmap
2. Smart Discussion Facilitation
3. Quick Polls from Discussion Context
4. Session Templates & Cloning
5. Student Progress Tracking Across Sessions
6. Breakout Group Management
7. Pre-Class Preparation Insights
8. Post-Class Automated Follow-ups
9. Comparative Analytics
10. Voice-Controlled Timer & Pacing
11. Quick Student Lookup
12. AI Teaching Assistant for Q&A
"""
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, and_

from api.models.user import User
from api.models.session import Session as SessionModel, SessionStatus, Case
from api.models.post import Post
from api.models.poll import Poll, PollVote
from api.models.enrollment import Enrollment
from api.models.engagement import (
    StudentEngagement,
    EngagementLevel,
    SessionTimer,
    BreakoutGroup,
    BreakoutGroupMember,
    SessionTemplate,
    PreClassCheckpoint,
    CheckpointCompletion,
    AIResponseDraft,
)

logger = logging.getLogger(__name__)


# =============================================================================
# 1. REAL-TIME STUDENT ENGAGEMENT HEATMAP
# =============================================================================

def get_engagement_heatmap(db: Session, session_id: int) -> Dict[str, Any]:
    """
    Get real-time engagement data for all students in a session.
    Returns engagement levels and activity metrics for heatmap visualization.
    """
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        return {"error": "Session not found"}

    # Get all enrolled students for this course
    enrolled = db.query(Enrollment).filter(Enrollment.course_id == session.course_id).all()
    enrolled_user_ids = [e.user_id for e in enrolled]

    # Get existing engagement records
    engagements = db.query(StudentEngagement).filter(
        StudentEngagement.session_id == session_id
    ).all()
    engagement_map = {e.user_id: e for e in engagements}

    # Calculate current engagement levels
    now = datetime.utcnow()
    students_data = []

    for user_id in enrolled_user_ids:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            continue

        eng = engagement_map.get(user_id)

        if eng and eng.last_activity_at:
            minutes_since_activity = (now - eng.last_activity_at).total_seconds() / 60

            if minutes_since_activity <= 2:
                level = EngagementLevel.highly_active
            elif minutes_since_activity <= 5:
                level = EngagementLevel.active
            elif minutes_since_activity <= 15:
                level = EngagementLevel.idle
            else:
                level = EngagementLevel.disengaged
        elif eng and eng.joined_at:
            level = EngagementLevel.idle
        else:
            level = EngagementLevel.not_joined

        students_data.append({
            "user_id": user_id,
            "name": user.name,
            "email": user.email,
            "engagement_level": level.value,
            "post_count": eng.post_count if eng else 0,
            "reply_count": eng.reply_count if eng else 0,
            "last_activity": eng.last_activity_at.isoformat() if eng and eng.last_activity_at else None,
            "joined_at": eng.joined_at.isoformat() if eng and eng.joined_at else None,
        })

    # Summary statistics
    level_counts = {}
    for s in students_data:
        level = s["engagement_level"]
        level_counts[level] = level_counts.get(level, 0) + 1

    return {
        "session_id": session_id,
        "total_students": len(students_data),
        "engagement_summary": level_counts,
        "students": students_data,
        "timestamp": now.isoformat(),
    }


def update_student_engagement(db: Session, session_id: int, user_id: int, activity_type: str = "post") -> Dict[str, Any]:
    """
    Update engagement tracking when a student performs an activity.
    Called when students post, reply, or vote.
    """
    eng = db.query(StudentEngagement).filter(
        StudentEngagement.session_id == session_id,
        StudentEngagement.user_id == user_id
    ).first()

    now = datetime.utcnow()

    if not eng:
        eng = StudentEngagement(
            session_id=session_id,
            user_id=user_id,
            joined_at=now,
            last_activity_at=now,
        )
        db.add(eng)

    eng.last_activity_at = now

    if activity_type == "post":
        eng.post_count += 1
    elif activity_type == "reply":
        eng.reply_count += 1
    elif activity_type == "poll_vote":
        eng.poll_votes += 1

    db.commit()
    db.refresh(eng)

    return {"success": True, "engagement_level": eng.engagement_level.value if eng.engagement_level else "active"}


def get_disengaged_students(db: Session, session_id: int) -> Dict[str, Any]:
    """Get list of students who need attention (idle or disengaged)."""
    heatmap = get_engagement_heatmap(db, session_id)
    if "error" in heatmap:
        return heatmap

    needs_attention = [
        s for s in heatmap["students"]
        if s["engagement_level"] in ["idle", "disengaged", "not_joined"]
    ]

    return {
        "session_id": session_id,
        "needs_attention_count": len(needs_attention),
        "students": needs_attention,
    }


# =============================================================================
# 2. SMART DISCUSSION FACILITATION
# =============================================================================

def get_facilitation_suggestions(db: Session, session_id: int) -> Dict[str, Any]:
    """
    Generate smart facilitation suggestions based on discussion patterns.
    Suggests follow-up questions, students to call on, and connection opportunities.
    """
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        return {"error": "Session not found"}

    # Get recent posts (last 10 minutes)
    recent_cutoff = datetime.utcnow() - timedelta(minutes=10)
    recent_posts = db.query(Post).filter(
        Post.session_id == session_id,
        Post.created_at >= recent_cutoff
    ).order_by(Post.created_at.desc()).all()

    # Get participation stats
    post_counts = db.query(
        Post.user_id,
        func.count(Post.id).label("count")
    ).filter(Post.session_id == session_id).group_by(Post.user_id).all()

    participation_map = {pc.user_id: pc.count for pc in post_counts}

    # Find students who haven't participated much
    enrolled = db.query(Enrollment).join(SessionModel, Enrollment.course_id == SessionModel.course_id).filter(
        SessionModel.id == session_id
    ).all()

    low_participation = []
    for e in enrolled:
        count = participation_map.get(e.user_id, 0)
        if count < 2:  # Less than 2 posts
            user = db.query(User).filter(User.id == e.user_id).first()
            if user and user.role.value == "student":
                low_participation.append({
                    "user_id": user.id,
                    "name": user.name,
                    "post_count": count,
                })

    # Analyze discussion momentum
    posts_per_minute = len(recent_posts) / 10.0 if recent_posts else 0
    is_stalling = posts_per_minute < 0.5

    suggestions = []

    if is_stalling:
        suggestions.append({
            "type": "reengagement",
            "priority": "high",
            "message": "Discussion seems to be slowing down. Consider posing a provocative question or calling on a specific student.",
        })

    if low_participation:
        suggestions.append({
            "type": "call_on_student",
            "priority": "medium",
            "message": f"{len(low_participation)} students have low participation. Consider calling on one of them.",
            "students": low_participation[:5],
        })

    # Suggest follow-up if recent posts have questions
    question_posts = [p for p in recent_posts if "?" in p.content]
    if question_posts:
        suggestions.append({
            "type": "address_questions",
            "priority": "high",
            "message": f"There are {len(question_posts)} unanswered questions in recent posts.",
            "post_ids": [p.id for p in question_posts[:3]],
        })

    return {
        "session_id": session_id,
        "discussion_momentum": "stalling" if is_stalling else "active",
        "posts_per_minute": round(posts_per_minute, 2),
        "suggestions": suggestions,
        "low_participation_count": len(low_participation),
    }


def suggest_next_student(db: Session, session_id: int) -> Dict[str, Any]:
    """Suggest which student to call on next based on participation patterns."""
    facilitation = get_facilitation_suggestions(db, session_id)
    if "error" in facilitation:
        return facilitation

    # Prioritize students who haven't participated
    for suggestion in facilitation.get("suggestions", []):
        if suggestion["type"] == "call_on_student" and suggestion.get("students"):
            student = suggestion["students"][0]
            return {
                "suggested_student": student,
                "reason": f"{student['name']} has only made {student['post_count']} posts and could benefit from being called on.",
            }

    return {"message": "All students have good participation levels."}


# =============================================================================
# 3. QUICK POLLS FROM DISCUSSION CONTEXT
# =============================================================================

def suggest_poll_from_discussion(db: Session, session_id: int) -> Dict[str, Any]:
    """
    Analyze recent discussion and suggest relevant poll questions.
    Uses discussion themes and confusion points to generate poll ideas.
    """
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        return {"error": "Session not found"}

    # Get recent posts
    recent_cutoff = datetime.utcnow() - timedelta(minutes=15)
    recent_posts = db.query(Post).filter(
        Post.session_id == session_id,
        Post.created_at >= recent_cutoff
    ).order_by(Post.created_at.desc()).limit(20).all()

    if not recent_posts:
        return {
            "session_id": session_id,
            "suggestions": [],
            "message": "Not enough recent discussion to generate poll suggestions.",
        }

    # Analyze posts for potential poll topics
    # (In production, this would use LLM analysis)
    suggestions = []

    # Check for disagreement patterns (multiple viewpoints)
    posts_content = [p.content.lower() for p in recent_posts]
    has_disagreement = any("disagree" in c or "but" in c or "however" in c for c in posts_content)

    if has_disagreement:
        suggestions.append({
            "type": "opinion_poll",
            "question": "Based on the discussion, which perspective do you find most compelling?",
            "options": ["Perspective A", "Perspective B", "Both have merit", "Neither"],
            "context": "Detected multiple viewpoints in discussion",
        })

    # Check for confusion signals
    has_confusion = any("confused" in c or "don't understand" in c or "unclear" in c for c in posts_content)

    if has_confusion:
        suggestions.append({
            "type": "comprehension_check",
            "question": "How confident are you in your understanding of this topic?",
            "options": ["Very confident", "Somewhat confident", "Need more clarification", "Very confused"],
            "context": "Detected confusion signals in discussion",
        })

    # Default suggestion based on session plan
    if session.plan_json and session.plan_json.get("key_concepts"):
        concepts = session.plan_json["key_concepts"][:3]
        suggestions.append({
            "type": "concept_check",
            "question": f"Which concept from today's session is most challenging?",
            "options": concepts + ["All are clear"],
            "context": "Based on session learning objectives",
        })

    return {
        "session_id": session_id,
        "suggestions": suggestions,
        "analyzed_posts": len(recent_posts),
    }


def create_quick_poll(db: Session, session_id: int, question: str, options: List[str]) -> Dict[str, Any]:
    """Create a poll quickly from a suggestion."""
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        return {"error": "Session not found"}

    poll = Poll(
        session_id=session_id,
        question=question,
        options_json=options,
    )
    db.add(poll)
    db.commit()
    db.refresh(poll)

    return {
        "id": poll.id,
        "question": poll.question,
        "options": poll.options_json,
        "created_at": poll.created_at.isoformat(),
    }


# =============================================================================
# 4. SESSION TEMPLATES & CLONING
# =============================================================================

def save_session_as_template(
    db: Session,
    session_id: int,
    template_name: str,
    user_id: int,
    description: str = None,
    category: str = None
) -> Dict[str, Any]:
    """Save a session's plan as a reusable template."""
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        return {"error": "Session not found"}

    template = SessionTemplate(
        created_by=user_id,
        name=template_name,
        description=description or f"Template based on '{session.title}'",
        category=category,
        plan_json=session.plan_json,
    )
    db.add(template)
    db.commit()
    db.refresh(template)

    return {
        "id": template.id,
        "name": template.name,
        "description": template.description,
        "category": template.category,
    }


def list_templates(db: Session, user_id: int = None, category: str = None) -> Dict[str, Any]:
    """List available session templates."""
    query = db.query(SessionTemplate)

    if user_id:
        query = query.filter(SessionTemplate.created_by == user_id)
    if category:
        query = query.filter(SessionTemplate.category == category)

    templates = query.order_by(SessionTemplate.use_count.desc()).all()

    return {
        "templates": [
            {
                "id": t.id,
                "name": t.name,
                "description": t.description,
                "category": t.category,
                "use_count": t.use_count,
                "created_at": t.created_at.isoformat(),
            }
            for t in templates
        ]
    }


def clone_session(db: Session, session_id: int, new_title: str, course_id: int = None) -> Dict[str, Any]:
    """Clone an existing session with its plan to a new session."""
    original = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not original:
        return {"error": "Session not found"}

    new_session = SessionModel(
        course_id=course_id or original.course_id,
        title=new_title,
        plan_json=original.plan_json,
        plan_version=original.plan_version,
        status=SessionStatus.draft,
    )
    db.add(new_session)
    db.commit()
    db.refresh(new_session)

    return {
        "id": new_session.id,
        "title": new_session.title,
        "cloned_from": session_id,
    }


def create_session_from_template(db: Session, template_id: int, course_id: int, title: str) -> Dict[str, Any]:
    """Create a new session from a template."""
    template = db.query(SessionTemplate).filter(SessionTemplate.id == template_id).first()
    if not template:
        return {"error": "Template not found"}

    new_session = SessionModel(
        course_id=course_id,
        title=title,
        plan_json=template.plan_json,
        status=SessionStatus.draft,
    )
    db.add(new_session)

    # Increment template usage count
    template.use_count += 1

    db.commit()
    db.refresh(new_session)

    return {
        "id": new_session.id,
        "title": new_session.title,
        "from_template": template.name,
    }


# =============================================================================
# 5. STUDENT PROGRESS TRACKING ACROSS SESSIONS
# =============================================================================

def get_student_progress(db: Session, user_id: int, course_id: int = None) -> Dict[str, Any]:
    """Get longitudinal progress for a student across sessions."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {"error": "User not found"}

    # Get all sessions the student participated in
    query = db.query(Post.session_id, func.count(Post.id).label("post_count")).filter(
        Post.user_id == user_id
    ).group_by(Post.session_id)

    if course_id:
        query = query.join(SessionModel).filter(SessionModel.course_id == course_id)

    participation = query.all()

    session_data = []
    for session_id, post_count in participation:
        session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
        if session:
            # Get quality metrics for this session
            quality_posts = db.query(Post).filter(
                Post.session_id == session_id,
                Post.user_id == user_id,
                Post.labels_json.contains(["high-quality"])
            ).count()

            session_data.append({
                "session_id": session_id,
                "session_title": session.title,
                "session_date": session.created_at.isoformat(),
                "post_count": post_count,
                "quality_posts": quality_posts,
            })

    # Calculate trends
    if len(session_data) >= 2:
        recent_avg = sum(s["post_count"] for s in session_data[-3:]) / min(3, len(session_data))
        earlier_avg = sum(s["post_count"] for s in session_data[:-3]) / max(1, len(session_data) - 3) if len(session_data) > 3 else recent_avg
        trend = "improving" if recent_avg > earlier_avg else "declining" if recent_avg < earlier_avg else "stable"
    else:
        trend = "insufficient_data"

    return {
        "user_id": user_id,
        "user_name": user.name,
        "total_sessions": len(session_data),
        "total_posts": sum(s["post_count"] for s in session_data),
        "total_quality_posts": sum(s["quality_posts"] for s in session_data),
        "participation_trend": trend,
        "sessions": session_data,
    }


def get_class_progress_summary(db: Session, course_id: int) -> Dict[str, Any]:
    """Get progress summary for all students in a course."""
    enrollments = db.query(Enrollment).filter(Enrollment.course_id == course_id).all()

    students_progress = []
    for enrollment in enrollments:
        progress = get_student_progress(db, enrollment.user_id, course_id)
        if "error" not in progress:
            students_progress.append({
                "user_id": progress["user_id"],
                "name": progress["user_name"],
                "total_posts": progress["total_posts"],
                "trend": progress["participation_trend"],
            })

    # Sort by total posts descending
    students_progress.sort(key=lambda x: x["total_posts"], reverse=True)

    return {
        "course_id": course_id,
        "total_students": len(students_progress),
        "students": students_progress,
    }


# =============================================================================
# 6. BREAKOUT GROUP MANAGEMENT
# =============================================================================

def create_breakout_groups(
    db: Session,
    session_id: int,
    num_groups: int,
    assignment: str = "random"  # "random" or "balanced"
) -> Dict[str, Any]:
    """Create breakout groups for a session."""
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        return {"error": "Session not found"}

    # Get enrolled students
    enrollments = db.query(Enrollment).filter(Enrollment.course_id == session.course_id).all()
    student_ids = [e.user_id for e in enrollments]

    if len(student_ids) < num_groups:
        return {"error": f"Not enough students ({len(student_ids)}) for {num_groups} groups"}

    # Create groups
    groups = []
    for i in range(num_groups):
        group = BreakoutGroup(
            session_id=session_id,
            name=f"Group {i + 1}",
        )
        db.add(group)
        db.flush()  # Get the ID
        groups.append(group)

    # Assign students to groups
    import random
    if assignment == "random":
        random.shuffle(student_ids)

    for idx, user_id in enumerate(student_ids):
        group_idx = idx % num_groups
        member = BreakoutGroupMember(
            group_id=groups[group_idx].id,
            user_id=user_id,
        )
        db.add(member)

    db.commit()

    # Return group details
    result_groups = []
    for group in groups:
        db.refresh(group)
        members = db.query(BreakoutGroupMember).filter(BreakoutGroupMember.group_id == group.id).all()
        member_details = []
        for m in members:
            user = db.query(User).filter(User.id == m.user_id).first()
            if user:
                member_details.append({"user_id": user.id, "name": user.name})

        result_groups.append({
            "id": group.id,
            "name": group.name,
            "member_count": len(members),
            "members": member_details,
        })

    return {
        "session_id": session_id,
        "num_groups": num_groups,
        "groups": result_groups,
    }


def get_breakout_groups(db: Session, session_id: int) -> Dict[str, Any]:
    """Get all breakout groups for a session."""
    groups = db.query(BreakoutGroup).filter(
        BreakoutGroup.session_id == session_id,
        BreakoutGroup.is_active == True
    ).all()

    result = []
    for group in groups:
        members = db.query(BreakoutGroupMember).filter(BreakoutGroupMember.group_id == group.id).all()
        member_details = []
        for m in members:
            user = db.query(User).filter(User.id == m.user_id).first()
            if user:
                member_details.append({"user_id": user.id, "name": user.name})

        # Get group's discussion stats
        member_ids = [m.user_id for m in members]
        post_count = db.query(Post).filter(
            Post.session_id == session_id,
            Post.user_id.in_(member_ids)
        ).count() if member_ids else 0

        result.append({
            "id": group.id,
            "name": group.name,
            "topic": group.topic,
            "member_count": len(members),
            "members": member_details,
            "post_count": post_count,
        })

    return {
        "session_id": session_id,
        "groups": result,
    }


def dissolve_breakout_groups(db: Session, session_id: int) -> Dict[str, Any]:
    """End breakout session and dissolve groups."""
    groups = db.query(BreakoutGroup).filter(BreakoutGroup.session_id == session_id).all()

    for group in groups:
        group.is_active = False

    db.commit()

    return {"session_id": session_id, "message": f"Dissolved {len(groups)} breakout groups"}


# =============================================================================
# 7. PRE-CLASS PREPARATION INSIGHTS
# =============================================================================

def create_preclass_checkpoint(
    db: Session,
    session_id: int,
    title: str,
    description: str = None,
    checkpoint_type: str = "reading"
) -> Dict[str, Any]:
    """Create a pre-class preparation checkpoint."""
    checkpoint = PreClassCheckpoint(
        session_id=session_id,
        title=title,
        description=description,
        checkpoint_type=checkpoint_type,
    )
    db.add(checkpoint)
    db.commit()
    db.refresh(checkpoint)

    return {
        "id": checkpoint.id,
        "title": checkpoint.title,
        "type": checkpoint.checkpoint_type,
    }


def get_preclass_completion_status(db: Session, session_id: int) -> Dict[str, Any]:
    """Get pre-class preparation completion status for all students."""
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        return {"error": "Session not found"}

    checkpoints = db.query(PreClassCheckpoint).filter(
        PreClassCheckpoint.session_id == session_id
    ).all()

    if not checkpoints:
        return {
            "session_id": session_id,
            "message": "No pre-class checkpoints defined for this session",
            "checkpoints": [],
        }

    # Get enrolled students
    enrollments = db.query(Enrollment).filter(Enrollment.course_id == session.course_id).all()

    checkpoint_results = []
    for checkpoint in checkpoints:
        completions = db.query(CheckpointCompletion).filter(
            CheckpointCompletion.checkpoint_id == checkpoint.id
        ).all()
        completed_user_ids = [c.user_id for c in completions]

        completed_students = []
        incomplete_students = []

        for enrollment in enrollments:
            user = db.query(User).filter(User.id == enrollment.user_id).first()
            if not user:
                continue

            if enrollment.user_id in completed_user_ids:
                completed_students.append({"user_id": user.id, "name": user.name})
            else:
                incomplete_students.append({"user_id": user.id, "name": user.name})

        checkpoint_results.append({
            "checkpoint_id": checkpoint.id,
            "title": checkpoint.title,
            "type": checkpoint.checkpoint_type,
            "completion_rate": len(completed_students) / len(enrollments) * 100 if enrollments else 0,
            "completed_count": len(completed_students),
            "incomplete_count": len(incomplete_students),
            "completed_students": completed_students,
            "incomplete_students": incomplete_students,
        })

    overall_rate = sum(c["completion_rate"] for c in checkpoint_results) / len(checkpoint_results) if checkpoint_results else 0

    return {
        "session_id": session_id,
        "overall_completion_rate": round(overall_rate, 1),
        "checkpoints": checkpoint_results,
    }


# =============================================================================
# 8. POST-CLASS AUTOMATED FOLLOW-UPS
# =============================================================================

def generate_session_summary_email(db: Session, session_id: int) -> Dict[str, Any]:
    """Generate a summary email content for students after a session."""
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        return {"error": "Session not found"}

    # Get session statistics
    posts = db.query(Post).filter(Post.session_id == session_id).all()
    polls = db.query(Poll).filter(Poll.session_id == session_id).all()

    # Get key discussion points (pinned posts)
    pinned_posts = db.query(Post).filter(
        Post.session_id == session_id,
        Post.pinned == True
    ).all()

    # Build email content
    plan = session.plan_json or {}
    topics = plan.get("topics", [])
    key_concepts = plan.get("key_concepts", [])

    email_content = {
        "subject": f"Session Summary: {session.title}",
        "session_title": session.title,
        "date": session.created_at.isoformat(),
        "statistics": {
            "total_posts": len(posts),
            "polls_conducted": len(polls),
        },
        "topics_covered": topics,
        "key_concepts": key_concepts,
        "key_discussion_points": [
            {"author": db.query(User).filter(User.id == p.user_id).first().name if db.query(User).filter(User.id == p.user_id).first() else "Unknown", "content": p.content[:200]}
            for p in pinned_posts[:5]
        ],
        "next_steps": plan.get("follow_up", []) if plan else [],
    }

    return {
        "session_id": session_id,
        "email_content": email_content,
    }


def get_unresolved_topics(db: Session, session_id: int) -> Dict[str, Any]:
    """Identify topics that need follow-up based on discussion patterns."""
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        return {"error": "Session not found"}

    # Get posts with confusion signals
    posts = db.query(Post).filter(Post.session_id == session_id).all()

    confusion_indicators = ["confused", "don't understand", "unclear", "what do you mean", "can you explain"]
    unresolved = []

    for post in posts:
        content_lower = post.content.lower()
        if any(indicator in content_lower for indicator in confusion_indicators):
            # Check if there's a reply that might have resolved it
            replies = db.query(Post).filter(Post.parent_post_id == post.id).all()
            if len(replies) == 0:  # No replies = unresolved
                user = db.query(User).filter(User.id == post.user_id).first()
                unresolved.append({
                    "post_id": post.id,
                    "student": user.name if user else "Unknown",
                    "content": post.content[:150],
                    "created_at": post.created_at.isoformat(),
                })

    return {
        "session_id": session_id,
        "unresolved_count": len(unresolved),
        "unresolved_topics": unresolved,
    }


# =============================================================================
# 9. COMPARATIVE ANALYTICS
# =============================================================================

def compare_sessions(db: Session, session_ids: List[int]) -> Dict[str, Any]:
    """Compare engagement and participation metrics across multiple sessions."""
    comparisons = []

    for session_id in session_ids:
        session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
        if not session:
            continue

        posts = db.query(Post).filter(Post.session_id == session_id).all()
        unique_participants = len(set(p.user_id for p in posts))
        polls = db.query(Poll).filter(Poll.session_id == session_id).count()

        # Get enrolled count
        enrolled = db.query(Enrollment).filter(Enrollment.course_id == session.course_id).count()

        participation_rate = (unique_participants / enrolled * 100) if enrolled > 0 else 0

        comparisons.append({
            "session_id": session_id,
            "title": session.title,
            "date": session.created_at.isoformat(),
            "status": session.status.value if hasattr(session.status, "value") else session.status,
            "total_posts": len(posts),
            "unique_participants": unique_participants,
            "participation_rate": round(participation_rate, 1),
            "polls_count": polls,
            "avg_posts_per_student": round(len(posts) / unique_participants, 1) if unique_participants > 0 else 0,
        })

    # Calculate averages
    if comparisons:
        avg_posts = sum(c["total_posts"] for c in comparisons) / len(comparisons)
        avg_participation = sum(c["participation_rate"] for c in comparisons) / len(comparisons)
    else:
        avg_posts = 0
        avg_participation = 0

    return {
        "sessions_compared": len(comparisons),
        "average_posts": round(avg_posts, 1),
        "average_participation_rate": round(avg_participation, 1),
        "sessions": comparisons,
    }


def get_course_analytics(db: Session, course_id: int) -> Dict[str, Any]:
    """Get comprehensive analytics for a course."""
    sessions = db.query(SessionModel).filter(SessionModel.course_id == course_id).all()
    session_ids = [s.id for s in sessions]

    if not session_ids:
        return {"course_id": course_id, "message": "No sessions found"}

    comparison = compare_sessions(db, session_ids)

    # Identify best and worst performing sessions
    if comparison["sessions"]:
        sorted_by_participation = sorted(comparison["sessions"], key=lambda x: x["participation_rate"], reverse=True)
        best_session = sorted_by_participation[0] if sorted_by_participation else None
        worst_session = sorted_by_participation[-1] if sorted_by_participation else None
    else:
        best_session = None
        worst_session = None

    return {
        "course_id": course_id,
        "total_sessions": len(sessions),
        "completed_sessions": len([s for s in sessions if s.status == SessionStatus.completed]),
        "overall_stats": {
            "average_posts_per_session": comparison["average_posts"],
            "average_participation_rate": comparison["average_participation_rate"],
        },
        "best_performing_session": best_session,
        "needs_improvement_session": worst_session,
        "session_details": comparison["sessions"],
    }


# =============================================================================
# 10. VOICE-CONTROLLED TIMER & PACING
# =============================================================================

def start_timer(db: Session, session_id: int, duration_seconds: int, label: str = "Discussion") -> Dict[str, Any]:
    """Start a countdown timer for a discussion segment."""
    timer = SessionTimer(
        session_id=session_id,
        label=label,
        duration_seconds=duration_seconds,
        started_at=datetime.utcnow(),
        is_active=True,
    )
    db.add(timer)
    db.commit()
    db.refresh(timer)

    return {
        "timer_id": timer.id,
        "label": timer.label,
        "duration_seconds": timer.duration_seconds,
        "started_at": timer.started_at.isoformat(),
    }


def get_timer_status(db: Session, session_id: int) -> Dict[str, Any]:
    """Get current timer status for a session."""
    timer = db.query(SessionTimer).filter(
        SessionTimer.session_id == session_id,
        SessionTimer.is_active == True
    ).order_by(SessionTimer.created_at.desc()).first()

    if not timer:
        return {"session_id": session_id, "active_timer": None}

    now = datetime.utcnow()
    if timer.started_at and not timer.paused_at:
        elapsed = (now - timer.started_at).total_seconds() + timer.elapsed_seconds
        remaining = max(0, timer.duration_seconds - elapsed)
    elif timer.paused_at:
        remaining = max(0, timer.duration_seconds - timer.elapsed_seconds)
    else:
        remaining = timer.duration_seconds

    return {
        "session_id": session_id,
        "active_timer": {
            "id": timer.id,
            "label": timer.label,
            "duration_seconds": timer.duration_seconds,
            "remaining_seconds": int(remaining),
            "is_paused": timer.paused_at is not None,
            "is_expired": remaining <= 0,
        }
    }


def pause_timer(db: Session, timer_id: int) -> Dict[str, Any]:
    """Pause an active timer."""
    timer = db.query(SessionTimer).filter(SessionTimer.id == timer_id).first()
    if not timer:
        return {"error": "Timer not found"}

    if timer.paused_at:
        return {"error": "Timer is already paused"}

    now = datetime.utcnow()
    elapsed = (now - timer.started_at).total_seconds() if timer.started_at else 0
    timer.elapsed_seconds = int(elapsed)
    timer.paused_at = now

    db.commit()

    return {"timer_id": timer_id, "status": "paused", "elapsed_seconds": timer.elapsed_seconds}


def resume_timer(db: Session, timer_id: int) -> Dict[str, Any]:
    """Resume a paused timer."""
    timer = db.query(SessionTimer).filter(SessionTimer.id == timer_id).first()
    if not timer:
        return {"error": "Timer not found"}

    if not timer.paused_at:
        return {"error": "Timer is not paused"}

    timer.started_at = datetime.utcnow()
    timer.paused_at = None

    db.commit()

    return {"timer_id": timer_id, "status": "resumed"}


def stop_timer(db: Session, timer_id: int) -> Dict[str, Any]:
    """Stop and deactivate a timer."""
    timer = db.query(SessionTimer).filter(SessionTimer.id == timer_id).first()
    if not timer:
        return {"error": "Timer not found"}

    timer.is_active = False
    db.commit()

    return {"timer_id": timer_id, "status": "stopped"}


# =============================================================================
# 11. QUICK STUDENT LOOKUP
# =============================================================================

def lookup_student(db: Session, user_id: int, session_id: int = None) -> Dict[str, Any]:
    """Get comprehensive student information for quick lookup."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {"error": "Student not found"}

    # Get overall stats
    total_posts = db.query(Post).filter(Post.user_id == user_id).count()

    # Get enrollments
    enrollments = db.query(Enrollment).filter(Enrollment.user_id == user_id).all()
    enrolled_courses = []
    for e in enrollments:
        from api.models.course import Course
        course = db.query(Course).filter(Course.id == e.course_id).first()
        if course:
            enrolled_courses.append({"id": course.id, "title": course.title})

    result = {
        "user_id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role.value if hasattr(user.role, "value") else user.role,
        "total_posts": total_posts,
        "enrolled_courses": enrolled_courses,
    }

    # If session_id provided, get session-specific stats
    if session_id:
        session_posts = db.query(Post).filter(
            Post.user_id == user_id,
            Post.session_id == session_id
        ).order_by(Post.created_at.desc()).all()

        result["session_stats"] = {
            "session_id": session_id,
            "post_count": len(session_posts),
            "recent_posts": [
                {
                    "id": p.id,
                    "content": p.content[:100] + "..." if len(p.content) > 100 else p.content,
                    "created_at": p.created_at.isoformat(),
                }
                for p in session_posts[:5]
            ],
        }

    return result


def search_students(db: Session, query: str, course_id: int = None) -> Dict[str, Any]:
    """Search for students by name or email."""
    search_pattern = f"%{query}%"

    base_query = db.query(User).filter(
        User.role == "student",
        (User.name.ilike(search_pattern) | User.email.ilike(search_pattern))
    )

    if course_id:
        base_query = base_query.join(Enrollment).filter(Enrollment.course_id == course_id)

    students = base_query.limit(10).all()

    return {
        "query": query,
        "results": [
            {"user_id": s.id, "name": s.name, "email": s.email}
            for s in students
        ],
    }


# =============================================================================
# 12. AI TEACHING ASSISTANT FOR Q&A
# =============================================================================

def generate_ai_response_draft(db: Session, post_id: int, session_id: int) -> Dict[str, Any]:
    """
    Generate an AI draft response for a student's question.
    In production, this would call an LLM to generate the response.
    """
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        return {"error": "Post not found"}

    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        return {"error": "Session not found"}

    # In production, call LLM here with context from:
    # - The question (post.content)
    # - Session plan (session.plan_json)
    # - Course materials
    # - Previous posts in the thread

    # For now, create a placeholder draft
    draft_content = f"[AI Draft Response to: '{post.content[:50]}...']\n\nThis is where the AI-generated response would appear. The response would be based on the session's learning objectives and course materials."

    draft = AIResponseDraft(
        post_id=post_id,
        session_id=session_id,
        draft_content=draft_content,
        confidence_score=0.85,
        status="pending",
    )
    db.add(draft)
    db.commit()
    db.refresh(draft)

    return {
        "draft_id": draft.id,
        "post_id": post_id,
        "draft_content": draft.draft_content,
        "confidence_score": draft.confidence_score,
        "status": draft.status,
    }


def get_pending_ai_drafts(db: Session, session_id: int) -> Dict[str, Any]:
    """Get all pending AI response drafts for instructor review."""
    drafts = db.query(AIResponseDraft).filter(
        AIResponseDraft.session_id == session_id,
        AIResponseDraft.status == "pending"
    ).order_by(AIResponseDraft.created_at.desc()).all()

    result = []
    for draft in drafts:
        post = db.query(Post).filter(Post.id == draft.post_id).first()
        user = db.query(User).filter(User.id == post.user_id).first() if post else None

        result.append({
            "draft_id": draft.id,
            "post_id": draft.post_id,
            "student_name": user.name if user else "Unknown",
            "question": post.content[:150] if post else "",
            "draft_response": draft.draft_content,
            "confidence": draft.confidence_score,
            "created_at": draft.created_at.isoformat(),
        })

    return {
        "session_id": session_id,
        "pending_count": len(result),
        "drafts": result,
    }


def approve_ai_draft(db: Session, draft_id: int, instructor_id: int, edited_content: str = None) -> Dict[str, Any]:
    """Approve an AI draft (optionally with edits) and post as a reply."""
    draft = db.query(AIResponseDraft).filter(AIResponseDraft.id == draft_id).first()
    if not draft:
        return {"error": "Draft not found"}

    # Use edited content if provided, otherwise use original draft
    final_content = edited_content if edited_content else draft.draft_content

    # Create the reply post
    reply = Post(
        session_id=draft.session_id,
        user_id=instructor_id,
        content=final_content,
        parent_post_id=draft.post_id,
    )
    db.add(reply)

    # Update draft status
    draft.status = "approved" if not edited_content else "edited"
    draft.instructor_edits = edited_content
    draft.reviewed_at = datetime.utcnow()
    draft.reviewed_by = instructor_id

    db.commit()
    db.refresh(reply)

    return {
        "draft_id": draft_id,
        "reply_id": reply.id,
        "status": draft.status,
        "posted_content": final_content[:100] + "..." if len(final_content) > 100 else final_content,
    }


def reject_ai_draft(db: Session, draft_id: int, instructor_id: int) -> Dict[str, Any]:
    """Reject an AI draft."""
    draft = db.query(AIResponseDraft).filter(AIResponseDraft.id == draft_id).first()
    if not draft:
        return {"error": "Draft not found"}

    draft.status = "rejected"
    draft.reviewed_at = datetime.utcnow()
    draft.reviewed_by = instructor_id

    db.commit()

    return {"draft_id": draft_id, "status": "rejected"}


def edit_ai_draft(db: Session, draft_id: int, edited_content: str) -> Dict[str, Any]:
    """Edit an AI draft content without approving/rejecting it."""
    draft = db.query(AIResponseDraft).filter(AIResponseDraft.id == draft_id).first()
    if not draft:
        return {"error": "Draft not found"}

    draft.draft_content = edited_content
    draft.instructor_edits = edited_content
    draft.status = "edited"

    db.commit()

    return {
        "draft_id": draft_id,
        "status": "edited",
        "edited_content": edited_content,
    }
