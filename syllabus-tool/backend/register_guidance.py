import sys
import os
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.uploaded_file import UploadedFile

def register_guidance():
    db = SessionLocal()
    try:
        filename = "stat6010_guidance.txt"
        object_name = "stat6010_guidance.txt"
        
        # Check if already exists
        existing = db.query(UploadedFile).filter(UploadedFile.object_name == object_name).first()
        if existing:
            print(f"File {filename} already registered with ID {existing.id}")
            return

        new_file = UploadedFile(
            filename=filename,
            version=1,
            object_name=object_name,
            category="guidance",
            status="uploaded",
            school="Bowling Green State University",
            department="Business Analytics",
            subject="STAT 6010"
        )
        db.add(new_file)
        db.commit()
        db.refresh(new_file)
        print(f"Successfully registered {filename} with ID {new_file.id}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    # Add current directory to path so imports work
    sys.path.append(os.getcwd())
    register_guidance()
