from collections import defaultdict
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from database import db_session
from utils.decorators import role_required

student_bp = Blueprint('student', __name__)

@student_bp.route('/student_dashboard', methods=['GET', 'POST'], endpoint='student_dashboard')
@role_required('student')
def student_dashboard():
    user_id = session.get('user_id')

    if request.method == 'POST':
        class_to_enroll = request.form.get('class_to_enroll', '').strip()

        with db_session(commit=True) as (conn, cur):
            cur.execute('''
                SELECT approved FROM enrollments 
                WHERE studentid=%s AND class=%s 
                ORDER BY requested_at DESC LIMIT 1
            ''', (user_id, class_to_enroll))
            latest = cur.fetchone()

            if latest:
                if latest[0] is None:
                    flash(f"You already have a pending enrollment request for '{class_to_enroll}'.", "warning")
                elif latest[0] is True:
                    flash(f"You are already enrolled in '{class_to_enroll}'.", "info")
                else:
                    cur.execute('''
                        INSERT INTO enrollments (studentid, class, approved, requested_at) 
                        VALUES (%s, %s, NULL, NOW())
                    ''', (user_id, class_to_enroll))
                    flash(f"Enrollment request reapplied for '{class_to_enroll}'.", "success")
            else:
                cur.execute('''
                    INSERT INTO enrollments (studentid, class, approved, requested_at)
                    VALUES (%s, %s, NULL, NOW())
                ''', (user_id, class_to_enroll))
                flash(f"Enrollment request for '{class_to_enroll}' submitted!", "success")

        return redirect(url_for('student_dashboard'))

    # GET Workflow Details
    with db_session() as (conn, cur):
        cur.execute("SELECT tc.class, tc.subject, u.name FROM teacher_classes tc JOIN users u ON tc.teacherid = u.userid")
        available_classes = cur.fetchall()

        cur.execute('SELECT name, email, role FROM users WHERE userid=%s', (user_id,))
        student = cur.fetchone()

        cur.execute('SELECT class FROM enrollments WHERE studentid=%s AND approved=TRUE', (user_id,))
        student_classes = [row[0] for row in cur.fetchall()]

        cur.execute('SELECT class, approved FROM enrollments WHERE studentid=%s ORDER BY requested_at DESC', (user_id,))
        rows = cur.fetchall()

        status_by_class = defaultdict(list)
        for cls, approved in rows:
            status_by_class[cls].append(approved)

        pending_enrollment_classes = [cls for cls, stats in status_by_class.items() if stats[0] is None]
        rejected_enrollment_classes = [cls for cls, stats in status_by_class.items() if stats[0] is False]

        cur.execute("""
            SELECT DISTINCT e.class, tc.subject FROM enrollments e
            LEFT JOIN teacher_classes tc ON e.class = tc.class
            WHERE e.studentid=%s AND e.approved=TRUE ORDER BY e.class
        """, (user_id,))
        enrolled_classes = cur.fetchall()
        enrollment_dict = {cls: True for cls, _ in enrolled_classes}

        cur.execute('SELECT COUNT(*) FROM attempts WHERE studentid=%s AND score IS NOT NULL', (user_id,))
        completed_quizzes = cur.fetchone()[0]

        cur.execute('SELECT AVG(score) FROM attempts WHERE studentid=%s AND score IS NOT NULL', (user_id,))
        avg_score = cur.fetchone()[0] or 0

        if student_classes:
            cur.execute('''
                SELECT COUNT(*) FROM quizzes 
                WHERE class = ANY(%s) AND isdraft = FALSE
                AND quizid NOT IN (SELECT quizid FROM attempts WHERE studentid=%s AND score IS NOT NULL)
            ''', (student_classes, user_id))
            pending_quizzes = cur.fetchone()[0]
        else:
            pending_quizzes = 0

        cur.execute('SELECT MAX(score) FROM attempts WHERE studentid=%s AND score IS NOT NULL', (user_id,))
        best_score = cur.fetchone()[0] or 0

        upcoming_quizzes = []
        if student_classes:
            cur.execute('''
                SELECT quizid, title, availablefrom, availableto, class FROM quizzes
                WHERE class = ANY(%s) AND isdraft = FALSE
                AND quizid NOT IN (SELECT quizid FROM attempts WHERE studentid=%s AND score IS NOT NULL)
                ORDER BY availablefrom ASC
            ''', (student_classes, user_id))
            upcoming_quizzes = cur.fetchall()

        cur.execute('''
            SELECT q.title, a.score, a.attemptid FROM attempts a
            JOIN quizzes q ON a.quizid = q.quizid
            WHERE a.studentid=%s AND a.score IS NOT NULL
            ORDER BY a.endtime DESC LIMIT 5
        ''', (user_id,))
        recent_results = cur.fetchall()

        cur.execute('SELECT attemptid FROM feedback WHERE studentid = %s', (user_id,))
        feedback_attempt_ids = {row[0] for row in cur.fetchall()}

    return render_template(
        'student_dashboard.html',
        name=student[0], email=student[1], role=student[2],
        available_classes=available_classes, student_classes=student_classes,
        enrolled_classes=enrolled_classes, completed_quizzes=completed_quizzes,
        avg_score=avg_score, pending_quizzes=pending_quizzes, best_score=best_score,
        upcoming_quizzes=upcoming_quizzes, recent_results=recent_results,
        enrollment_dict=enrollment_dict, rejected_enrollment_classes=rejected_enrollment_classes,
        feedback_attempt_ids=feedback_attempt_ids, pending_enrollment_classes=pending_enrollment_classes
    )


