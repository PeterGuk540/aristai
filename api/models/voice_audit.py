"""Voice audit log model for tracking voice assistant interactions."""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON
from sqlalchemy.sql import func
from api.core.database import Base


class VoiceAudit(Base):
    __tablename__ = "voice_audits"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    transcript_hash = Column(String(64), nullable=False)  # SHA-256 hex
    plan_json = Column(JSON, nullable=False)
    tool_calls = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
