"""UI Action Run model for logging voice-triggered UI actions.

This table provides observability for the voice assistant's UI actions,
supporting the Skill Platform requirements for step-level logging.
"""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON, Boolean, Enum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum

from api.core.database import Base


class ActionRunStatus(str, enum.Enum):
    """Status of an action run."""
    PENDING = "pending"
    SUCCESS = "success"
    FAILURE = "failure"
    SKIPPED = "skipped"  # Idempotency dedup


class ActionRiskTier(str, enum.Enum):
    """Risk tier classification for UI actions."""
    LOW = "low"        # Navigation, tab switching
    MEDIUM = "medium"  # Form filling, button clicks
    HIGH = "high"      # Deletions, publishing, sending


class UIActionRun(Base):
    """Log entry for a UI action execution.

    Tracks each voice-triggered UI action for:
    - Observability and debugging
    - Audit trail for high-risk actions
    - Idempotency verification
    - Performance monitoring
    """
    __tablename__ = "ui_action_runs"

    id = Column(Integer, primary_key=True, index=True)

    # User context
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    voice_session_id = Column(String(64), nullable=True, index=True)  # ElevenLabs session ID

    # Action details
    action_id = Column(String(64), nullable=False, index=True)  # e.g., "NAV_COURSES", "SWITCH_TAB"
    action_args = Column(JSON, nullable=True)  # Arguments passed to the action
    risk_tier = Column(Enum(ActionRiskTier), nullable=True)

    # Execution context
    current_route = Column(String(256), nullable=True)  # Page where action was triggered
    transcript = Column(String(1024), nullable=True)  # User's voice command

    # Result
    status = Column(Enum(ActionRunStatus), nullable=False, default=ActionRunStatus.PENDING)
    result_ok = Column(Boolean, nullable=True)
    result_did = Column(String(256), nullable=True)  # What was done
    result_hint = Column(String(512), nullable=True)  # Hint for agent
    result_error = Column(String(512), nullable=True)  # Error message if failed

    # Timing
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    duration_ms = Column(Integer, nullable=True)  # Execution time in milliseconds

    # Idempotency
    idempotency_key = Column(String(128), nullable=True, index=True)  # Hash of action_id + args
    was_deduplicated = Column(Boolean, default=False)  # True if returned cached result

    # Relationships
    user = relationship("User", backref="ui_action_runs")

    def __repr__(self):
        return f"<UIActionRun(id={self.id}, action_id='{self.action_id}', status='{self.status}')>"