@student_bp.route('/attempt_quiz/<int:quiz_id>', endpoint='attempt_quiz')
@role_required('student')
def attempt_quiz(quiz_id):
    user_id = session.get('user_id')

    with db_session() as (conn, cur):
        cur.execute("""
            SELECT quizid, createdby, title, description, difficulty, 
                   availablefrom, availableto, attemptlimit, isdraft, class 
            FROM quizzes WHERE quizid=%s
        """, (quiz_id,))
        quiz = cur.fetchone()

        if not quiz:
            flash("Quiz not found.", "error")
            return redirect(url_for('student_dashboard'))

        cur.execute("SELECT 1 FROM enrollments WHERE studentid=%s AND class=%s AND approved=TRUE", (user_id, quiz[9]))
        if not cur.fetchone():
            flash("You are not enrolled in this class.", "error")
            return redirect(url_for('student_dashboard'))

        cur.execute("SELECT COUNT(*) FROM attempts WHERE quizid=%s AND studentid=%s", (quiz_id, user_id))
        attempt_count = cur.fetchone()[0]

    return render_template('attempt_quiz.html', quiz=quiz, attempt_count=attempt_count, quiz_id=quiz_id)


@student_bp.route('/start_quiz/<int:quiz_id>', endpoint='start_quiz')
@role_required('student')
def start_quiz(quiz_id):
    user_id = session.get('user_id')

    with db_session(commit=True) as (conn, cur):
        cur.execute("""
            SELECT COALESCE(MAX(attemptno), 0) + 1 FROM attempts WHERE quizid=%s AND studentid=%s
        """, (quiz_id, user_id))
        next_attemptno = cur.fetchone()[0]

        cur.execute("""
            INSERT INTO attempts (quizid, studentid, attemptno, starttime)
            VALUES (%s, %s, %s, NOW())
        """, (quiz_id, user_id, next_attemptno))
        
        cur.execute("""
            SELECT MAX(attemptid) FROM attempts WHERE quizid=%s AND studentid=%s
        """, (quiz_id, user_id))
        attempt_id = cur.fetchone()[0]

    return redirect(url_for('take_quiz', attempt_id=attempt_id))


