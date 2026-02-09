"""Course Material model for S3-stored files."""

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, BigInteger
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from api.core.database import Base


class CourseMaterial(Base):
    """
    Represents an uploaded file/material for a course.
    Files are stored in S3, metadata is stored here.
    """
    __tablename__ = "course_materials"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True, index=True)

    # File metadata
    filename = Column(String(500), nullable=False)  # Original filename
    s3_key = Column(String(1000), nullable=False, unique=True)  # S3 object key
    file_size = Column(BigInteger, nullable=False)  # Size in bytes
    content_type = Column(String(255), nullable=False)  # MIME type

    # User-facing metadata
    title = Column(String(500), nullable=True)  # Optional display title
    description = Column(Text, nullable=True)  # Optional description

    # Upload tracking
    uploaded_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Version tracking (for replacements)
    version = Column(Integer, default=1)
    replaced_material_id = Column(Integer, ForeignKey("course_materials.id", ondelete="SET NULL"), nullable=True)

    # Relationships
    course = relationship("Course", back_populates="materials")
    session = relationship("Session", back_populates="materials")
    uploader = relationship("User", foreign_keys=[uploaded_by])
    replaced_by = relationship("CourseMaterial", remote_side=[id], foreign_keys=[replaced_material_id])
