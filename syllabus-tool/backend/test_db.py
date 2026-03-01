import psycopg2
from app.core.config import settings
import sys

def create_db():
    print("Connecting as 'postgres' to create database...")
    try:
        conn = psycopg2.connect(
            dbname="postgres",
            user="postgres", # Use postgres user
            password=settings.POSTGRES_PASSWORD,
            host=settings.POSTGRES_SERVER,
            port=settings.POSTGRES_PORT
        )
        conn.autocommit = True
        cur = conn.cursor()
        
        cur.execute("SELECT 1 FROM pg_database WHERE datname = 'syllabus_tool'")
        if not cur.fetchone():
            print("Creating database 'syllabus_tool'...")
            cur.execute("CREATE DATABASE syllabus_tool")
            print("Database created.")
        else:
            print("Database 'syllabus_tool' already exists.")
            
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

create_db()


