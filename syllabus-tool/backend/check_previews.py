from app.db.session import engine, get_db
from app.models.uploaded_file import UploadedFile
from sqlalchemy.orm import Session

def check_previews():
    db = next(get_db())
    files = db.query(UploadedFile).all()
    for f in files:
        print(f"ID: {f.id}, Filename: {f.filename}, Preview: {f.preview_object_name}")

if __name__ == "__main__":
    check_previews()
