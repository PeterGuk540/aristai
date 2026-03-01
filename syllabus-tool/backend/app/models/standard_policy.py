from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.sql import func
from app.db.base import Base

class StandardPolicy(Base):
    __tablename__ = "standard_policies"

    id = Column(Integer, primary_key=True, index=True)
    category = Column(String, index=True)  # e.g., "Attendance", "Grading", "Academic Integrity"
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
