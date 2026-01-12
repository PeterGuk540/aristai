from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from api.core.database import Base


class Report(Base):
    __tablename__ = "reports"
    __table_args__ = (
        UniqueConstraint("session_id", "version", name="uq_report_session_version"),
    )

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    version = Column(String(50), nullable=False)
    report_md = Column(Text, nullable=True)
    report_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Metadata for LLM tracking
    model_name = Column(String(100), nullable=True)
    prompt_version = Column(String(50), nullable=True)

    # Relationships
    session = relationship("Session", back_populates="reports")
