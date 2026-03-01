from app.db.session import engine
from sqlalchemy import text

def reset_history_table():
    try:
        with engine.connect() as connection:
            connection.execute(text("DROP TABLE IF EXISTS analysis_history"))
            connection.commit()
        print("Dropped analysis_history table")
    except Exception as e:
        print(f"Error dropping table: {e}")

if __name__ == "__main__":
    reset_history_table()
