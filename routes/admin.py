from io import BytesIO
import openpyxl
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, Response
from database import db_session
from utils.decorators import role_required

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/admin_dashboard', methods=['GET', 'POST'], endpoint='admin_dashboard')
@role_required('admin')
def admin_dashboard():
    user_id = session.get('user_id')

    if request.method == 'POST':
        with db_session(commit=True) as (conn, cur):
            if 'approveteacher' in request.form:
                tid = int(request.form.get('approveteacher'))
                cur.execute("UPDATE users SET approved = TRUE WHERE userid = %s", (tid,))
                flash("Teacher approved successfully.", "success")
            elif 'rejectteacher' in request.form:
                tid = int(request.form.get('rejectteacher'))
                cur.execute("UPDATE users SET approved = FALSE WHERE userid = %s", (tid,))
                flash("Teacher rejected.", "warning")
            elif 'deactivateuser' in request.form:
                uid = int(request.form.get('deactivateuser'))
                cur.execute("UPDATE users SET approved = FALSE WHERE userid = %s", (uid,))
                flash("User deactivated.", "success")

    with db_session() as (conn, cur):
        cur.execute('SELECT name, email FROM users WHERE userid=%s', (user_id,))
        admin_row = cur.fetchone()

        cur.execute("SELECT userid, name, email, role, approved FROM users ORDER BY role, name")
        users = [dict(id=u[0], name=u[1], email=u[2], role=u[3], approved=u[4], active=u[4]) for u in cur.fetchall()]

        cur.execute("SELECT userid, name, email, role FROM users WHERE role='teacher' AND approved = FALSE ORDER BY name")
        rejected_teachers = [dict(id=rt[0], name=rt[1], email=rt[2], role=rt[3]) for rt in cur.fetchall()]

        cur.execute("SELECT COUNT(*) FROM quizzes")
        quizzes_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(DISTINCT class) FROM users WHERE class IS NOT NULL")
        classes_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM attempts WHERE endtime > (CURRENT_DATE - INTERVAL '7 days')")
        attempts_count = cur.fetchone()[0]

    return render_template('admin_dashboard.html', users=users, rejected_teachers=rejected_teachers,
                           name=admin_row[0] if admin_row else "Admin",
                           email=admin_row[1] if admin_row else "admin@annauniv.edu",
                           quizzes=quizzes_count, classes=classes_count, attempts=attempts_count)


@admin_bp.route('/export_quizzes', methods=['POST'], endpoint='export_quizzes')
@role_required('admin')
def export_quizzes():
    with db_session() as (conn, cur):
        cur.execute("""
            SELECT q.quizid, q.title, q.description, q.class, q.availablefrom, q.availableto, u.name
            FROM quizzes q LEFT JOIN users u ON q.createdby = u.userid
        """)
        quizzes = cur.fetchall()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Quizzes"
    ws.append(['Quiz ID', 'Title', 'Description', 'Class', 'Available From', 'Available To', 'Teacher'])

    for row in quizzes:
        formatted_row = list(row)
        if formatted_row[4] and hasattr(formatted_row[4], 'strftime'):
            formatted_row[4] = formatted_row[4].strftime('%Y-%m-%d %H:%M')
        elif formatted_row[4]:
            formatted_row[4] = str(formatted_row[4])

        if formatted_row[5] and hasattr(formatted_row[5], 'strftime'):
            formatted_row[5] = formatted_row[5].strftime('%Y-%m-%d %H:%M')
        elif formatted_row[5]:
            formatted_row[5] = str(formatted_row[5])

        ws.append(formatted_row)

    output = BytesIO()
    wb.save(output)
    output.seek(0)

    return Response(
        output.getvalue(),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment;filename=quiz_report.xlsx"}
    )