@student_bp.route('/take_quiz/<int:attempt_id>', methods=['GET', 'POST'], endpoint='take_quiz')
@role_required('student')
def take_quiz(attempt_id):
    user_id = session.get('user_id')

    with db_session() as (conn, cur):
        cur.execute("SELECT quizid, studentid FROM attempts WHERE attemptid=%s", (attempt_id,))
        attempt = cur.fetchone()

        if not attempt or attempt[1] != user_id:
            flash("Invalid attempt.", "error")
            return redirect(url_for('student_dashboard'))

        quiz_id = attempt[0]

        cur.execute("SELECT quizid, createdby, title, description FROM quizzes WHERE quizid=%s", (quiz_id,))
        quiz = cur.fetchone()

        cur.execute("""
            SELECT questionid, questiontext, optiona, optionb, optionc, optiond 
            FROM questions WHERE quizid=%s ORDER BY questionid
        """, (quiz_id,))
        questions = cur.fetchall()

    if request.method == 'POST':
        correct_count = 0
        total_questions = len(questions)

        with db_session(commit=True) as (conn, cur):
            for question in questions:
                qid = question[0]
                selected_answer = request.form.get(f'question_{qid}')

                cur.execute("SELECT correctoption FROM questions WHERE questionid=%s", (qid,))
                correct_answer = cur.fetchone()[0]

                iscorrect = (selected_answer == correct_answer)
                if iscorrect:
                    correct_count += 1

                cur.execute("""
                    INSERT INTO responses (attemptid, questionid, selectedoption, iscorrect, submittedat)
                    VALUES (%s, %s, %s, %s, NOW())
                """, (attempt_id, qid, selected_answer, iscorrect))

            score = (correct_count / total_questions * 100) if total_questions > 0 else 0

            cur.execute("UPDATE attempts SET score=%s, endtime=NOW() WHERE attemptid=%s", (score, attempt_id))

            cur.execute("SELECT class FROM quizzes WHERE quizid=%s", (quiz_id,))
            quiz_class_row = cur.fetchone()
            quiz_class = quiz_class_row[0] if quiz_class_row else ""
            quiz_class_truncated = quiz_class[:20] if quiz_class else ""

            cur.execute("SELECT leaderboardid, totalscore FROM leaderboard WHERE studentid = %s AND class = %s",
                        (user_id, quiz_class_truncated))
            existing_entry = cur.fetchone()

            if existing_entry:
                lid, old_score = existing_entry
                if score > float(old_score):
                    cur.execute("UPDATE leaderboard SET totalscore = %s WHERE leaderboardid = %s", (score, lid))
            else:
                cur.execute("""
                    INSERT INTO leaderboard (quizid, studentid, totalscore, class)
                    VALUES (%s, %s, %s, %s)
                """, (quiz_id, user_id, score, quiz_class_truncated))

            # Re-rank execution paths
            cur.execute("SELECT leaderboardid FROM leaderboard WHERE class = %s ORDER BY totalscore DESC",
                        (quiz_class_truncated,))
            for idx, row in enumerate(cur.fetchall(), start=1):
                cur.execute("UPDATE leaderboard SET rank = %s WHERE leaderboardid = %s", (idx, row[0]))

        flash(f"Quiz submitted! Your score: {score:.2f}%", "success")
        return redirect(url_for('feedback', attempt_id=attempt_id))

    return render_template('take_quiz.html', quiz=quiz, questions=questions, attempt_id=attempt_id)


@student_bp.route('/list_responses', endpoint='list_responses')
@role_required('student', 'teacher', 'admin')
def list_responses():
    user_id = session.get('user_id')
    role = session.get('role')

    with db_session() as (conn, cur):
        cur.execute("""
            SELECT a.attemptid, q.title, a.score, a.starttime, a.endtime, q.class
            FROM attempts a
            JOIN quizzes q ON a.quizid = q.quizid
            WHERE a.studentid = %s AND a.score IS NOT NULL ORDER BY a.endtime DESC
        """, (user_id,))
        attempts_raw = cur.fetchall()

    attempts = []
    for attempt in attempts_raw:
        starttime = attempt[3]
        endtime = attempt[4]
        
        # Safe format if datetime object or string
        if hasattr(starttime, 'strftime'):
            st_str = starttime.strftime('%Y-%m-%d %H:%M:%S')
        else:
            st_str = str(starttime) if starttime else 'N/A'
            
        if hasattr(endtime, 'strftime'):
            et_str = endtime.strftime('%Y-%m-%d %H:%M:%S')
        else:
            et_str = str(endtime) if endtime else 'N/A'

        duration = 0
        if starttime and endtime and hasattr(endtime, '__sub__') and hasattr(starttime, '__sub__'):
            try:
                duration = int((endtime - starttime).total_seconds() / 60)
            except Exception:
                duration = 0

        attempts.append((
            attempt[0], attempt[1], float(attempt[2]) if attempt[2] is not None else 0.0,
            st_str, et_str, attempt[5], duration
        ))

    return render_template('list_responses.html', attempts=attempts, role=role)


