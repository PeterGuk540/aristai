"""
Student Engagement Tracking Model.

Tracks real-time student activity for engagement heatmap visualization.
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Float, JSON, Text, Boolean
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from api.core.database import Base


class EngagementLevel(str, enum.Enum):
    highly_active = "highly_active"  # Posted in last 2 minutes
    active = "active"                # Posted in last 5 minutes
    idle = "idle"                    # No activity in 5-15 minutes
    disengaged = "disengaged"        # No activity in 15+ minutes
    not_joined = "not_joined"        # Never joined the session


class StudentEngagement(Base):
    """Track real-time student engagement in live sessions."""
    __tablename__ = "student_engagements"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Engagement metrics
    engagement_level = Column(SAEnum(EngagementLevel, name="engagement_level"), default=EngagementLevel.not_joined)
    last_activity_at = Column(DateTime(timezone=True), nullable=True)
    post_count = Column(Integer, default=0)
    reply_count = Column(Integer, default=0)
    poll_votes = Column(Integer, default=0)

    # Quality metrics
    avg_post_length = Column(Float, default=0.0)
    quality_posts = Column(Integer, default=0)  # Posts marked as high-quality

    # Session join tracking
    joined_at = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    session = relationship("Session", backref="student_engagements")
    user = relationship("User", backref="engagements")


class SessionTimer(Base):
    """Track discussion timers for pacing."""
    __tablename__ = "session_timers"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)

    label = Column(String(255), nullable=False)  # e.g., "Group Discussion", "Case Analysis"
    duration_seconds = Column(Integer, nullable=False)  # Total duration
    started_at = Column(DateTime(timezone=True), nullable=True)
    paused_at = Column(DateTime(timezone=True), nullable=True)
    elapsed_seconds = Column(Integer, default=0)  # Time elapsed when paused
    is_active = Column(Boolean, default=False)
    is_visible_to_students = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    session = relationship("Session", backref="timers")


class BreakoutGroup(Base):
    """Manage breakout groups within a session."""
    __tablename__ = "breakout_groups"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)

    name = Column(String(100), nullable=False)  # e.g., "Group 1", "Team Alpha"
    topic = Column(Text, nullable=True)  # Optional discussion topic for this group
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    session = relationship("Session", backref="breakout_groups")
    members = relationship("BreakoutGroupMember", back_populates="group", cascade="all, delete-orphan")


class BreakoutGroupMember(Base):
    """Track which students are in which breakout group."""
    __tablename__ = "breakout_group_members"

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("breakout_groups.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    joined_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    group = relationship("BreakoutGroup", back_populates="members")
    user = relationship("User", backref="breakout_memberships")


class SessionTemplate(Base):
    """Store reusable session templates."""
    __tablename__ = "session_templates"

    id = Column(Integer, primary_key=True, index=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(100), nullable=True)  # e.g., "Case Study", "Lecture", "Workshop"

    # Template content (mirrors session plan structure)
    plan_json = Column(JSON, nullable=True)
    duration_minutes = Column(Integer, nullable=True)

    # Usage tracking
    use_count = Column(Integer, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    creator = relationship("User", backref="session_templates")


class PreClassCheckpoint(Base):
    """Track pre-class preparation checkpoints."""
    __tablename__ = "preclass_checkpoints"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)

    title = Column(String(255), nullable=False)  # e.g., "Complete Chapter 5 Reading"
    description = Column(Text, nullable=True)
    checkpoint_type = Column(String(50), default="reading")  # reading, video, quiz, assignment
    due_before_session = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    session = relationship("Session", backref="preclass_checkpoints")
    completions = relationship("CheckpointCompletion", back_populates="checkpoint", cascade="all, delete-orphan")


class CheckpointCompletion(Base):
    """Track student completion of pre-class checkpoints."""
    __tablename__ = "checkpoint_completions"

    id = Column(Integer, primary_key=True, index=True)
    checkpoint_id = Column(Integer, ForeignKey("preclass_checkpoints.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    completed_at = Column(DateTime(timezone=True), server_default=func.now())
    score = Column(Float, nullable=True)  # Optional score for quiz-type checkpoints

    # Relationships
    checkpoint = relationship("PreClassCheckpoint", back_populates="completions")
    user = relationship("User", backref="checkpoint_completions")


class AIResponseDraft(Base):
    """Store AI-drafted responses for instructor review."""
    __tablename__ = "ai_response_drafts"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)

    draft_content = Column(Text, nullable=False)
    confidence_score = Column(Float, nullable=True)  # AI's confidence in the response

    status = Column(String(50), default="pending")  # pending, approved, rejected, edited
    instructor_edits = Column(Text, nullable=True)  # Instructor's modifications

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    reviewed_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # Relationships
    post = relationship("Post", backref="ai_drafts")
    session = relationship("Session", backref="ai_drafts")
    reviewer = relationship("User", backref="reviewed_ai_drafts")
