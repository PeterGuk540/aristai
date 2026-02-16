"""
Enhanced AI Features Models

This module contains models for the 10 enhanced AI features:
1. Smart Discussion Summarization
2. AI-Powered Student Grouping
3. Personalized Follow-up Generator
4. Question Bank Builder
5. Attendance & Participation Insights
6. AI Teaching Assistant Mode
7. Session Recording & Transcript Analysis
8. Learning Objective Alignment Dashboard
9. Peer Review Workflow
10. Multi-Language Support
"""

from sqlalchemy import (
    Column, Integer, String, DateTime, ForeignKey, JSON, Float, Text,
    Boolean, Enum as SQLEnum
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from api.core.database import Base
import enum


# ============ Feature 1: Smart Discussion Summarization ============

class LiveSummary(Base):
    """Real-time rolling summaries during live sessions."""
    __tablename__ = "live_summaries"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)

    # Summary content
    summary_text = Column(Text, nullable=False)
    key_themes = Column(JSON, nullable=True)  # List of emerging themes
    unanswered_questions = Column(JSON, nullable=True)  # Questions needing attention
    misconceptions = Column(JSON, nullable=True)  # Detected misconceptions
    engagement_pulse = Column(String(20), nullable=True)  # high/medium/low

    # Tracking
    posts_analyzed = Column(Integer, nullable=True)
    last_post_id = Column(Integer, nullable=True)  # For incremental updates

    # LLM metrics
    model_name = Column(String(100), nullable=True)
    total_tokens = Column(Integer, nullable=True)
    estimated_cost_usd = Column(Float, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    session = relationship("Session")


# ============ Feature 2: AI-Powered Student Grouping ============

class StudentGroup(Base):
    """AI-suggested student groups for breakout activities."""
    __tablename__ = "student_groups"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)

    name = Column(String(100), nullable=False)
    group_type = Column(String(50), nullable=False)  # debate, mixed_participation, learning_gap, jigsaw
    topic = Column(String(500), nullable=True)  # Assigned topic for jigsaw
    rationale = Column(Text, nullable=True)  # Why these students were grouped

    # Group configuration
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    session = relationship("Session")
    members = relationship("StudentGroupMember", back_populates="group", cascade="all, delete-orphan")


