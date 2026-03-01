from sqlalchemy import Column, Integer, String, DateTime, JSON
from sqlalchemy.sql import func
from app.db.base import Base

class UploadedFile(Base):
    __tablename__ = "uploaded_files"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, index=True) # Removed unique=True
    version = Column(Integer, default=1)
    object_name = Column(String, unique=True) # MinIO object name
    preview_object_name = Column(String, nullable=True) # MinIO object name for PDF preview
    category = Column(String, index=True)  # 'template', 'example', 'user_upload'
    status = Column(String, default="uploaded")  # 'uploaded', 'processed', 'reviewed'
    school = Column(String, nullable=True)
    department = Column(String, nullable=True)
    subject = Column(String, nullable=True)
    parsed_data = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
