"""
Voice Command Handlers for Instructor Features.

This module provides voice command processing for the new instructor enhancement features:
1. Engagement Heatmap
2. Smart Facilitation
3. Quick Polls
4. Session Templates
5. Student Progress
6. Breakout Groups
7. Pre-Class Insights
8. Post-Class Follow-ups
9. Comparative Analytics
10. Timer Control
11. Student Lookup
12. AI Teaching Assistant
"""
import re
import logging
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from api.services import instructor_features as features
from api.services.speech_filter import sanitize_speech

logger = logging.getLogger(__name__)


def handle_instructor_feature(
    action: str,
    user_id: Optional[int],
    session_id: Optional[int],
    course_id: Optional[int],
    transcript: str,
    db: Session,
    llm_params: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Handle voice commands for instructor enhancement features.

    Returns None if the action is not an instructor feature command.
    Returns a dict with 'message' and optional 'ui_actions' if handled.
    """
    llm_params = llm_params or {}

    # =========================================================================
    # ENGAGEMENT HEATMAP
    # =========================================================================
    if action == 'get_engagement_heatmap':
        if not session_id:
            return {"message": sanitize_speech("Please select a live session first to view engagement.")}

        result = features.get_engagement_heatmap(db, session_id)
        if "error" in result:
            return {"message": sanitize_speech(result["error"])}

        summary = result.get("engagement_summary", {})
        total = result.get("total_students", 0)

        highly_active = summary.get("highly_active", 0)
        active = summary.get("active", 0)
        idle = summary.get("idle", 0)
        disengaged = summary.get("disengaged", 0)

        message = f"Engagement overview: {highly_active + active} students are active, {idle} are idle, and {disengaged} appear disengaged out of {total} total."

        return {
            "message": sanitize_speech(message),
            "data": result,
            "ui_actions": [
                {"type": "ui.showEngagementHeatmap", "payload": result}
            ]
        }

    if action == 'get_disengaged_students':
        if not session_id:
            return {"message": sanitize_speech("Please select a live session first.")}

        result = features.get_disengaged_students(db, session_id)
        if "error" in result:
            return {"message": sanitize_speech(result["error"])}

        count = result.get("needs_attention_count", 0)
        students = result.get("students", [])

        if count == 0:
            message = "Great news! All students are actively participating."
        else:
            names = [s["name"] for s in students[:3]]
            names_str = ", ".join(names)
            more = f" and {count - 3} more" if count > 3 else ""
            message = f"{count} students need attention: {names_str}{more}."

        return {
            "message": sanitize_speech(message),
            "data": result,
        }

    # =========================================================================
    # SMART FACILITATION
    # =========================================================================
    if action == 'get_facilitation_suggestions':
        if not session_id:
            return {"message": sanitize_speech("Please select a live session first.")}

        result = features.get_facilitation_suggestions(db, session_id)
        if "error" in result:
            return {"message": sanitize_speech(result["error"])}

        suggestions = result.get("suggestions", [])
        momentum = result.get("discussion_momentum", "unknown")

        if not suggestions:
            message = f"Discussion is {momentum}. No specific suggestions at this time."
        else:
            top_suggestion = suggestions[0]
            message = f"Discussion is {momentum}. {top_suggestion.get('message', '')}"

        return {
            "message": sanitize_speech(message),
            "data": result,
        }

    if action == 'suggest_next_student':
        if not session_id:
            return {"message": sanitize_speech("Please select a live session first.")}

        result = features.suggest_next_student(db, session_id)
        if "error" in result:
            return {"message": sanitize_speech(result["error"])}

        if "suggested_student" in result:
            student = result["suggested_student"]
            message = f"I suggest calling on {student['name']}. {result.get('reason', '')}"
        else:
            message = result.get("message", "All students have good participation.")

        return {"message": sanitize_speech(message), "data": result}

    # =========================================================================
    # QUICK POLLS
    # =========================================================================
    if action == 'get_poll_suggestions':
        if not session_id:
            return {"message": sanitize_speech("Please select a live session first.")}

        result = features.suggest_poll_from_discussion(db, session_id)
        if "error" in result:
            return {"message": sanitize_speech(result["error"])}

        suggestions = result.get("suggestions", [])
        if not suggestions:
            message = "No poll suggestions available yet. More discussion is needed."
        else:
            first = suggestions[0]
            question = first.get("question", "")
            message = f"Based on the discussion, you could ask: {question}"

        return {
            "message": sanitize_speech(message),
            "data": result,
            "ui_actions": [
                {"type": "ui.showPollSuggestions", "payload": {"suggestions": suggestions}}
            ]
        }

    # =========================================================================
    # SESSION TEMPLATES
    # =========================================================================
    if action == 'list_templates':
        result = features.list_templates(db, user_id)
        templates = result.get("templates", [])

        if not templates:
            message = "You don't have any saved templates yet. You can save a session as a template after creating it."
        else:
            names = [t["name"] for t in templates[:3]]
            message = f"You have {len(templates)} templates. Top ones: {', '.join(names)}."

        return {"message": sanitize_speech(message), "data": result}

    if action == 'save_template':
        if not session_id:
            return {"message": sanitize_speech("Please select a session to save as a template.")}

        # Extract template name from transcript
        template_name = _extract_template_name(transcript) or f"Template from session"

        result = features.save_session_as_template(db, session_id, template_name, user_id)
        if "error" in result:
            return {"message": sanitize_speech(result["error"])}

        message = f"Session saved as template: {result.get('name', template_name)}."
        return {"message": sanitize_speech(message), "data": result}

    if action == 'clone_session':
        if not session_id:
            return {"message": sanitize_speech("Please select a session to clone.")}

        new_title = _extract_session_title(transcript) or "Cloned Session"

        result = features.clone_session(db, session_id, new_title, course_id)
        if "error" in result:
            return {"message": sanitize_speech(result["error"])}

        message = f"Session cloned. New session created: {result.get('title', new_title)}."
        return {
            "message": sanitize_speech(message),
            "data": result,
            "ui_actions": [
                {"type": "ui.toast", "payload": {"message": "Session cloned successfully", "type": "success"}}
            ]
        }

    # =========================================================================
    # STUDENT PROGRESS
    # =========================================================================
    if action == 'get_student_progress':
        # Extract student name from transcript or llm_params
        student_name = llm_params.get("student_name") or _extract_student_name(transcript)
        if not student_name:
            return {"message": sanitize_speech("Please specify which student you'd like to know about.")}

        # Look up student by name
        search_result = features.search_students(db, student_name, course_id)
        students = search_result.get("results", [])

        if not students:
            return {"message": sanitize_speech(f"I couldn't find a student named {student_name}.")}

        student_id = students[0]["user_id"]
        result = features.get_student_progress(db, student_id, course_id)

        if "error" in result:
            return {"message": sanitize_speech(result["error"])}

        name = result.get("user_name", student_name)
        total_posts = result.get("total_posts", 0)
        trend = result.get("participation_trend", "unknown")
        sessions = result.get("total_sessions", 0)

        message = f"{name} has participated in {sessions} sessions with {total_posts} total posts. Their trend is {trend}."

        return {"message": sanitize_speech(message), "data": result}

    if action == 'get_class_progress':
        if not course_id:
            return {"message": sanitize_speech("Please select a course first.")}

        result = features.get_class_progress_summary(db, course_id)
        if "error" in result:
            return {"message": sanitize_speech(result["error"])}

        students = result.get("students", [])
        total = result.get("total_students", 0)

        if not students:
            message = "No student progress data available yet."
        else:
            top_3 = [s["name"] for s in students[:3]]
            message = f"Class has {total} students. Top participants: {', '.join(top_3)}."

        return {"message": sanitize_speech(message), "data": result}

    # =========================================================================
    # BREAKOUT GROUPS
    # =========================================================================
    if action == 'create_breakout_groups':
        if not session_id:
            return {"message": sanitize_speech("Please select a live session first.")}

        # Extract number of groups from transcript
        num_groups = _extract_number(transcript) or 4

        result = features.create_breakout_groups(db, session_id, num_groups)
        if "error" in result:
            return {"message": sanitize_speech(result["error"])}

        message = f"Created {num_groups} breakout groups. Students have been randomly assigned."
        return {
            "message": sanitize_speech(message),
            "data": result,
            "ui_actions": [
                {"type": "ui.showBreakoutGroups", "payload": result},
                {"type": "ui.toast", "payload": {"message": f"{num_groups} groups created", "type": "success"}}
            ]
        }

    if action == 'get_breakout_groups':
        if not session_id:
            return {"message": sanitize_speech("Please select a session first.")}

        result = features.get_breakout_groups(db, session_id)
        groups = result.get("groups", [])

        if not groups:
            message = "No active breakout groups in this session."
        else:
            message = f"There are {len(groups)} active breakout groups."
            for g in groups[:3]:
                message += f" {g['name']} has {g['member_count']} members with {g['post_count']} posts."

        return {"message": sanitize_speech(message), "data": result}

    if action == 'dissolve_breakout_groups':
        if not session_id:
            return {"message": sanitize_speech("Please select a session first.")}

        result = features.dissolve_breakout_groups(db, session_id)
        message = result.get("message", "Breakout groups have been dissolved.")

        return {
            "message": sanitize_speech(message),
            "ui_actions": [
                {"type": "ui.toast", "payload": {"message": "Groups dissolved", "type": "info"}}
            ]
        }

    # =========================================================================
    # PRE-CLASS INSIGHTS
    # =========================================================================
    if action == 'get_preclass_status':
        if not session_id:
            return {"message": sanitize_speech("Please select a session first.")}

        result = features.get_preclass_completion_status(db, session_id)
        if "error" in result:
            return {"message": sanitize_speech(result["error"])}

        rate = result.get("overall_completion_rate", 0)
        checkpoints = result.get("checkpoints", [])

        if not checkpoints:
            message = "No pre-class checkpoints are set for this session."
        else:
            message = f"Overall pre-class completion rate is {rate:.0f}%."
            if rate < 70:
                incomplete = sum(c.get("incomplete_count", 0) for c in checkpoints)
                message += f" {incomplete} students haven't completed their preparation."

        return {"message": sanitize_speech(message), "data": result}

    # =========================================================================
    # POST-CLASS FOLLOW-UPS
    # =========================================================================
    if action == 'get_session_summary':
        if not session_id:
            return {"message": sanitize_speech("Please select a session first.")}

        result = features.generate_session_summary_email(db, session_id)
        if "error" in result:
            return {"message": sanitize_speech(result["error"])}

        email = result.get("email_content", {})
        stats = email.get("statistics", {})
        posts = stats.get("total_posts", 0)
        polls = stats.get("polls_conducted", 0)

        message = f"Session summary ready. {posts} posts and {polls} polls. Would you like me to send it to students?"

        return {
            "message": sanitize_speech(message),
            "data": result,
            "ui_actions": [
                {"type": "ui.showSessionSummary", "payload": email}
            ]
        }

    if action == 'get_unresolved_topics':
        if not session_id:
            return {"message": sanitize_speech("Please select a session first.")}

        result = features.get_unresolved_topics(db, session_id)
        if "error" in result:
            return {"message": sanitize_speech(result["error"])}

        count = result.get("unresolved_count", 0)
        topics = result.get("unresolved_topics", [])

        if count == 0:
            message = "Great! All questions from this session have been addressed."
        else:
            first_topic = topics[0]["content"][:50] if topics else ""
            message = f"There are {count} unresolved topics that need follow-up. First one: {first_topic}..."

        return {"message": sanitize_speech(message), "data": result}

    if action == 'send_session_summary':
        if not session_id:
            return {"message": sanitize_speech("Please select a session first.")}

        # In production, this would trigger an email send
        result = features.generate_session_summary_email(db, session_id)
        if "error" in result:
            return {"message": sanitize_speech(result["error"])}

        message = "Session summary has been prepared. Email sending would be triggered here."
        return {
            "message": sanitize_speech(message),
            "ui_actions": [
                {"type": "ui.toast", "payload": {"message": "Summary ready to send", "type": "success"}}
            ]
        }

    # =========================================================================
    # COMPARATIVE ANALYTICS
    # =========================================================================
    if action == 'compare_sessions':
        if not course_id:
            return {"message": sanitize_speech("Please select a course first.")}

        # Get recent sessions for comparison
        from api.models.session import Session as SessionModel
        sessions = db.query(SessionModel).filter(
            SessionModel.course_id == course_id
        ).order_by(SessionModel.created_at.desc()).limit(5).all()

        if len(sessions) < 2:
            return {"message": sanitize_speech("Need at least 2 sessions to compare.")}

        session_ids = [s.id for s in sessions]
        result = features.compare_sessions(db, session_ids)

        avg_posts = result.get("average_posts", 0)
        avg_participation = result.get("average_participation_rate", 0)

        message = f"Comparing {len(session_ids)} sessions. Average posts: {avg_posts:.0f}, average participation: {avg_participation:.0f}%."

        return {
            "message": sanitize_speech(message),
            "data": result,
            "ui_actions": [
                {"type": "ui.showSessionComparison", "payload": result}
            ]
        }

    if action == 'get_course_analytics':
        if not course_id:
            return {"message": sanitize_speech("Please select a course first.")}

        result = features.get_course_analytics(db, course_id)
        if "error" in result:
            return {"message": sanitize_speech(result["error"])}

        stats = result.get("overall_stats", {})
        total = result.get("total_sessions", 0)
        completed = result.get("completed_sessions", 0)

        message = f"Course has {total} sessions, {completed} completed. Average participation: {stats.get('average_participation_rate', 0):.0f}%."

        return {"message": sanitize_speech(message), "data": result}

    # =========================================================================
    # TIMER CONTROL
    # =========================================================================
    if action == 'start_timer':
        if not session_id:
            return {"message": sanitize_speech("Please select a session first.")}

        # Extract duration from transcript
        duration = _extract_duration(transcript) or 300  # Default 5 minutes

        label = _extract_timer_label(transcript) or "Discussion"

        result = features.start_timer(db, session_id, duration, label)

        minutes = duration // 60
        seconds = duration % 60
        time_str = f"{minutes} minute{'s' if minutes != 1 else ''}" if seconds == 0 else f"{minutes}:{seconds:02d}"

        message = f"Timer started: {time_str} for {label}."

        return {
            "message": sanitize_speech(message),
            "data": result,
            "ui_actions": [
                {"type": "ui.startTimer", "payload": result},
                {"type": "ui.toast", "payload": {"message": f"Timer: {time_str}", "type": "info"}}
            ]
        }

    if action == 'get_timer_status':
        if not session_id:
            return {"message": sanitize_speech("Please select a session first.")}

        result = features.get_timer_status(db, session_id)
        timer = result.get("active_timer")

        if not timer:
            message = "No active timer."
        else:
            remaining = timer.get("remaining_seconds", 0)
            minutes = remaining // 60
            seconds = remaining % 60

            if timer.get("is_expired"):
                message = "Timer has expired."
            elif timer.get("is_paused"):
                message = f"Timer is paused with {minutes}:{seconds:02d} remaining."
            else:
                message = f"{minutes}:{seconds:02d} remaining on the {timer.get('label', 'timer')}."

        return {"message": sanitize_speech(message), "data": result}

    if action == 'pause_timer':
        if not session_id:
            return {"message": sanitize_speech("Please select a session first.")}

        status = features.get_timer_status(db, session_id)
        timer = status.get("active_timer")

        if not timer:
            return {"message": sanitize_speech("No active timer to pause.")}

        result = features.pause_timer(db, timer["id"])
        if "error" in result:
            return {"message": sanitize_speech(result["error"])}

        return {
            "message": sanitize_speech("Timer paused."),
            "ui_actions": [
                {"type": "ui.pauseTimer", "payload": {"timer_id": timer["id"]}}
            ]
        }

    if action == 'resume_timer':
        if not session_id:
            return {"message": sanitize_speech("Please select a session first.")}

        status = features.get_timer_status(db, session_id)
        timer = status.get("active_timer")

        if not timer:
            return {"message": sanitize_speech("No timer to resume.")}

        result = features.resume_timer(db, timer["id"])
        if "error" in result:
            return {"message": sanitize_speech(result["error"])}

        return {
            "message": sanitize_speech("Timer resumed."),
            "ui_actions": [
                {"type": "ui.resumeTimer", "payload": {"timer_id": timer["id"]}}
            ]
        }

    if action == 'stop_timer':
        if not session_id:
            return {"message": sanitize_speech("Please select a session first.")}

        status = features.get_timer_status(db, session_id)
        timer = status.get("active_timer")

        if not timer:
            return {"message": sanitize_speech("No active timer.")}

        result = features.stop_timer(db, timer["id"])

        return {
            "message": sanitize_speech("Timer stopped."),
            "ui_actions": [
                {"type": "ui.stopTimer", "payload": {"timer_id": timer["id"]}}
            ]
        }

    # =========================================================================
    # STUDENT LOOKUP
    # =========================================================================
    if action == 'student_lookup':
        student_name = llm_params.get("student_name") or _extract_student_name(transcript)
        if not student_name:
            return {"message": sanitize_speech("Please specify which student you'd like to look up.")}

        # Search for student
        search_result = features.search_students(db, student_name, course_id)
        students = search_result.get("results", [])

        if not students:
            return {"message": sanitize_speech(f"I couldn't find a student named {student_name}.")}

        student_id = students[0]["user_id"]
        result = features.lookup_student(db, student_id, session_id)

        if "error" in result:
            return {"message": sanitize_speech(result["error"])}

        name = result.get("name", student_name)
        total_posts = result.get("total_posts", 0)

        message = f"{name} has made {total_posts} posts total."

        if "session_stats" in result:
            session_posts = result["session_stats"].get("post_count", 0)
            message += f" In this session: {session_posts} posts."

        return {
            "message": sanitize_speech(message),
            "data": result,
            "ui_actions": [
                {"type": "ui.showStudentCard", "payload": result}
            ]
        }

    # =========================================================================
    # AI TEACHING ASSISTANT
    # =========================================================================
    if action == 'get_ai_drafts':
        if not session_id:
            return {"message": sanitize_speech("Please select a session first.")}

        result = features.get_pending_ai_drafts(db, session_id)
        count = result.get("pending_count", 0)

        if count == 0:
            message = "No pending AI draft responses to review."
        else:
            message = f"You have {count} AI draft responses waiting for review."

        return {
            "message": sanitize_speech(message),
            "data": result,
            "ui_actions": [
                {"type": "ui.showAIDrafts", "payload": result}
            ]
        }

    if action == 'generate_ai_draft':
        if not session_id:
            return {"message": sanitize_speech("Please select a session first.")}

        # This would need the post_id - for now, generate for most recent question
        from api.models.post import Post
        recent_question = db.query(Post).filter(
            Post.session_id == session_id,
            Post.content.ilike('%?%')
        ).order_by(Post.created_at.desc()).first()

        if not recent_question:
            return {"message": sanitize_speech("No recent questions found to draft a response for.")}

        result = features.generate_ai_response_draft(db, recent_question.id, session_id)
        if "error" in result:
            return {"message": sanitize_speech(result["error"])}

        message = "AI has drafted a response for the most recent question. Would you like to review and approve it?"

        return {
            "message": sanitize_speech(message),
            "data": result,
            "ui_actions": [
                {"type": "ui.showAIDraft", "payload": result}
            ]
        }

    if action == 'approve_ai_draft':
        # This requires confirmation flow - handled by conversation state
        return {
            "message": sanitize_speech("Which draft would you like to approve?"),
            "requires_selection": True,
        }

    if action == 'reject_ai_draft':
        return {
            "message": sanitize_speech("Which draft would you like to reject?"),
            "requires_selection": True,
        }

    # Action not handled by instructor features
    return None


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _extract_template_name(transcript: str) -> Optional[str]:
    """Extract template name from transcript."""
    patterns = [
        r"(?:call it|name it|as)\s+['\"]?([^'\"]+)['\"]?",
        r"template\s+(?:called|named)\s+['\"]?([^'\"]+)['\"]?",
    ]
    for pattern in patterns:
        match = re.search(pattern, transcript.lower())
        if match:
            return match.group(1).strip()
    return None


def _extract_session_title(transcript: str) -> Optional[str]:
    """Extract session title from transcript."""
    patterns = [
        r"(?:call it|name it|title)\s+['\"]?([^'\"]+)['\"]?",
        r"(?:as|to)\s+['\"]?([^'\"]+)['\"]?$",
    ]
    for pattern in patterns:
        match = re.search(pattern, transcript.lower())
        if match:
            return match.group(1).strip().title()
    return None


def _extract_student_name(transcript: str) -> Optional[str]:
    """Extract student name from transcript."""
    patterns = [
        r"(?:about|for|on)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
        r"(?:how is|how's|hows)\s+([A-Z][a-z]+)",
        r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+(?:doing|participating|progress)",
    ]
    for pattern in patterns:
        match = re.search(pattern, transcript)
        if match:
            return match.group(1).strip()
    return None


def _extract_number(transcript: str) -> Optional[int]:
    """Extract a number from transcript."""
    # Word to number mapping
    word_numbers = {
        'two': 2, 'three': 3, 'four': 4, 'five': 5,
        'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
        'dos': 2, 'tres': 3, 'cuatro': 4, 'cinco': 5,
        'seis': 6, 'siete': 7, 'ocho': 8, 'nueve': 9, 'diez': 10,
    }

    transcript_lower = transcript.lower()

    # Check word numbers
    for word, num in word_numbers.items():
        if word in transcript_lower:
            return num

    # Check digit numbers
    match = re.search(r'\b(\d+)\b', transcript)
    if match:
        return int(match.group(1))

    return None


def _extract_duration(transcript: str) -> Optional[int]:
    """Extract duration in seconds from transcript."""
    transcript_lower = transcript.lower()

    # Match patterns like "5 minutes", "10 minute", "30 seconds"
    minute_patterns = [
        r'(\d+)\s*(?:minute|minutes|min|mins)',
        r'(\d+)\s*(?:minuto|minutos)',
    ]
    second_patterns = [
        r'(\d+)\s*(?:second|seconds|sec|secs)',
        r'(\d+)\s*(?:segundo|segundos)',
    ]

    total_seconds = 0

    for pattern in minute_patterns:
        match = re.search(pattern, transcript_lower)
        if match:
            total_seconds += int(match.group(1)) * 60

    for pattern in second_patterns:
        match = re.search(pattern, transcript_lower)
        if match:
            total_seconds += int(match.group(1))

    return total_seconds if total_seconds > 0 else None


def _extract_timer_label(transcript: str) -> Optional[str]:
    """Extract timer label from transcript."""
    patterns = [
        r"for\s+(?:the\s+)?([a-zA-Z]+(?:\s+[a-zA-Z]+)?)\s*$",
        r"(?:label|called|named)\s+['\"]?([^'\"]+)['\"]?",
    ]
    for pattern in patterns:
        match = re.search(pattern, transcript.lower())
        if match:
            label = match.group(1).strip()
            if label not in ['the', 'a', 'an', 'this']:
                return label.title()
    return None