class StudentGroupMember(Base):
    """Members of a student group."""
    __tablename__ = "student_group_members"

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("student_groups.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    role = Column(String(50), nullable=True)  # facilitator, note_taker, presenter, etc.

    group = relationship("StudentGroup", back_populates="members")
    user = relationship("User")


# ============ Feature 3: Personalized Follow-up Generator ============

class PersonalizedFollowup(Base):
    """AI-generated personalized feedback for students."""
    __tablename__ = "personalized_followups"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Feedback content
    strengths = Column(JSON, nullable=True)  # What they did well
    improvements = Column(JSON, nullable=True)  # Areas to improve
    key_takeaways = Column(JSON, nullable=True)  # Personalized takeaways
    suggested_resources = Column(JSON, nullable=True)  # Recommended readings/videos
    custom_message = Column(Text, nullable=True)  # Full personalized message

    # Delivery status
    status = Column(String(30), default="draft")  # draft, approved, sent
    sent_at = Column(DateTime(timezone=True), nullable=True)
    sent_via = Column(String(30), nullable=True)  # email, canvas, in_app

    # LLM metrics
    model_name = Column(String(100), nullable=True)
    total_tokens = Column(Integer, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    session = relationship("Session")
    user = relationship("User")


# ============ Feature 4: Question Bank Builder ============

class QuestionBankItem(Base):
    """AI-generated questions from discussion content."""
    __tablename__ = "question_bank_items"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True, index=True)

    # Question content
    question_type = Column(String(30), nullable=False)  # mcq, short_answer, essay, true_false
    question_text = Column(Text, nullable=False)
    options = Column(JSON, nullable=True)  # For MCQ: list of options
    correct_answer = Column(Text, nullable=True)  # For MCQ/short_answer
    explanation = Column(Text, nullable=True)  # Why this is correct
    rubric = Column(JSON, nullable=True)  # For essay grading

    # Metadata
    difficulty = Column(String(20), nullable=True)  # easy, medium, hard
    learning_objective = Column(String(500), nullable=True)
    tags = Column(JSON, nullable=True)  # List of topic tags
    source_post_ids = Column(JSON, nullable=True)  # Posts that inspired this question

    # Usage tracking
    times_used = Column(Integer, default=0)
    avg_score = Column(Float, nullable=True)

    # Status
    status = Column(String(30), default="draft")  # draft, approved, archived
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    course = relationship("Course")
    session = relationship("Session")


# ============ Feature 5: Attendance & Participation Insights ============

class ParticipationSnapshot(Base):
    """Periodic snapshots of student participation metrics."""
    __tablename__ = "participation_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Metrics
    post_count = Column(Integer, default=0)
    reply_count = Column(Integer, default=0)
    quality_score = Column(Float, nullable=True)  # AI-assessed quality
    engagement_level = Column(String(20), nullable=True)  # highly_active, active, idle, disengaged
    time_active_minutes = Column(Integer, nullable=True)

    # Risk indicators
    at_risk = Column(Boolean, default=False)
    risk_factors = Column(JSON, nullable=True)  # List of concern factors

    snapshot_date = Column(DateTime(timezone=True), server_default=func.now())

    course = relationship("Course")
    session = relationship("Session")
    user = relationship("User")


class ParticipationAlert(Base):
    """Alerts for at-risk students or participation issues."""
    __tablename__ = "participation_alerts"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    alert_type = Column(String(50), nullable=False)  # low_participation, declining_trend, absence_streak
    severity = Column(String(20), nullable=False)  # info, warning, critical
    message = Column(Text, nullable=False)

    # Action taken
    acknowledged = Column(Boolean, default=False)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    action_taken = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    course = relationship("Course")
    user = relationship("User")


# ============ Feature 6: AI Teaching Assistant Mode ============

class AIAssistantMessage(Base):
    """Messages from AI Teaching Assistant to students."""
    __tablename__ = "ai_assistant_messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # The student's question
    student_question = Column(Text, nullable=False)
    student_post_id = Column(Integer, ForeignKey("posts.id", ondelete="SET NULL"), nullable=True)

    # AI response
    ai_response = Column(Text, nullable=False)
    confidence_score = Column(Float, nullable=True)  # How confident AI is in response
    sources_used = Column(JSON, nullable=True)  # Course materials referenced

    # Approval workflow
    status = Column(String(30), default="pending")  # pending, approved, rejected, auto_approved
    reviewed_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    instructor_edits = Column(Text, nullable=True)  # If instructor modified response

    # If posted to forum
    response_post_id = Column(Integer, ForeignKey("posts.id", ondelete="SET NULL"), nullable=True)

    # LLM metrics
    model_name = Column(String(100), nullable=True)
    total_tokens = Column(Integer, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    session = relationship("Session")
    student = relationship("User", foreign_keys=[student_id])
    reviewer = relationship("User", foreign_keys=[reviewed_by])


# ============ Feature 7: Session Recording & Transcript Analysis ============

class SessionRecording(Base):
    """Session audio/video recordings and transcripts."""
    __tablename__ = "session_recordings"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)

    # Recording info
    recording_type = Column(String(20), nullable=False)  # audio, video
    file_url = Column(String(1000), nullable=True)  # S3 URL
    duration_seconds = Column(Integer, nullable=True)

    # Transcript
    transcript_text = Column(Text, nullable=True)
    transcript_segments = Column(JSON, nullable=True)  # Timestamped segments

    # Analysis
    key_moments = Column(JSON, nullable=True)  # Important timestamps
    topics_discussed = Column(JSON, nullable=True)
    speaker_segments = Column(JSON, nullable=True)  # Who spoke when

    # Processing status
    status = Column(String(30), default="uploaded")  # uploaded, transcribing, analyzing, completed, failed
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    processed_at = Column(DateTime(timezone=True), nullable=True)

    session = relationship("Session")


class TranscriptPostLink(Base):
    """Links between transcript moments and forum posts."""
    __tablename__ = "transcript_post_links"

    id = Column(Integer, primary_key=True, index=True)
    recording_id = Column(Integer, ForeignKey("session_recordings.id", ondelete="CASCADE"), nullable=False, index=True)
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True)

    # Timestamp in recording
    start_seconds = Column(Integer, nullable=False)
    end_seconds = Column(Integer, nullable=True)

    # Context
    transcript_snippet = Column(Text, nullable=True)
    relevance_score = Column(Float, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    recording = relationship("SessionRecording")
    post = relationship("Post")


# ============ Feature 8: Learning Objective Alignment Dashboard ============

class ObjectiveCoverage(Base):
    """Tracks how well learning objectives are covered across sessions."""
    __tablename__ = "objective_coverage"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True, index=True)

    objective_text = Column(Text, nullable=False)
    objective_index = Column(Integer, nullable=True)  # Position in course objectives

    # Coverage metrics
    coverage_level = Column(String(20), nullable=True)  # not_covered, partially, fully
    coverage_score = Column(Float, nullable=True)  # 0.0 to 1.0
    evidence_post_ids = Column(JSON, nullable=True)  # Posts that demonstrate coverage

    # AI analysis
    coverage_summary = Column(Text, nullable=True)
    gaps_identified = Column(JSON, nullable=True)

    analyzed_at = Column(DateTime(timezone=True), server_default=func.now())

    course = relationship("Course")
    session = relationship("Session")


