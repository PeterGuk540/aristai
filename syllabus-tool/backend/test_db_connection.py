import psycopg2
try:
    conn = psycopg2.connect(
        dbname="syllabus_tool",
        user="syllabus_tool",
        password="123321",
        host="localhost",
        port="5432"
    )
    print("Connection successful")
    conn.close()
except Exception as e:
    print(f"Connection failed: {e}")
