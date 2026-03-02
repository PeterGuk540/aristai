from sqlalchemy import Column, Integer, String, JSON, DateTime
from sqlalchemy.sql import func
from app.db.base import Base

class Syllabus(Base):
    __tablename__ = "syllabuses"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    content = Column(JSON)
    template_id = Column(String, default="BGSU_Standard")
    instructor_id = Column(Integer, nullable=True, index=True)  # Forum user.id
    source = Column(String, default="standalone")                # "standalone" | "forum_embed"
    forum_course_title = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
