import sys
import os
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
import logging

# Add backend directory to sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.db.base import Base
from app.models.syllabus import Syllabus
from app.models.uploaded_file import UploadedFile
from app.models.analysis_history import AnalysisHistory

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# CONFIGURATION
# 1. Source (SQLite)
SQLITE_URI = "sqlite:///./syllabus.db"

# 2. Destination (Supabase)
# We try to get this from the environment variable (which should be updated by the user)
# Or pass it as an argument
DEST_URI = os.getenv("SQLALCHEMY_DATABASE_URI")

def migrate():
    if not DEST_URI or "sqlite" in DEST_URI or "YOUR_SUPABASE_DB_PASSWORD" in DEST_URI:
        logger.error("Destination URI is invalid. Please update SQLALCHEMY_DATABASE_URI in .env with your Supabase password.")
        logger.error("Current URI: %s", DEST_URI)
        return

    logger.info("Connecting to Source (SQLite)...")
    source_engine = create_engine(SQLITE_URI)
    SourceSession = sessionmaker(bind=source_engine)
    source_session = SourceSession()

    logger.info("Connecting to Destination (Supabase Postgres)...")
    try:
        dest_engine = create_engine(DEST_URI)
        DestSession = sessionmaker(bind=dest_engine)
        dest_session = DestSession()
        
        # Test connection explicitly before proceeding
        with dest_engine.connect() as conn:
            pass
            
    except Exception as e:
        logger.error(f"Failed to connect to Supabase: {e}")
        error_str = str(e)
        if "Network is unreachable" in error_str and "supabase.co" in DEST_URI:
             logger.error("\n[CRITICAL ERROR] IPv6 Connectivity Issue Detected")
             logger.error("The Supabase Direct DB URL (db.project.supabase.co) functionality resolves to IPv6 only.")
             logger.error("Your current environment appears to support only IPv4.")
             logger.error("SOLUTION: You MUST use the Supabase Connection Pooler (Supavisor).")
             logger.error("1. Go to Supabase Dashboard -> Project Settings -> Database -> Connection Pooling")
             logger.error("2. Copy the Host (e.g., aws-0-us-east-1.pooler.supabase.com) and Port (6543)")
             logger.error("3. Update your backend/.env file with these values.")
        sys.exit(1)

    # 1. Create Tables in Destination
    logger.info("Creating tables in destination...")
    Base.metadata.create_all(dest_engine)

    # 2. Migrate UploadedFiles
    logger.info("Migrating UploadedFiles...")
    files = source_session.query(UploadedFile).all()
    logger.info(f"Found {len(files)} files to migrate.")
    for f in files:
        # Check if exists
        existing = dest_session.query(UploadedFile).filter_by(id=f.id).first()
        if not existing:
            new_f = UploadedFile(
                id=f.id,
                filename=f.filename,
                object_name=f.object_name,
                preview_object_name=f.preview_object_name,
                version=f.version,
                category=f.category,
                parsed_data=f.parsed_data,
                status=f.status,
                school=f.school,
                department=f.department,
                subject=f.subject,
                created_at=f.created_at
            )
            dest_session.add(new_f)
    dest_session.commit()

    # 3. Migrate AnalysisHistory
    logger.info("Migrating AnalysisHistory...")
    histories = source_session.query(AnalysisHistory).all()
    logger.info(f"Found {len(histories)} history items.")
    for h in histories:
        existing = dest_session.query(AnalysisHistory).filter_by(id=h.id).first()
        if not existing:
            new_h = AnalysisHistory(
                id=h.id,
                file_ids=h.file_ids,
                file_names=h.file_names,
                combined_text=h.combined_text,
                structured_data=h.structured_data,
                created_at=h.created_at,
                is_deleted=h.is_deleted
            )
            dest_session.add(new_h)
    dest_session.commit()

    # 4. Migrate Syllabuses (if any exist in DB)
    logger.info("Migrating Syllabuses...")
    
    syllabi_rows = []
    try:
        # Try full query first
        syllabi_rows = source_session.query(Syllabus).all()
    except Exception:
        source_session.rollback()
        logger.info("Source table missing columns (likely template_id), querying available columns only.")
        syllabi_rows = source_session.query(
            Syllabus.id,
            Syllabus.title,
            Syllabus.content,
            Syllabus.created_at,
            Syllabus.updated_at
        ).all()

    logger.info(f"Found {len(syllabi_rows)} syllabi.")
    for s in syllabi_rows:
        existing = dest_session.query(Syllabus).filter_by(id=s.id).first()
        if not existing:
            # Default to "BGSU_Standard" if template_id is missing from source row
            t_id = getattr(s, 'template_id', "BGSU_Standard")
            # Handle None case if column existed but was null
            if t_id is None: 
                t_id = "BGSU_Standard"

            new_s = Syllabus(
                id=s.id,
                title=s.title,
                content=s.content,
                template_id=t_id,
                created_at=s.created_at,
                updated_at=s.updated_at
            )
            dest_session.add(new_s)
    dest_session.commit()

    logger.info("Migration Completed Successfully!")
    source_session.close()
    dest_session.close()

if __name__ == "__main__":
    # Load .env explicitly if needed
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), '../.env'))
    
    # Re-fetch DEST_URI after load_dotenv
    DEST_URI = os.getenv("SQLALCHEMY_DATABASE_URI")
    
    migrate()
