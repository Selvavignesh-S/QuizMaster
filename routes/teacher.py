from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from database import db_session
from utils.decorators import role_required

teacher_bp = Blueprint('teacher', __name__)

@teacher_bp.route('/teacher_dashboard', endpoint='teacher_dashboard')
@role_required('teacher')
def teacher_dashboard():
    user_id = session.get('user_id')

    with db_session() as (conn, cur):
        cur.execute('SELECT name, email, role, class FROM users WHERE userid=%s', (user_id,))
        teacher = cur.fetchone()
        classy = teacher[3] if teacher[3] else "Not Assigned"

        cur.execute('SELECT class, subject FROM teacher_classes WHERE teacherid=%s', (user_id,))
        managed_classes = cur.fetchall()
        managed_class_list = [cls[0] for cls in managed_classes]

        cur.execute('SELECT COUNT(*) FROM quizzes WHERE createdby=%s', (user_id,))
        total_quizzes = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM quizzes WHERE createdby=%s AND isdraft=FALSE AND availableto >= NOW()",
                    (user_id,))
        active_quizzes = cur.fetchone()[0]

        cur.execute("SELECT quizid, title FROM quizzes WHERE createdby = %s", (user_id,))
        quiz_ids_titles = cur.fetchall()
        grouped_attempts = {title: [] for _, title in quiz_ids_titles}

        cur.execute("""
            SELECT q.quizid, q.title, u.name, u.email, a.score, a.endtime 
            FROM attempts a
            JOIN quizzes q ON a.quizid = q.quizid
            JOIN users u ON a.studentid = u.userid
            WHERE q.createdby = %s AND a.score IS NOT NULL
            ORDER BY q.title, a.endtime DESC
        """, (user_id,))

        for qid, title, s_name, s_email, score, endtime in cur.fetchall():
            endtime_str = endtime.strftime('%Y-%m-%d %H:%M') if (endtime and hasattr(endtime, 'strftime')) else str(endtime or 'N/A')
            grouped_attempts[title].append({
                "student_name": s_name, "student_email": s_email,
                "score": float(score), "endtime": endtime_str
            })

        if managed_class_list:
            cur.execute("SELECT COUNT(*) FROM users WHERE class = ANY(%s) AND role='student'", (managed_class_list,))
            total_students = cur.fetchone()[0]
        else:
            total_students = 0

        cur.execute("""
            SELECT AVG(a.score) FROM attempts a
            JOIN quizzes q ON a.quizid = q.quizid
            WHERE q.createdby = %s AND a.score IS NOT NULL
        """, (user_id,))
        avg_score = cur.fetchone()[0] or 0

        cur.execute("""
            SELECT f.feedbackid, f.feedback, f.comments, f.createdat, u.name, q.title
            FROM feedback f
            JOIN users u ON f.studentid = u.userid
            JOIN attempts a ON f.attemptid = a.attemptid
            JOIN quizzes q ON a.quizid = q.quizid
            WHERE f.teacherid = %s ORDER BY f.createdat DESC
        """, (user_id,))

        feedbacks = []
        for row in cur.fetchall():
            feedbacks.append({
                'feedbackid': row[0], 'feedback': row[1], 'comments': row[2],
                'createdat': row[3], 'student_name': row[4], 'quiz_title': row[5]
            })

        cur.execute("""
            SELECT quizid, title, description, availablefrom, availableto, attemptlimit, isdraft, class 
            FROM quizzes WHERE createdby=%s ORDER BY quizid DESC
        """, (user_id,))
        quiz_list = cur.fetchall()

        if managed_class_list:
            cur.execute("SELECT COUNT(*) FROM enrollments WHERE approved IS NULL AND class = ANY(%s)",
                        (managed_class_list,))
            num_pending_enrollments = cur.fetchone()[0]
        else:
            num_pending_enrollments = 0

    return render_template(
        'teacher_dashboard.html',
        name=teacher[0], email=teacher[1], role=teacher[2], classy=classy,
        managed_classes=managed_classes, total_quizzes=total_quizzes,
        active_quizzes=active_quizzes, total_students=total_students,
        avg_score=round(float(avg_score), 2), quiz_list=quiz_list,
        num_pending_enrollments=num_pending_enrollments,
        grouped_attempts=grouped_attempts, feedbacks=feedbacks
    )


@teacher_bp.route('/pending_enrollments', methods=['GET', 'POST'], endpoint='pending_enrollments')
@role_required('teacher')
def pending_enrollments():
    user_id = session.get('user_id')

    with db_session(commit=True) as (conn, cur):
        cur.execute("SELECT class FROM teacher_classes WHERE teacherid = %s", (user_id,))
        classes = [row[0] for row in cur.fetchall()]

        if not classes:
            flash("You aren't managing any classes.", "error")
            return redirect(url_for('teacher_dashboard'))

        if request.method == 'POST':
            eid = request.form.get('enrollment_id')
            action = request.form.get('action')

            cur.execute("""
                SELECT 1 FROM enrollments e
                JOIN teacher_classes tc ON e.class = tc.class
                WHERE e.enrollmentid = %s AND tc.teacherid = %s
            """, (eid, user_id))

            if cur.fetchone():
                status = True if action == 'approve' else False
                cur.execute("UPDATE enrollments SET approved = %s WHERE enrollmentid = %s", (status, eid))
                flash("Enrollment processed successfully.", "success")

            return redirect(url_for('pending_enrollments'))

        cur.execute("""
            SELECT e.enrollmentid, u.userid, u.name, u.email, e.class
            FROM enrollments e
            JOIN users u ON e.studentid = u.userid
            WHERE e.class = ANY(%s) AND e.approved IS NULL
        """, (classes,))
        requests = cur.fetchall()

    return render_template('pending_enrollments.html', requests=requests, classes=classes)


