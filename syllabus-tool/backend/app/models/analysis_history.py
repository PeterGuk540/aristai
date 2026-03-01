from sqlalchemy import Column, Integer, String, JSON, DateTime, Boolean
from sqlalchemy.sql import func
from app.db.base import Base

class AnalysisHistory(Base):
    __tablename__ = "analysis_history"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    file_ids = Column(JSON)  # List of file IDs used in this analysis
    file_names = Column(JSON) # List of filenames for display
    combined_text = Column(String, nullable=True) # The combined text context
    structured_data = Column(JSON) # The resulting syllabus data
    is_deleted = Column(Boolean, default=False) # Logical delete flag
