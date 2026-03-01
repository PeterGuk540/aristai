from app.db.session import engine
from app.models.uploaded_file import UploadedFile
from sqlalchemy import text

def reset_table():
    try:
        # Try to drop the table
        with engine.connect() as connection:
            connection.execute(text("DROP TABLE IF EXISTS uploaded_files"))
            connection.commit()
        print("Dropped uploaded_files table")
    except Exception as e:
        print(f"Error dropping table: {e}")

if __name__ == "__main__":
    reset_table()
