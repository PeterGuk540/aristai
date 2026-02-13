"""Models for LMS integration persistence and sync tracking."""

from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    Boolean,
    Text,
    UniqueConstraint,
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from api.core.database import Base


class IntegrationConnection(Base):
    __tablename__ = "integration_connections"
    __table_args__ = (
        UniqueConstraint("provider", "user_id", name="uq_integration_connection_provider_user"),
    )

    id = Column(Integer, primary_key=True, index=True)
    provider = Column(String(50), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(30), nullable=False, default="active")  # active|revoked|error
    provider_user_id = Column(String(255), nullable=True)
    provider_user_name = Column(String(255), nullable=True)
    metadata_json = Column(Text, nullable=True)
    last_checked_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User")


class IntegrationCourseMapping(Base):
    __tablename__ = "integration_course_mappings"
    __table_args__ = (
        UniqueConstraint("provider", "external_course_id", "target_course_id", name="uq_integration_course_mapping"),
    )

    id = Column(Integer, primary_key=True, index=True)
    provider = Column(String(50), nullable=False, index=True)
    external_course_id = Column(String(255), nullable=False, index=True)
    external_course_name = Column(String(500), nullable=True)
    target_course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    target_course = relationship("Course")
    creator = relationship("User")


class IntegrationSyncJob(Base):
    __tablename__ = "integration_sync_jobs"

    id = Column(Integer, primary_key=True, index=True)
    provider = Column(String(50), nullable=False, index=True)
    source_course_external_id = Column(String(255), nullable=False, index=True)
    target_course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    target_session_id = Column(Integer, ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True, index=True)
    triggered_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    status = Column(String(30), nullable=False, default="queued")  # queued|running|completed|failed
    requested_count = Column(Integer, nullable=False, default=0)
    imported_count = Column(Integer, nullable=False, default=0)
    skipped_count = Column(Integer, nullable=False, default=0)
    failed_count = Column(Integer, nullable=False, default=0)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    target_course = relationship("Course")
    target_session = relationship("Session")
    trigger_user = relationship("User")


class IntegrationSyncItem(Base):
    __tablename__ = "integration_sync_items"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("integration_sync_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    external_material_id = Column(String(255), nullable=False, index=True)
    external_material_name = Column(String(500), nullable=True)
    status = Column(String(30), nullable=False, default="queued")  # imported|skipped|failed
    message = Column(Text, nullable=True)
    course_material_id = Column(Integer, ForeignKey("course_materials.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    job = relationship("IntegrationSyncJob")
    course_material = relationship("CourseMaterial")


class IntegrationMaterialLink(Base):
    __tablename__ = "integration_material_links"
    __table_args__ = (
        UniqueConstraint(
            "provider", "external_material_id", "target_course_id", "target_session_id",
            name="uq_integration_material_link_provider_external_target"
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    provider = Column(String(50), nullable=False, index=True)
    external_material_id = Column(String(255), nullable=False, index=True)
    external_course_id = Column(String(255), nullable=False, index=True)
    target_course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    target_session_id = Column(Integer, ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True, index=True)
    course_material_id = Column(Integer, ForeignKey("course_materials.id", ondelete="CASCADE"), nullable=False, index=True)
    checksum_sha256 = Column(String(64), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    target_course = relationship("Course")
    target_session = relationship("Session")
    course_material = relationship("CourseMaterial")
