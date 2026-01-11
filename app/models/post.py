from sqlalchemy import Column, Integer, Text, DateTime, ForeignKey, JSON, Boolean
from sqlalchemy.orm import relationship, backref
from sqlalchemy.sql import func
from app.core.database import Base


class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    content = Column(Text, nullable=False)
    parent_post_id = Column(Integer, ForeignKey("posts.id", ondelete="SET NULL"), nullable=True, index=True)
    labels_json = Column(JSON, nullable=True)  # e.g., ["high-quality", "needs-clarification"]
    pinned = Column(Boolean, default=False, nullable=False)  # Instructor can pin important posts
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    session = relationship("Session", back_populates="posts")
    user = relationship("User", back_populates="posts")
    parent = relationship(
        "Post",
        remote_side="Post.id",
        backref=backref("replies", passive_deletes=True),
    )
