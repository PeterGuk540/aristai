from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON, Float, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from api.core.database import Base


class Intervention(Base):
    __tablename__ = "interventions"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    intervention_type = Column(String(50), nullable=False)  # prompt, clarification_flag, activity, poll_suggestion
    suggestion_json = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Metadata for LLM tracking
    model_name = Column(String(100), nullable=True)
    prompt_version = Column(String(50), nullable=True)
    evidence_post_ids = Column(JSON, nullable=True)  # List of post IDs that triggered this

    # Observability fields (Milestone 6)
    execution_time_seconds = Column(Float, nullable=True)
    total_tokens = Column(Integer, nullable=True)
    prompt_tokens = Column(Integer, nullable=True)
    completion_tokens = Column(Integer, nullable=True)
    estimated_cost_usd = Column(Float, nullable=True)
    error_message = Column(Text, nullable=True)
    used_fallback = Column(Integer, default=0)  # 0=LLM used, 1=fallback used
    posts_analyzed = Column(Integer, nullable=True)

    # Relationships
    session = relationship("Session", back_populates="interventions")
