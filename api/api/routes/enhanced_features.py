"""
Enhanced AI Features API Routes

This module provides endpoints for all 10 enhanced AI features.
"""

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import List, Optional, Any
from pydantic import BaseModel
from datetime import datetime, timedelta

from api.core.database import get_db
from api.models.session import Session as SessionModel
from api.models.course import Course
from api.models.post import Post
from api.models.user import User
from api.models.enrollment import Enrollment
from api.models.enhanced_features import (
    LiveSummary,
    StudentGroup, StudentGroupMember,
    PersonalizedFollowup,
    QuestionBankItem,
    ParticipationSnapshot, ParticipationAlert,
    AIAssistantMessage,
    SessionRecording, TranscriptPostLink,
    ObjectiveCoverage,
    PeerReviewAssignment, PeerReviewFeedback,
    PostTranslation, UserLanguagePreference,
)

router = APIRouter(prefix="/enhanced", tags=["enhanced-features"])


# ============ Pydantic Schemas ============

# Feature 1: Live Summary
class LiveSummaryResponse(BaseModel):
    id: int
    session_id: int
    summary_text: str
    key_themes: Optional[List[str]] = None
    unanswered_questions: Optional[List[str]] = None
    misconceptions: Optional[List[dict]] = None
    engagement_pulse: Optional[str] = None
    posts_analyzed: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


# Feature 2: Student Groups
class StudentGroupMemberResponse(BaseModel):
    user_id: int
    name: str
    role: Optional[str] = None


class StudentGroupResponse(BaseModel):
    id: int
    session_id: int
    name: str
    group_type: str
    topic: Optional[str] = None
    rationale: Optional[str] = None
    members: List[StudentGroupMemberResponse] = []
    created_at: datetime

    class Config:
        from_attributes = True


class CreateGroupsRequest(BaseModel):
    session_id: int
    group_type: str = "mixed_participation"  # debate, mixed_participation, learning_gap, jigsaw
    num_groups: int = 4
    topics: Optional[List[str]] = None  # For jigsaw mode


# Feature 3: Personalized Follow-up
class PersonalizedFollowupResponse(BaseModel):
    id: int
    session_id: int
    user_id: int
    user_name: Optional[str] = None
    strengths: Optional[List[str]] = None
    improvements: Optional[List[str]] = None
    key_takeaways: Optional[List[str]] = None
    suggested_resources: Optional[List[dict]] = None
    custom_message: Optional[str] = None
    status: str
    sent_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class GenerateFollowupsRequest(BaseModel):
    session_id: int
    student_ids: Optional[List[int]] = None  # If None, generate for all participants


class SendFollowupRequest(BaseModel):
    followup_id: int
    send_via: str = "canvas"  # canvas, email, in_app
    custom_message: Optional[str] = None


# Feature 4: Question Bank
class QuestionBankItemResponse(BaseModel):
    id: int
    course_id: int
    session_id: Optional[int] = None
    question_type: str
    question_text: str
    options: Optional[List[str]] = None
    correct_answer: Optional[str] = None
    explanation: Optional[str] = None
    difficulty: Optional[str] = None
    learning_objective: Optional[str] = None
    tags: Optional[List[str]] = None
    times_used: int = 0
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class GenerateQuestionsRequest(BaseModel):
    session_id: int
    question_types: List[str] = ["mcq", "short_answer"]  # mcq, short_answer, essay, true_false
    num_questions: int = 5
    difficulty: Optional[str] = None  # easy, medium, hard


class UpdateQuestionRequest(BaseModel):
    question_text: Optional[str] = None
    options: Optional[List[str]] = None
    correct_answer: Optional[str] = None
    explanation: Optional[str] = None
    difficulty: Optional[str] = None
    status: Optional[str] = None


# Feature 5: Participation Insights
class ParticipationSnapshotResponse(BaseModel):
    user_id: int
    user_name: str
    post_count: int
    reply_count: int
    quality_score: Optional[float] = None
    engagement_level: Optional[str] = None
    at_risk: bool = False
    risk_factors: Optional[List[str]] = None

    class Config:
        from_attributes = True


class ParticipationAlertResponse(BaseModel):
    id: int
    course_id: int
    user_id: Optional[int] = None
    user_name: Optional[str] = None
    alert_type: str
    severity: str
    message: str
    acknowledged: bool
    created_at: datetime

    class Config:
        from_attributes = True