@teacher_bp.route('/create_class', methods=['GET', 'POST'], endpoint='create_class')
@role_required('teacher')
def create_class():
    user_id = session.get('user_id')

    if request.method == 'POST':
        c_name = request.form.get('class_name', '').strip()
        subj = request.form.get('subject', '').strip()

        with db_session(commit=True) as (conn, cur):
            cur.execute("SELECT 1 FROM teacher_classes WHERE class = %s", (c_name,))
            if cur.fetchone():
                flash(f"Class '{c_name}' already exists.", "error")
            else:
                cur.execute("INSERT INTO teacher_classes (teacherid, class, subject) VALUES (%s, %s, %s)",
                            (user_id, c_name, subj))
                flash("Class created successfully!", "success")
                return redirect(url_for('teacher_dashboard'))

    return render_template('create_class.html')


@teacher_bp.route('/create_quiz', methods=['GET', 'POST'], endpoint='create_quiz')
@role_required('teacher')
def create_quiz():
    user_id = session.get('user_id')

    with db_session() as (conn, cur):
        cur.execute("SELECT class, subject FROM teacher_classes WHERE teacherid=%s", (user_id,))
        teacher_classes = cur.fetchall()

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        desc = request.form.get('description', '').strip()
        diff = request.form.get('difficulty', 'Medium')
        a_from = request.form.get('available_from')
        a_to = request.form.get('available_to')
        limit = request.form.get('attempt_limit', '1')
        c_name = request.form.get('class', '')

        with db_session(commit=True) as (conn, cur):
            cur.execute("""
                INSERT INTO quizzes (title, description, difficulty, availablefrom, availableto, attemptlimit, createdby, class, isdraft)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, TRUE)
            """, (title, desc, diff, a_from, a_to, limit, user_id, c_name))

            cur.execute("""
                SELECT MAX(quizid) FROM quizzes WHERE createdby=%s
            """, (user_id,))
            qid = cur.fetchone()[0]

        flash("Quiz created as draft!", "success")
        return redirect(url_for('manage_questions', quiz_id=qid))

    return render_template('create_quiz.html', teacher_classes=teacher_classes)


@teacher_bp.route('/manage_questions/<int:quiz_id>', methods=['GET', 'POST'], endpoint='manage_questions')
@role_required('teacher')
def manage_questions(quiz_id):
    user_id = session.get('user_id')

    with db_session() as (conn, cur):
        cur.execute("""
            SELECT quizid, createdby, title, description, difficulty, availablefrom, availableto, attemptlimit, isdraft, class
            FROM quizzes WHERE quizid=%s AND createdby=%s
        """, (quiz_id, user_id))
        quiz = cur.fetchone()

    if not quiz:
        flash("Quiz not accessible.", "error")
        return redirect(url_for('teacher_dashboard'))

    if request.method == 'POST':
        if not quiz[8]:  # isdraft
            flash("Published quizzes are locked.", "error")
        else:
            q_text = request.form.get('question_text')
            op_a = request.form.get('option_a')
            op_b = request.form.get('option_b')
            op_c = request.form.get('option_c')
            op_d = request.form.get('option_d')
            correct = request.form.get('correct_option')
            diff = request.form.get('difficulty', 'Medium')

            with db_session(commit=True) as (conn, cur):
                cur.execute("""
                    INSERT INTO questions (quizid, questiontext, optiona, optionb, optionc, optiond, correctoption, difficulty)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (quiz_id, q_text, op_a, op_b, op_c, op_d, correct, diff))
            flash("Question added!", "success")
        return redirect(url_for('manage_questions', quiz_id=quiz_id))

    with db_session() as (conn, cur):
        cur.execute("SELECT * FROM questions WHERE quizid=%s ORDER BY questionid", (quiz_id,))
        questions = cur.fetchall()

    return render_template('questions.html', quiz=quiz, questions=questions, quiz_id=quiz_id)


@teacher_bp.route('/publish_quiz/<int:quiz_id>', endpoint='publish_quiz')
@role_required('teacher')
def publish_quiz(quiz_id):
    user_id = session.get('user_id')

    with db_session(commit=True) as (conn, cur):
        cur.execute("SELECT COUNT(*) FROM questions WHERE quizid = %s", (quiz_id,))
        if cur.fetchone()[0] == 0:
            flash("Add at least one question before publishing.", "error")
            return redirect(url_for('manage_questions', quiz_id=quiz_id))

        cur.execute("UPDATE quizzes SET isdraft = FALSE WHERE quizid = %s AND createdby = %s", (quiz_id, user_id))

    flash("Quiz is now live!", "success")
    return redirect(url_for('teacher_dashboard'))


@teacher_bp.route('/delete_question/<int:question_id>', endpoint='delete_question')
@role_required('teacher')
def delete_question(question_id):
    user_id = session.get('user_id')

    with db_session(commit=True) as (conn, cur):
        cur.execute("""
            SELECT q.quizid, qz.isdraft, qz.createdby FROM questions q
            JOIN quizzes qz ON q.quizid = qz.quizid WHERE q.questionid = %s
        """, (question_id,))
        res = cur.fetchone()

        if res and res[2] == user_id and res[1]:
            cur.execute("DELETE FROM questions WHERE questionid = %s", (question_id,))
            flash("Question deleted.", "success")
            quiz_id = res[0]
        else:
            flash("Cannot delete question.", "error")
            quiz_id = res[0] if res else 0

    return redirect(url_for('manage_questions', quiz_id=quiz_id))