# ============ Feature 9: Peer Review Workflow ============

class PeerReviewAssignment(Base):
    """Peer review assignments between students."""
    __tablename__ = "peer_review_assignments"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)

    # Submission being reviewed
    submission_post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True)
    author_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Reviewer
    reviewer_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Review status
    status = Column(String(30), default="assigned")  # assigned, in_progress, submitted, acknowledged
    due_at = Column(DateTime(timezone=True), nullable=True)
    submitted_at = Column(DateTime(timezone=True), nullable=True)

    # Matching rationale (AI)
    match_rationale = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    session = relationship("Session")
    submission = relationship("Post", foreign_keys=[submission_post_id])
    author = relationship("User", foreign_keys=[author_id])
    reviewer = relationship("User", foreign_keys=[reviewer_id])
    feedback = relationship("PeerReviewFeedback", back_populates="assignment", uselist=False)


class PeerReviewFeedback(Base):
    """Feedback given in peer reviews."""
    __tablename__ = "peer_review_feedback"

    id = Column(Integer, primary_key=True, index=True)
    assignment_id = Column(Integer, ForeignKey("peer_review_assignments.id", ondelete="CASCADE"), nullable=False, index=True)

    # Structured feedback
    overall_rating = Column(Integer, nullable=True)  # 1-5
    strengths = Column(JSON, nullable=True)
    areas_for_improvement = Column(JSON, nullable=True)
    specific_comments = Column(Text, nullable=True)

    # Rubric responses (if using rubric)
    rubric_responses = Column(JSON, nullable=True)

    # Quality assessment (AI)
    feedback_quality_score = Column(Float, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    assignment = relationship("PeerReviewAssignment", back_populates="feedback")


# ============ Feature 10: Multi-Language Support ============

class PostTranslation(Base):
    """Translations of posts for multi-language support."""
    __tablename__ = "post_translations"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True)

    # Language info
    source_language = Column(String(10), nullable=False)  # ISO code: en, es, zh, etc.
    target_language = Column(String(10), nullable=False)

    # Translation
    translated_content = Column(Text, nullable=False)

    # Quality
    confidence_score = Column(Float, nullable=True)
    is_verified = Column(Boolean, default=False)
    verified_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # LLM metrics
    model_name = Column(String(100), nullable=True)
    total_tokens = Column(Integer, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    post = relationship("Post")
    verifier = relationship("User")


class UserLanguagePreference(Base):
    """User's language preferences for translations."""
    __tablename__ = "user_language_preferences"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)

    preferred_language = Column(String(10), nullable=False, default="en")
    auto_translate = Column(Boolean, default=True)  # Auto-translate posts in other languages
    show_original = Column(Boolean, default=True)  # Show original alongside translation

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User")