@student_bp.route('/view_responses/<int:attemptid>', endpoint='view_responses')
@role_required('student', 'teacher', 'admin')
def view_responses(attemptid):
    userid = session.get('user_id')
    role = session.get('role')

    with db_session() as (conn, cur):
        cur.execute("""
            SELECT a.studentid, q.title, a.score, a.starttime, a.endtime
            FROM attempts a
            JOIN quizzes q ON a.quizid = q.quizid
            WHERE a.attemptid = %s
        """, (attemptid,))
        attempt = cur.fetchone()

        if not attempt:
            flash("Attempt not found.", "error")
            return redirect(url_for('list_responses'))

        if role == 'student' and attempt[0] != userid:
            flash("Unauthorized access.", "error")
            return redirect(url_for('list_responses'))

        st = attempt[3]
        et = attempt[4]
        if isinstance(st, str):
            try:
                st = datetime.strptime(st.split('.')[0], '%Y-%m-%d %H:%M:%S')
            except Exception:
                pass
        if isinstance(et, str):
            try:
                et = datetime.strptime(et.split('.')[0], '%Y-%m-%d %H:%M:%S')
            except Exception:
                pass

        attempt_cleaned = (attempt[0], attempt[1], float(attempt[2]) if attempt[2] is not None else 0.0, st, et)

        cur.execute("""
            SELECT r.questionid, q.questiontext, r.selectedoption, r.iscorrect, q.correctoption
            FROM responses r
            JOIN questions q ON r.questionid = q.questionid
            WHERE r.attemptid = %s ORDER BY r.questionid
        """, (attemptid,))
        responses = cur.fetchall()

    return render_template('view_responses.html', attempt=attempt_cleaned, responses=responses)


@student_bp.route('/feedback/<int:attempt_id>', endpoint='feedback')
@role_required('student')
def feedback(attempt_id):
    user_id = session.get('user_id')

    with db_session() as (conn, cur):
        cur.execute("SELECT studentid FROM attempts WHERE attemptid=%s", (attempt_id,))
        attempt = cur.fetchone()
        if not attempt or attempt[0] != user_id:
            flash("Invalid attempt context.", "error")
            return redirect(url_for('student_dashboard'))

        cur.execute("SELECT 1 FROM feedback WHERE attemptid=%s AND studentid=%s", (attempt_id, user_id))
        if cur.fetchone():
            flash("Feedback already submitted.", "info")
            return redirect(url_for('student_dashboard'))

    return render_template('feedback.html', attempt_id=attempt_id)


@student_bp.route('/submit_feedback/<int:attempt_id>', methods=['POST'], endpoint='submit_feedback')
@role_required('student')
def submit_feedback(attempt_id):
    user_id = session.get('user_id')

    feedback_text = request.form.get('feedback', '').strip()
    comments_text = request.form.get('comments', '').strip()

    with db_session(commit=True) as (conn, cur):
        cur.execute("""
            SELECT a.studentid, q.createdby FROM attempts a
            JOIN quizzes q ON a.quizid = q.quizid WHERE a.attemptid = %s
        """, (attempt_id,))
        row = cur.fetchone()

        if not row or row[0] != user_id:
            flash("Invalid feedback token.", "error")
            return redirect(url_for('student_dashboard'))

        cur.execute("""
            INSERT INTO feedback (attemptid, teacherid, studentid, feedback, comments, createdat)
            VALUES (%s, %s, %s, %s, %s, NOW())
        """, (attempt_id, row[1], user_id, feedback_text, comments_text))

    flash("Thank you for your feedback!", "success")
    return redirect(url_for('student_dashboard'))