class CourseParticipationSummary(BaseModel):
    course_id: int
    total_students: int
    active_students: int
    at_risk_students: int
    avg_posts_per_student: float
    participation_rate: float
    alerts: List[ParticipationAlertResponse] = []


# Feature 6: AI Teaching Assistant
class AIAssistantMessageResponse(BaseModel):
    id: int
    session_id: int
    student_id: int
    student_name: Optional[str] = None
    student_question: str
    ai_response: str
    confidence_score: Optional[float] = None
    status: str
    reviewed_by: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class AskAIAssistantRequest(BaseModel):
    session_id: int
    question: str
    post_id: Optional[int] = None


class ReviewAIResponseRequest(BaseModel):
    message_id: int
    action: str  # approve, reject, edit
    edited_response: Optional[str] = None


# Feature 7: Session Recording
class SessionRecordingResponse(BaseModel):
    id: int
    session_id: int
    recording_type: str
    file_url: Optional[str] = None
    duration_seconds: Optional[int] = None
    status: str
    key_moments: Optional[List[dict]] = None
    topics_discussed: Optional[List[str]] = None
    created_at: datetime

    class Config:
        from_attributes = True


class UploadRecordingRequest(BaseModel):
    session_id: int
    recording_type: str = "audio"
    file_url: str


# Feature 8: Learning Objective Coverage
class ObjectiveCoverageResponse(BaseModel):
    objective_text: str
    objective_index: Optional[int] = None
    coverage_level: Optional[str] = None
    coverage_score: Optional[float] = None
    coverage_summary: Optional[str] = None
    gaps_identified: Optional[List[str]] = None
    sessions_covered: List[int] = []

    class Config:
        from_attributes = True


class CourseCoverageReport(BaseModel):
    course_id: int
    total_objectives: int
    fully_covered: int
    partially_covered: int
    not_covered: int
    objectives: List[ObjectiveCoverageResponse] = []
    recommended_topics: List[str] = []


# Feature 9: Peer Review
class PeerReviewAssignmentResponse(BaseModel):
    id: int
    session_id: int
    submission_post_id: int
    author_name: str
    reviewer_name: str
    status: str
    due_at: Optional[datetime] = None
    submitted_at: Optional[datetime] = None
    feedback: Optional[dict] = None

    class Config:
        from_attributes = True


class CreatePeerReviewRequest(BaseModel):
    session_id: int
    submission_post_ids: Optional[List[int]] = None  # If None, use all top-level posts
    reviews_per_submission: int = 2


class SubmitPeerReviewRequest(BaseModel):
    assignment_id: int
    overall_rating: int
    strengths: List[str]
    areas_for_improvement: List[str]
    specific_comments: Optional[str] = None


# Feature 10: Multi-Language
class PostTranslationResponse(BaseModel):
    post_id: int
    source_language: str
    target_language: str
    original_content: str
    translated_content: str
    confidence_score: Optional[float] = None

    class Config:
        from_attributes = True


class TranslatePostRequest(BaseModel):
    post_id: int
    target_language: str


class UserLanguagePreferenceRequest(BaseModel):
    preferred_language: str
    auto_translate: bool = True
    show_original: bool = True


# ============ Feature 1: Smart Discussion Summarization ============

@router.get("/sessions/{session_id}/live-summary", response_model=LiveSummaryResponse)
def get_live_summary(session_id: int, db: Session = Depends(get_db)):
    """Get the latest live summary for a session."""
    summary = db.query(LiveSummary).filter(
        LiveSummary.session_id == session_id
    ).order_by(desc(LiveSummary.created_at)).first()

    if not summary:
        raise HTTPException(status_code=404, detail="No summary available yet")

    return summary


