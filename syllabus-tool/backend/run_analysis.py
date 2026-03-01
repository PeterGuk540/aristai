import sys
import os
import json
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.uploaded_file import UploadedFile
from app.services.storage import storage_service
from app.services.parser import parse_file, extract_syllabus_data

def run_analysis(syllabus_id, guidance_id):
    db = SessionLocal()
    try:
        syllabus_file = db.query(UploadedFile).filter(UploadedFile.id == syllabus_id).first()
        guidance_file = db.query(UploadedFile).filter(UploadedFile.id == guidance_id).first()
        
        if not syllabus_file or not guidance_file:
            print("Files not found")
            return

        print(f"Analyzing {syllabus_file.filename} using {guidance_file.filename}...")
        
        # Get content
        s_content = storage_service.get_file(syllabus_file.object_name)
        g_content = storage_service.get_file(guidance_file.object_name)
        
        s_text = parse_file(syllabus_file.filename, s_content)
        g_text = parse_file(guidance_file.filename, g_content)
        
        # Extract
        data = extract_syllabus_data(s_text, g_text)
        
        # Save to DB
        syllabus_file.parsed_data = data
        syllabus_file.status = "processed"
        db.commit()
        print("Saved analysis results to database.")
        
        # Print Validation Results
        if data.get("validation"):
            print("\n=== VALIDATION RESULTS ===")
            print(f"Conforms: {data['validation'].get('conforms_to_guidance')}")
            print("\nIssues:")
            for issue in data['validation'].get('issues', []):
                if isinstance(issue, dict):
                    print(f"- [{issue.get('type', 'issue').upper()}] {issue.get('issue')}")
                    print(f"  Suggestion: {issue.get('suggestion')}")
                else:
                    print(f"- {issue}")
        else:
            print("No validation data returned.")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    sys.path.append(os.getcwd())
    # ID 1 is the syllabus, ID 4 is the new guidance
    run_analysis(1, 4)
