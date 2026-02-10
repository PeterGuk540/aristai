"""
API Routes for Instructor Enhancement Features.

Provides REST endpoints for:
1. Real-Time Engagement Heatmap
2. Smart Discussion Facilitation
3. Quick Polls from Context
4. Session Templates & Cloning
5. Student Progress Tracking
6. Breakout Groups
7. Pre-Class Insights
8. Post-Class Follow-ups
9. Comparative Analytics
10. Timer & Pacing
11. Quick Student Lookup
12. AI Teaching Assistant
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional
from sqlalchemy.orm import Session

from api.core.database import get_db
from api.services import instructor_features as features

router = APIRouter(prefix="/instructor", tags=["instructor-features"])


# =============================================================================
# Request/Response Models
# =============================================================================

class BreakoutGroupRequest(BaseModel):
    session_id: int
    num_groups: int = Field(ge=2, le=20)
    assignment: str = "random"  # "random" or "balanced"


class TimerRequest(BaseModel):
    session_id: int
    duration_seconds: int = Field(ge=30, le=3600)  # 30 sec to 1 hour
    label: str = "Discussion"


class TemplateRequest(BaseModel):
    session_id: int
    template_name: str
    user_id: int
    description: Optional[str] = None
    category: Optional[str] = None


class CreateFromTemplateRequest(BaseModel):
    template_id: int
    course_id: int
    title: str


class CloneSessionRequest(BaseModel):
    session_id: int
    new_title: str
    course_id: Optional[int] = None


class CheckpointRequest(BaseModel):
    session_id: int
    title: str
    description: Optional[str] = None
    checkpoint_type: str = "reading"


class QuickPollRequest(BaseModel):
    session_id: int
    question: str
    options: List[str] = Field(min_length=2, max_length=6)


class AIResponseApprovalRequest(BaseModel):
    draft_id: int
    instructor_id: int
    edited_content: Optional[str] = None


class StudentSearchRequest(BaseModel):
    query: str
    course_id: Optional[int] = None


class CompareSessionsRequest(BaseModel):
    session_ids: List[int] = Field(min_length=2, max_length=10)


# =============================================================================
# 1. ENGAGEMENT HEATMAP ENDPOINTS
# =============================================================================

@router.get("/engagement/heatmap/{session_id}")
async def get_engagement_heatmap(session_id: int, db: Session = Depends(get_db)):
    """Get real-time engagement heatmap for a session."""
    result = features.get_engagement_heatmap(db, session_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.get("/engagement/needs-attention/{session_id}")
async def get_students_needing_attention(session_id: int, db: Session = Depends(get_db)):
    """Get list of students who need attention (idle/disengaged)."""
    result = features.get_disengaged_students(db, session_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.post("/engagement/update")
async def update_engagement(
    session_id: int,
    user_id: int,
    activity_type: str = "post",
    db: Session = Depends(get_db)
):
    """Update student engagement when activity occurs."""
    return features.update_student_engagement(db, session_id, user_id, activity_type)


# =============================================================================
# 2. SMART FACILITATION ENDPOINTS
# =============================================================================

@router.get("/facilitation/suggestions/{session_id}")
async def get_facilitation_suggestions(session_id: int, db: Session = Depends(get_db)):
    """Get smart facilitation suggestions for a session."""
    result = features.get_facilitation_suggestions(db, session_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.get("/facilitation/next-student/{session_id}")
async def suggest_next_student(session_id: int, db: Session = Depends(get_db)):
    """Suggest which student to call on next."""
    result = features.suggest_next_student(db, session_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


# =============================================================================
# 3. QUICK POLLS ENDPOINTS
# =============================================================================

@router.get("/polls/suggestions/{session_id}")
async def get_poll_suggestions(session_id: int, db: Session = Depends(get_db)):
    """Get AI-suggested polls based on discussion context."""
    result = features.suggest_poll_from_discussion(db, session_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.post("/polls/quick-create")
async def create_quick_poll(request: QuickPollRequest, db: Session = Depends(get_db)):
    """Quickly create a poll from a suggestion."""
    result = features.create_quick_poll(db, request.session_id, request.question, request.options)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


# =============================================================================
# 4. SESSION TEMPLATES ENDPOINTS
# =============================================================================

@router.get("/templates")
async def list_templates(
    user_id: Optional[int] = None,
    category: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """List available session templates."""
    return features.list_templates(db, user_id, category)


@router.post("/templates/save")
async def save_as_template(request: TemplateRequest, db: Session = Depends(get_db)):
    """Save a session as a reusable template."""
    result = features.save_session_as_template(
        db, request.session_id, request.template_name,
        request.user_id, request.description, request.category
    )
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/templates/create-session")
async def create_from_template(request: CreateFromTemplateRequest, db: Session = Depends(get_db)):
    """Create a new session from a template."""
    result = features.create_session_from_template(
        db, request.template_id, request.course_id, request.title
    )
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/sessions/clone")
async def clone_session(request: CloneSessionRequest, db: Session = Depends(get_db)):
    """Clone an existing session."""
    result = features.clone_session(db, request.session_id, request.new_title, request.course_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


# =============================================================================
# 5. STUDENT PROGRESS ENDPOINTS
# =============================================================================

@router.get("/progress/student/{user_id}")
async def get_student_progress(
    user_id: int,
    course_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Get longitudinal progress for a student."""
    result = features.get_student_progress(db, user_id, course_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.get("/progress/class/{course_id}")
async def get_class_progress(course_id: int, db: Session = Depends(get_db)):
    """Get progress summary for all students in a course."""
    return features.get_class_progress_summary(db, course_id)


# =============================================================================
# 6. BREAKOUT GROUPS ENDPOINTS
# =============================================================================

@router.post("/breakout/create")
async def create_breakout_groups(request: BreakoutGroupRequest, db: Session = Depends(get_db)):
    """Create breakout groups for a session."""
    result = features.create_breakout_groups(
        db, request.session_id, request.num_groups, request.assignment
    )
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.get("/breakout/{session_id}")
async def get_breakout_groups(session_id: int, db: Session = Depends(get_db)):
    """Get breakout groups for a session."""
    return features.get_breakout_groups(db, session_id)


@router.delete("/breakout/{session_id}")
async def dissolve_breakout_groups(session_id: int, db: Session = Depends(get_db)):
    """Dissolve all breakout groups for a session."""
    return features.dissolve_breakout_groups(db, session_id)


# =============================================================================
# 7. PRE-CLASS INSIGHTS ENDPOINTS
# =============================================================================

@router.post("/preclass/checkpoint")
async def create_checkpoint(request: CheckpointRequest, db: Session = Depends(get_db)):
    """Create a pre-class preparation checkpoint."""
    return features.create_preclass_checkpoint(
        db, request.session_id, request.title, request.description, request.checkpoint_type
    )


@router.get("/preclass/status/{session_id}")
async def get_preclass_status(session_id: int, db: Session = Depends(get_db)):
    """Get pre-class completion status for a session."""
    result = features.get_preclass_completion_status(db, session_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


# =============================================================================
# 8. POST-CLASS FOLLOW-UP ENDPOINTS
# =============================================================================

@router.get("/postclass/summary/{session_id}")
async def get_session_summary(session_id: int, db: Session = Depends(get_db)):
    """Generate session summary for follow-up email."""
    result = features.generate_session_summary_email(db, session_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.get("/postclass/unresolved/{session_id}")
async def get_unresolved_topics(session_id: int, db: Session = Depends(get_db)):
    """Get unresolved topics that need follow-up."""
    result = features.get_unresolved_topics(db, session_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


# =============================================================================
# 9. COMPARATIVE ANALYTICS ENDPOINTS
# =============================================================================

@router.post("/analytics/compare")
async def compare_sessions(request: CompareSessionsRequest, db: Session = Depends(get_db)):
    """Compare metrics across multiple sessions."""
    return features.compare_sessions(db, request.session_ids)


@router.get("/analytics/course/{course_id}")
async def get_course_analytics(course_id: int, db: Session = Depends(get_db)):
    """Get comprehensive analytics for a course."""
    return features.get_course_analytics(db, course_id)


# =============================================================================
# 10. TIMER ENDPOINTS
# =============================================================================

@router.post("/timer/start")
async def start_timer(request: TimerRequest, db: Session = Depends(get_db)):
    """Start a discussion timer."""
    return features.start_timer(db, request.session_id, request.duration_seconds, request.label)


@router.get("/timer/status/{session_id}")
async def get_timer_status(session_id: int, db: Session = Depends(get_db)):
    """Get current timer status for a session."""
    return features.get_timer_status(db, session_id)


@router.post("/timer/{timer_id}/pause")
async def pause_timer(timer_id: int, db: Session = Depends(get_db)):
    """Pause an active timer."""
    result = features.pause_timer(db, timer_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/timer/{timer_id}/resume")
async def resume_timer(timer_id: int, db: Session = Depends(get_db)):
    """Resume a paused timer."""
    result = features.resume_timer(db, timer_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/timer/{timer_id}/stop")
async def stop_timer(timer_id: int, db: Session = Depends(get_db)):
    """Stop a timer."""
    return features.stop_timer(db, timer_id)


# =============================================================================
# 11. STUDENT LOOKUP ENDPOINTS
# =============================================================================

@router.get("/student/{user_id}")
async def lookup_student(
    user_id: int,
    session_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Quick lookup of student information."""
    result = features.lookup_student(db, user_id, session_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.post("/student/search")
async def search_students(request: StudentSearchRequest, db: Session = Depends(get_db)):
    """Search for students by name or email."""
    return features.search_students(db, request.query, request.course_id)


# =============================================================================
# 12. AI TEACHING ASSISTANT ENDPOINTS
# =============================================================================

@router.post("/ai/generate-draft/{post_id}")
async def generate_ai_draft(
    post_id: int,
    session_id: int,
    db: Session = Depends(get_db)
):
    """Generate an AI draft response for a student question."""
    result = features.generate_ai_response_draft(db, post_id, session_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.get("/ai/pending-drafts/{session_id}")
async def get_pending_drafts(session_id: int, db: Session = Depends(get_db)):
    """Get all pending AI drafts for instructor review."""
    return features.get_pending_ai_drafts(db, session_id)


@router.post("/ai/approve")
async def approve_ai_draft(request: AIResponseApprovalRequest, db: Session = Depends(get_db)):
    """Approve an AI draft and post as reply."""
    result = features.approve_ai_draft(
        db, request.draft_id, request.instructor_id, request.edited_content
    )
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/ai/reject/{draft_id}")
async def reject_ai_draft(draft_id: int, instructor_id: int, db: Session = Depends(get_db)):
    """Reject an AI draft."""
    result = features.reject_ai_draft(db, draft_id, instructor_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


class AIEditRequest(BaseModel):
    edited_content: str


@router.put("/ai/edit/{draft_id}")
async def edit_ai_draft(draft_id: int, request: AIEditRequest, db: Session = Depends(get_db)):
    """Edit an AI draft content."""
    result = features.edit_ai_draft(db, draft_id, request.edited_content)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result