@router.post("/sessions/{session_id}/live-summary/generate")
def generate_live_summary(
    session_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Trigger generation of a new live summary."""
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Queue background task
    from worker.tasks import generate_live_summary_task
    task = generate_live_summary_task.delay(session_id)

    return {"message": "Summary generation started", "task_id": task.id}


@router.get("/sessions/{session_id}/live-summary/history", response_model=List[LiveSummaryResponse])
def get_summary_history(session_id: int, limit: int = 10, db: Session = Depends(get_db)):
    """Get history of live summaries for a session."""
    summaries = db.query(LiveSummary).filter(
        LiveSummary.session_id == session_id
    ).order_by(desc(LiveSummary.created_at)).limit(limit).all()

    return summaries


# ============ Feature 2: AI-Powered Student Grouping ============

@router.post("/sessions/{session_id}/groups/generate", response_model=List[StudentGroupResponse])
def generate_student_groups(
    session_id: int,
    request: CreateGroupsRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Generate AI-powered student groups."""
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Queue background task
    from worker.tasks import generate_student_groups_task
    task = generate_student_groups_task.delay(
        session_id=session_id,
        group_type=request.group_type,
        num_groups=request.num_groups,
        topics=request.topics
    )

    return {"message": "Group generation started", "task_id": task.id}


@router.get("/sessions/{session_id}/groups", response_model=List[StudentGroupResponse])
def get_student_groups(session_id: int, db: Session = Depends(get_db)):
    """Get all student groups for a session."""
    groups = db.query(StudentGroup).filter(
        StudentGroup.session_id == session_id,
        StudentGroup.is_active == True
    ).all()

    result = []
    for group in groups:
        members = []
        for member in group.members:
            user = db.query(User).filter(User.id == member.user_id).first()
            members.append({
                "user_id": member.user_id,
                "name": user.name if user else "Unknown",
                "role": member.role
            })
        result.append({
            "id": group.id,
            "session_id": group.session_id,
            "name": group.name,
            "group_type": group.group_type,
            "topic": group.topic,
            "rationale": group.rationale,
            "members": members,
            "created_at": group.created_at
        })

    return result


@router.delete("/groups/{group_id}")
def delete_student_group(group_id: int, db: Session = Depends(get_db)):
    """Delete a student group."""
    group = db.query(StudentGroup).filter(StudentGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    group.is_active = False
    db.commit()

    return {"message": "Group deleted"}


# ============ Feature 3: Personalized Follow-up Generator ============

@router.post("/sessions/{session_id}/followups/generate")
def generate_personalized_followups(
    session_id: int,
    request: GenerateFollowupsRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Generate personalized follow-up messages for students."""
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    from worker.tasks import generate_followups_task
    task = generate_followups_task.delay(
        session_id=session_id,
        student_ids=request.student_ids
    )

    return {"message": "Follow-up generation started", "task_id": task.id}


@router.get("/sessions/{session_id}/followups", response_model=List[PersonalizedFollowupResponse])
def get_session_followups(session_id: int, status: Optional[str] = None, db: Session = Depends(get_db)):
    """Get all follow-ups for a session."""
    query = db.query(PersonalizedFollowup).filter(PersonalizedFollowup.session_id == session_id)

    if status:
        query = query.filter(PersonalizedFollowup.status == status)

    followups = query.all()

    result = []
    for f in followups:
        user = db.query(User).filter(User.id == f.user_id).first()
        result.append({
            **f.__dict__,
            "user_name": user.name if user else "Unknown"
        })

    return result


@router.post("/followups/{followup_id}/send")
def send_followup(
    followup_id: int,
    request: SendFollowupRequest,
    db: Session = Depends(get_db)
):
    """Send a follow-up message to a student."""
    followup = db.query(PersonalizedFollowup).filter(PersonalizedFollowup.id == followup_id).first()
    if not followup:
        raise HTTPException(status_code=404, detail="Follow-up not found")

    if request.custom_message:
        followup.custom_message = request.custom_message

    # TODO: Implement actual sending via Canvas/email
    followup.status = "sent"
    followup.sent_at = datetime.utcnow()
    followup.sent_via = request.send_via
    db.commit()

    return {"message": f"Follow-up sent via {request.send_via}"}


@router.post("/followups/send-all")
def send_all_followups(
    session_id: int,
    send_via: str = "canvas",
    db: Session = Depends(get_db)
):
    """Send all approved follow-ups for a session."""
    followups = db.query(PersonalizedFollowup).filter(
        PersonalizedFollowup.session_id == session_id,
        PersonalizedFollowup.status == "approved"
    ).all()

    sent_count = 0
    for f in followups:
        f.status = "sent"
        f.sent_at = datetime.utcnow()
        f.sent_via = send_via
        sent_count += 1

    db.commit()

    return {"message": f"Sent {sent_count} follow-ups via {send_via}"}


# ============ Feature 4: Question Bank Builder ============

@router.post("/sessions/{session_id}/questions/generate")
def generate_questions(
    session_id: int,
    request: GenerateQuestionsRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Generate quiz questions from session discussion."""
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    from worker.tasks import generate_questions_task
    task = generate_questions_task.delay(
        session_id=session_id,
        question_types=request.question_types,
        num_questions=request.num_questions,
        difficulty=request.difficulty
    )

    return {"message": "Question generation started", "task_id": task.id}


@router.get("/courses/{course_id}/question-bank", response_model=List[QuestionBankItemResponse])
def get_question_bank(
    course_id: int,
    session_id: Optional[int] = None,
    question_type: Optional[str] = None,
    difficulty: Optional[str] = None,
    status: str = "approved",
    db: Session = Depends(get_db)
):
    """Get questions from the question bank."""
    query = db.query(QuestionBankItem).filter(QuestionBankItem.course_id == course_id)

    if session_id:
        query = query.filter(QuestionBankItem.session_id == session_id)
    if question_type:
        query = query.filter(QuestionBankItem.question_type == question_type)
    if difficulty:
        query = query.filter(QuestionBankItem.difficulty == difficulty)
    if status:
        query = query.filter(QuestionBankItem.status == status)

    return query.all()


@router.put("/questions/{question_id}", response_model=QuestionBankItemResponse)
def update_question(
    question_id: int,
    request: UpdateQuestionRequest,
    db: Session = Depends(get_db)
):
    """Update a question in the question bank."""
    question = db.query(QuestionBankItem).filter(QuestionBankItem.id == question_id).first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    update_data = request.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(question, field, value)

    db.commit()
    db.refresh(question)

    return question


@router.delete("/questions/{question_id}")
def delete_question(question_id: int, db: Session = Depends(get_db)):
    """Delete a question from the question bank."""
    question = db.query(QuestionBankItem).filter(QuestionBankItem.id == question_id).first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    db.delete(question)
    db.commit()

    return {"message": "Question deleted"}


# ============ Feature 5: Attendance & Participation Insights ============

@router.get("/courses/{course_id}/participation", response_model=CourseParticipationSummary)
def get_course_participation(course_id: int, db: Session = Depends(get_db)):
    """Get participation summary for a course."""
    # Count enrolled students
    total_students = db.query(Enrollment).filter(Enrollment.course_id == course_id).count()

    # Get recent snapshots
    snapshots = db.query(ParticipationSnapshot).filter(
        ParticipationSnapshot.course_id == course_id
    ).order_by(desc(ParticipationSnapshot.snapshot_date)).limit(total_students).all()

    active_students = sum(1 for s in snapshots if s.engagement_level in ['highly_active', 'active'])
    at_risk_students = sum(1 for s in snapshots if s.at_risk)
    avg_posts = sum(s.post_count for s in snapshots) / len(snapshots) if snapshots else 0

    # Get unacknowledged alerts
    alerts = db.query(ParticipationAlert).filter(
        ParticipationAlert.course_id == course_id,
        ParticipationAlert.acknowledged == False
    ).order_by(desc(ParticipationAlert.created_at)).limit(10).all()

    alert_responses = []
    for a in alerts:
        user = db.query(User).filter(User.id == a.user_id).first() if a.user_id else None
        alert_responses.append({
            **a.__dict__,
            "user_name": user.name if user else None
        })

    return {
        "course_id": course_id,
        "total_students": total_students,
        "active_students": active_students,
        "at_risk_students": at_risk_students,
        "avg_posts_per_student": avg_posts,
        "participation_rate": (active_students / total_students * 100) if total_students > 0 else 0,
        "alerts": alert_responses
    }


@router.get("/sessions/{session_id}/participation", response_model=List[ParticipationSnapshotResponse])
def get_session_participation(session_id: int, db: Session = Depends(get_db)):
    """Get participation data for a specific session."""
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    snapshots = db.query(ParticipationSnapshot).filter(
        ParticipationSnapshot.session_id == session_id
    ).all()

    result = []
    for s in snapshots:
        user = db.query(User).filter(User.id == s.user_id).first()
        result.append({
            "user_id": s.user_id,
            "user_name": user.name if user else "Unknown",
            "post_count": s.post_count,
            "reply_count": s.reply_count,
            "quality_score": s.quality_score,
            "engagement_level": s.engagement_level,
            "at_risk": s.at_risk,
            "risk_factors": s.risk_factors
        })

    return result


@router.post("/alerts/{alert_id}/acknowledge")
def acknowledge_alert(alert_id: int, action_taken: Optional[str] = None, db: Session = Depends(get_db)):
    """Acknowledge a participation alert."""
    alert = db.query(ParticipationAlert).filter(ParticipationAlert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    alert.acknowledged = True
    alert.acknowledged_at = datetime.utcnow()
    if action_taken:
        alert.action_taken = action_taken

    db.commit()

    return {"message": "Alert acknowledged"}


@router.post("/courses/{course_id}/participation/analyze")
def analyze_participation(
    course_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Trigger participation analysis for a course."""
    from worker.tasks import analyze_participation_task
    task = analyze_participation_task.delay(course_id)

    return {"message": "Participation analysis started", "task_id": task.id}


# ============ Feature 6: AI Teaching Assistant Mode ============

@router.post("/sessions/{session_id}/ai-assistant/ask", response_model=AIAssistantMessageResponse)
def ask_ai_assistant(
    session_id: int,
    request: AskAIAssistantRequest,
    user_id: int,
    db: Session = Depends(get_db)
):
    """Ask the AI teaching assistant a question."""
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Queue background task for AI response
    from worker.tasks import generate_ai_assistant_response_task
    task = generate_ai_assistant_response_task.delay(
        session_id=session_id,
        student_id=user_id,
        question=request.question,
        post_id=request.post_id
    )

    return {"message": "AI assistant is thinking...", "task_id": task.id}


@router.get("/sessions/{session_id}/ai-assistant/messages", response_model=List[AIAssistantMessageResponse])
def get_ai_assistant_messages(
    session_id: int,
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get AI assistant messages for a session."""
    query = db.query(AIAssistantMessage).filter(AIAssistantMessage.session_id == session_id)

    if status:
        query = query.filter(AIAssistantMessage.status == status)

    messages = query.order_by(desc(AIAssistantMessage.created_at)).all()

    result = []
    for m in messages:
        student = db.query(User).filter(User.id == m.student_id).first()
        result.append({
            **m.__dict__,
            "student_name": student.name if student else "Unknown"
        })

    return result


@router.post("/ai-assistant/messages/{message_id}/review")
def review_ai_response(
    message_id: int,
    request: ReviewAIResponseRequest,
    user_id: int,
    db: Session = Depends(get_db)
):
    """Review and approve/reject an AI assistant response."""
    message = db.query(AIAssistantMessage).filter(AIAssistantMessage.id == message_id).first()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    message.reviewed_by = user_id
    message.reviewed_at = datetime.utcnow()

    if request.action == "approve":
        message.status = "approved"
        # TODO: Post the response to the forum
    elif request.action == "reject":
        message.status = "rejected"
    elif request.action == "edit":
        message.status = "approved"
        message.instructor_edits = request.edited_response
        message.ai_response = request.edited_response

    db.commit()

    return {"message": f"Response {request.action}d"}


# ============ Feature 7: Session Recording & Transcript Analysis ============

@router.post("/sessions/{session_id}/recordings", response_model=SessionRecordingResponse)
def upload_session_recording(
    session_id: int,
    request: UploadRecordingRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Upload a session recording for transcription and analysis."""
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    recording = SessionRecording(
        session_id=session_id,
        recording_type=request.recording_type,
        file_url=request.file_url,
        status="uploaded"
    )
    db.add(recording)
    db.commit()
    db.refresh(recording)

    # Queue transcription task
    from worker.tasks import transcribe_recording_task
    transcribe_recording_task.delay(recording.id)

    return recording


@router.get("/sessions/{session_id}/recordings", response_model=List[SessionRecordingResponse])
def get_session_recordings(session_id: int, db: Session = Depends(get_db)):
    """Get all recordings for a session."""
    return db.query(SessionRecording).filter(SessionRecording.session_id == session_id).all()


@router.get("/recordings/{recording_id}/transcript")
def get_recording_transcript(recording_id: int, db: Session = Depends(get_db)):
    """Get the transcript for a recording."""
    recording = db.query(SessionRecording).filter(SessionRecording.id == recording_id).first()
    if not recording:
        raise HTTPException(status_code=404, detail="Recording not found")

    if recording.status != "completed":
        return {"status": recording.status, "message": "Transcript not ready yet"}

    return {
        "transcript_text": recording.transcript_text,
        "transcript_segments": recording.transcript_segments,
        "key_moments": recording.key_moments,
        "topics_discussed": recording.topics_discussed
    }


@router.get("/recordings/{recording_id}/post-links")
def get_transcript_post_links(recording_id: int, db: Session = Depends(get_db)):
    """Get links between transcript moments and forum posts."""
    links = db.query(TranscriptPostLink).filter(TranscriptPostLink.recording_id == recording_id).all()

    result = []
    for link in links:
        post = db.query(Post).filter(Post.id == link.post_id).first()
        result.append({
            "post_id": link.post_id,
            "post_content": post.content[:200] if post else None,
            "start_seconds": link.start_seconds,
            "end_seconds": link.end_seconds,
            "transcript_snippet": link.transcript_snippet,
            "relevance_score": link.relevance_score
        })

    return result


# ============ Feature 8: Learning Objective Alignment Dashboard ============

@router.get("/courses/{course_id}/objective-coverage", response_model=CourseCoverageReport)
def get_objective_coverage(course_id: int, db: Session = Depends(get_db)):
    """Get learning objective coverage report for a course."""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    coverage_records = db.query(ObjectiveCoverage).filter(
        ObjectiveCoverage.course_id == course_id
    ).order_by(ObjectiveCoverage.objective_index).all()

    # Group by objective
    objectives_map = {}
    for record in coverage_records:
        key = record.objective_text
        if key not in objectives_map:
            objectives_map[key] = {
                "objective_text": record.objective_text,
                "objective_index": record.objective_index,
                "coverage_level": record.coverage_level,
                "coverage_score": record.coverage_score,
                "coverage_summary": record.coverage_summary,
                "gaps_identified": record.gaps_identified,
                "sessions_covered": []
            }
        if record.session_id:
            objectives_map[key]["sessions_covered"].append(record.session_id)

    objectives = list(objectives_map.values())
    fully_covered = sum(1 for o in objectives if o["coverage_level"] == "fully")
    partially_covered = sum(1 for o in objectives if o["coverage_level"] == "partially")
    not_covered = sum(1 for o in objectives if o["coverage_level"] == "not_covered")

    return {
        "course_id": course_id,
        "total_objectives": len(objectives),
        "fully_covered": fully_covered,
        "partially_covered": partially_covered,
        "not_covered": not_covered,
        "objectives": objectives,
        "recommended_topics": []  # TODO: Generate recommendations
    }


@router.post("/courses/{course_id}/objective-coverage/analyze")
def analyze_objective_coverage(
    course_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Trigger analysis of learning objective coverage."""
    from worker.tasks import analyze_objective_coverage_task
    task = analyze_objective_coverage_task.delay(course_id)

    return {"message": "Coverage analysis started", "task_id": task.id}


# ============ Feature 9: Peer Review Workflow ============

@router.post("/sessions/{session_id}/peer-reviews/create")
def create_peer_reviews(
    session_id: int,
    request: CreatePeerReviewRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Create peer review assignments for a session."""
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    from worker.tasks import create_peer_review_assignments_task
    task = create_peer_review_assignments_task.delay(
        session_id=session_id,
        submission_post_ids=request.submission_post_ids,
        reviews_per_submission=request.reviews_per_submission
    )

    return {"message": "Peer review assignments being created", "task_id": task.id}


@router.get("/sessions/{session_id}/peer-reviews", response_model=List[PeerReviewAssignmentResponse])
def get_peer_reviews(session_id: int, db: Session = Depends(get_db)):
    """Get all peer review assignments for a session."""
    assignments = db.query(PeerReviewAssignment).filter(
        PeerReviewAssignment.session_id == session_id
    ).all()

    result = []
    for a in assignments:
        author = db.query(User).filter(User.id == a.author_id).first()
        reviewer = db.query(User).filter(User.id == a.reviewer_id).first()
        feedback = db.query(PeerReviewFeedback).filter(
            PeerReviewFeedback.assignment_id == a.id
        ).first()

        result.append({
            "id": a.id,
            "session_id": a.session_id,
            "submission_post_id": a.submission_post_id,
            "author_name": author.name if author else "Unknown",
            "reviewer_name": reviewer.name if reviewer else "Unknown",
            "status": a.status,
            "due_at": a.due_at,
            "submitted_at": a.submitted_at,
            "feedback": feedback.__dict__ if feedback else None
        })

    return result


@router.get("/users/{user_id}/peer-reviews/assigned")
def get_user_assigned_reviews(user_id: int, db: Session = Depends(get_db)):
    """Get peer reviews assigned to a user."""
    assignments = db.query(PeerReviewAssignment).filter(
        PeerReviewAssignment.reviewer_id == user_id,
        PeerReviewAssignment.status.in_(["assigned", "in_progress"])
    ).all()

    result = []
    for a in assignments:
        author = db.query(User).filter(User.id == a.author_id).first()
        post = db.query(Post).filter(Post.id == a.submission_post_id).first()

        result.append({
            "id": a.id,
            "author_name": author.name if author else "Unknown",
            "submission_content": post.content[:500] if post else None,
            "due_at": a.due_at,
            "status": a.status
        })

    return result


@router.post("/peer-reviews/{assignment_id}/submit")
def submit_peer_review(
    assignment_id: int,
    request: SubmitPeerReviewRequest,
    db: Session = Depends(get_db)
):
    """Submit peer review feedback."""
    assignment = db.query(PeerReviewAssignment).filter(
        PeerReviewAssignment.id == assignment_id
    ).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    feedback = PeerReviewFeedback(
        assignment_id=assignment_id,
        overall_rating=request.overall_rating,
        strengths=request.strengths,
        areas_for_improvement=request.areas_for_improvement,
        specific_comments=request.specific_comments
    )
    db.add(feedback)

    assignment.status = "submitted"
    assignment.submitted_at = datetime.utcnow()

    db.commit()

    return {"message": "Peer review submitted"}


# ============ Feature 10: Multi-Language Support ============

@router.post("/posts/{post_id}/translate", response_model=PostTranslationResponse)
def translate_post(
    post_id: int,
    request: TranslatePostRequest,
    db: Session = Depends(get_db)
):
    """Translate a post to a target language."""
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    # Check for existing translation
    existing = db.query(PostTranslation).filter(
        PostTranslation.post_id == post_id,
        PostTranslation.target_language == request.target_language
    ).first()

    if existing:
        return {
            "post_id": post_id,
            "source_language": existing.source_language,
            "target_language": existing.target_language,
            "original_content": post.content,
            "translated_content": existing.translated_content,
            "confidence_score": existing.confidence_score
        }

    # Queue translation task
    from worker.tasks import translate_post_task
    task = translate_post_task.delay(post_id, request.target_language)

    return {"message": "Translation in progress", "task_id": task.id}


@router.get("/posts/{post_id}/translations")
def get_post_translations(post_id: int, db: Session = Depends(get_db)):
    """Get all translations for a post."""
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    translations = db.query(PostTranslation).filter(PostTranslation.post_id == post_id).all()

    return {
        "post_id": post_id,
        "original_content": post.content,
        "translations": [
            {
                "target_language": t.target_language,
                "translated_content": t.translated_content,
                "confidence_score": t.confidence_score
            }
            for t in translations
        ]
    }


@router.get("/users/{user_id}/language-preference")
def get_language_preference(user_id: int, db: Session = Depends(get_db)):
    """Get a user's language preferences."""
    pref = db.query(UserLanguagePreference).filter(
        UserLanguagePreference.user_id == user_id
    ).first()

    if not pref:
        return {
            "preferred_language": "en",
            "auto_translate": True,
            "show_original": True
        }

    return {
        "preferred_language": pref.preferred_language,
        "auto_translate": pref.auto_translate,
        "show_original": pref.show_original
    }


@router.put("/users/{user_id}/language-preference")
def update_language_preference(
    user_id: int,
    request: UserLanguagePreferenceRequest,
    db: Session = Depends(get_db)
):
    """Update a user's language preferences."""
    pref = db.query(UserLanguagePreference).filter(
        UserLanguagePreference.user_id == user_id
    ).first()

    if not pref:
        pref = UserLanguagePreference(user_id=user_id)
        db.add(pref)

    pref.preferred_language = request.preferred_language
    pref.auto_translate = request.auto_translate
    pref.show_original = request.show_original

    db.commit()

    return {"message": "Language preference updated"}


@router.post("/sessions/{session_id}/translate-all")
def translate_all_posts(
    session_id: int,
    target_language: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Translate all posts in a session to a target language."""
    from worker.tasks import translate_session_posts_task
    task = translate_session_posts_task.delay(session_id, target_language)

    return {"message": f"Translating all posts to {target_language}", "task_id": task.id}
