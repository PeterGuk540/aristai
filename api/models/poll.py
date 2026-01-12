from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from api.core.database import Base


class Poll(Base):
    __tablename__ = "polls"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    question = Column(String(500), nullable=False)
    options_json = Column(JSON, nullable=False)  # List of option strings
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    session = relationship("Session", back_populates="polls")
    votes = relationship("PollVote", back_populates="poll", cascade="all, delete-orphan")


class PollVote(Base):
    __tablename__ = "poll_votes"
    __table_args__ = (
        UniqueConstraint("poll_id", "user_id", name="uq_poll_vote_poll_user"),
    )

    id = Column(Integer, primary_key=True, index=True)
    poll_id = Column(Integer, ForeignKey("polls.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    option_index = Column(Integer, nullable=False)  # Validated in API layer against options_json
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    poll = relationship("Poll", back_populates="votes")
    user = relationship("User", back_populates="poll_votes")
