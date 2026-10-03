import os
import re
from database import get_db_connection, db_session
from config import Config

def init_db(sql_file="schema.sql", reset=False):
    if not os.path.exists(sql_file):
        print(f"Schema file {sql_file} not found.")
        return

    with open(sql_file, "r", encoding="utf-8") as f:
        sql_content = f.read()

    conn = get_db_connection()
    is_sqlite = hasattr(conn, '_conn') or Config.DB_ENGINE == 'sqlite'

    if reset:
        tables = ["feedback", "leaderboard", "responses", "attempts", "questions", "quizzes", "enrollments", "teacher_classes", "users"]
        if is_sqlite:
            raw_conn = getattr(conn, '_conn', conn)
            cursor = raw_conn.cursor()
            for t in tables:
                cursor.execute(f"DROP TABLE IF EXISTS {t}")
            raw_conn.commit()
        else:
            cur = conn.cursor()
            for t in tables:
                cur.execute(f"DROP TABLE IF EXISTS {t} CASCADE")
            conn.commit()
            cur.close()
    
    if is_sqlite:
        raw_conn = getattr(conn, '_conn', conn)
        sqlite_sql = sql_content.replace("SERIAL PRIMARY KEY", "INTEGER PRIMARY KEY AUTOINCREMENT")
        sqlite_sql = sqlite_sql.replace("TIMESTAMP DEFAULT CURRENT_TIMESTAMP", "DATETIME DEFAULT CURRENT_TIMESTAMP")
        sqlite_sql = sqlite_sql.replace("TIMESTAMP", "DATETIME")
        sqlite_sql = re.sub(r'VARCHAR\(\d+\)', 'TEXT', sqlite_sql)
        sqlite_sql = sqlite_sql.replace("BOOLEAN DEFAULT NULL", "BOOLEAN DEFAULT NULL")
        
        raw_conn.executescript(sqlite_sql)
        raw_conn.commit()
        raw_conn.close()
    else:
        cur = conn.cursor()
        cur.execute(sql_content)
        conn.commit()
        cur.close()
        conn.close()

    # Seed Admin User only if no admin user exists in DB
    with db_session(commit=True) as (conn, cur):
        cur.execute("SELECT userid FROM users WHERE role='admin'")
        admin_user = cur.fetchone()
        if not admin_user:
            cur.execute("""
                INSERT INTO users (name, email, passwordhash, role, approved)
                VALUES (%s, %s, %s, %s, %s)
            """, ('Super Admin', Config.ADMIN_EMAIL, Config.ADMIN_PASSWORD, 'admin', True))
            print(f"Admin account created: {Config.ADMIN_EMAIL}")

if __name__ == "__main__":
    init_db()
