from flask import Blueprint, render_template, redirect, url_for, session, flash
from database import db_session
from utils.decorators import login_required

main_bp = Blueprint('main', __name__)

@main_bp.route('/', endpoint='index')
def index():
    return render_template('index.html')


@main_bp.route('/leaderboard/<class_name>', endpoint='leaderboard')
@login_required
def leaderboard(class_name):
    user_id = session.get('user_id')
    role = session.get('role')

    authorized = False

    with db_session() as (conn, cur):
        if role == 'teacher':
            cur.execute("SELECT 1 FROM teacher_classes WHERE teacherid = %s AND class = %s", (user_id, class_name))
            if cur.fetchone():
                authorized = True
        elif role == 'student':
            cur.execute("SELECT 1 FROM enrollments WHERE studentid = %s AND class = %s AND approved = TRUE",
                        (user_id, class_name))
            if cur.fetchone():
                authorized = True
        elif role == 'admin':
            authorized = True

        if not authorized:
            flash("You are not authorized to view this leaderboard.", "error")
            return redirect(url_for('teacher_dashboard' if role == 'teacher' else 'student_dashboard'))

        class_lookup = class_name[:20] if class_name else ""
        cur.execute("""
            SELECT u.name, l.totalscore, l.rank
            FROM leaderboard l
            JOIN users u ON l.studentid = u.userid
            WHERE l.class = %s
            ORDER BY l.rank ASC NULLS LAST, l.totalscore DESC NULLS LAST
        """, (class_lookup,))
        leaderboard_data = cur.fetchall()

    dashboard_url = url_for('teacher_dashboard' if role == 'teacher' else ('admin_dashboard' if role == 'admin' else 'student_dashboard'))

    return render_template('leaderboard.html', class_name=class_name, leaderboard=leaderboard_data,
                           dashboard_url=dashboard_url)
