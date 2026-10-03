import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "quizmaster_super_secret_key_2026")
    
    # Database engine choice ('postgresql' by default, or 'sqlite')
    DB_ENGINE = os.getenv("DB_ENGINE", "postgresql").lower()
    
    # PostgreSQL Configuration
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_NAME = os.getenv("DB_NAME", "quiz_management")
    DB_USER = os.getenv("DB_USER", "postgres")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "GANGSTER_GANESH")
    DB_PORT = int(os.getenv("DB_PORT", "5432"))

    # SQLite Path (for test suite or SQLite fallback)
    SQLITE_PATH = os.getenv("SQLITE_PATH", "quizmaster.db")
    
    # Application rules
    TEACHER_SUPERKEY = os.getenv("TEACHER_SUPERKEY", "1")
    STUDENT_DOMAIN = os.getenv("STUDENT_DOMAIN", "@student.annauniv.edu")
    TEACHER_DOMAIN = os.getenv("TEACHER_DOMAIN", "@faculty.annauniv.edu")
    
    # Default Admin seed credentials
    ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "dsselvavignesh@gmail.com")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "quagmire")
