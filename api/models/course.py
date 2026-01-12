from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from api.core.database import Base


class Course(Base):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    syllabus_text = Column(Text, nullable=True)
    objectives_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships with cascades to avoid orphan rows
    resources = relationship("CourseResource", back_populates="course", cascade="all, delete-orphan")
    sessions = relationship("Session", back_populates="course", cascade="all, delete-orphan")


class CourseResource(Base):
    __tablename__ = "course_resources"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    resource_type = Column(String(50), nullable=False)  # e.g., "reading", "link", "file"
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=True)  # For text content or file path
    link = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    course = relationship("Course", back_populates="resources")
