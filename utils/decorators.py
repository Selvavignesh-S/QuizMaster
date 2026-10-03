from functools import wraps
from flask import session, redirect, url_for, flash

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user_id'):
            flash("Please log in to access this page.", "error")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user_id = session.get('user_id')
            user_role = session.get('role')
            if not user_id:
                flash("Please log in to access this page.", "error")
                return redirect(url_for('login'))
            if user_role not in roles:
                flash("Unauthorized access.", "error")
                if user_role == 'student':
                    return redirect(url_for('student_dashboard'))
                elif user_role == 'teacher':
                    return redirect(url_for('teacher_dashboard'))
                elif user_role == 'admin':
                    return redirect(url_for('admin_dashboard'))
                return redirect(url_for('login'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator
