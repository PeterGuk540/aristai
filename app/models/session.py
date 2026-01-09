from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.core.database import Base


class SessionStatus(str, enum.Enum):
    draft = "draft"
    scheduled = "scheduled"
    live = "live"
    completed = "completed"


class Session(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(255), nullable=False)
    date = Column(DateTime(timezone=True), nullable=True)
    status = Column(SAEnum(SessionStatus, name="session_status"), default=SessionStatus.draft)
    plan_version = Column(String(50), nullable=True)
    plan_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Metadata for LLM tracking
    model_name = Column(String(100), nullable=True)
    prompt_version = Column(String(50), nullable=True)

    # Relationships with cascades
    course = relationship("Course", back_populates="sessions")
    cases = relationship("Case", back_populates="session", cascade="all, delete-orphan")
    posts = relationship("Post", back_populates="session", cascade="all, delete-orphan")
    polls = relationship("Poll", back_populates="session", cascade="all, delete-orphan")
    interventions = relationship("Intervention", back_populates="session", cascade="all, delete-orphan")
    reports = relationship("Report", back_populates="session", cascade="all, delete-orphan")


class Case(Base):
    __tablename__ = "cases"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    prompt = Column(Text, nullable=False)
    attachments = Column(JSON, nullable=True)  # List of file paths or URLs
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    session = relationship("Session", back_populates="cases")
