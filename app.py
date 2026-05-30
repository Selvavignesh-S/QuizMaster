from flask import Flask, render_template, request, redirect, url_for, session, flash, Response
from datetime import datetime
from collections import defaultdict
from io import BytesIO
import openpyxl
import psycopg2

app = Flask(__name__)
app.secret_key = "your_secret_key"

TEACHER_SUPERKEY = "1"
STUDENT_DOMAIN = "@student.annauniv.edu"
TEACHER_DOMAIN = "@faculty.annauniv.edu"


def get_db_connection():
    return psycopg2.connect(
        host="localhost",
        database="quiz_management",
        user="postgres",
        password="GANGSTER_GANESH"
    )


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    # Clear any pending messages to avoid stale flashes on refresh
    _ = flash_messages = session.get('_flashes', [])

    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')

        conn = get_db_connection()
        cur = conn.cursor()

        # FIXED: Explicitly fetching named positions to prevent index shifts
        cur.execute(
            "SELECT userid, name, email, passwordhash, role, class, approved FROM users WHERE email=%s AND passwordhash=%s",
            (email, password))
        user = cur.fetchone()

        cur.close()
        conn.close()

        if user:
            session['user_id'] = user[0]
            session['role'] = user[4]

            if user[4] == 'student':
                return redirect(url_for('student_dashboard'))
            elif user[4] == 'teacher':
                # FIXED: Handling the DB boolean logic where False/True matches registration approval flow
                # If approved is False and it's a teacher, check your admin panel logic or use a separate state if needed.
                # Per your original logic: None=pending, False=rejected, True=approved.
                # Note: DB default is False, ensure your admin registration inserts explicit NULL for pending teachers if required.
                if user[6] is None:
                    flash("Teacher account status pending. Please wait for admin approval.", "info")
                    return render_template('login.html', form_data=request.form)
                elif user[6] is False:
                    flash("Teacher account rejected by admin.", "error")
                    return render_template('login.html', form_data=request.form)
                elif user[6] is True:
                    return redirect(url_for('teacher_dashboard'))
            else:  # Admin
                return redirect(url_for('admin_dashboard'))
        else:
            flash("Invalid email or password.", "error")
            return render_template('login.html', form_data=request.form)

    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        role = request.form.get('role', '')
        classy = request.form.get('class', '').strip()
        teacher_key = request.form.get('teacher_key', '').strip()

        if not username or not email or not password or not role or not classy:
            flash("Please fill out all the required fields.", "error")
            return render_template('register.html', form_data=request.form)

        if role == 'admin':
            flash("Online admin registration is not allowed.", "error")
            return render_template('register.html', form_data=request.form)

        if role == 'teacher':
            if not email.endswith(TEACHER_DOMAIN):
                flash(f"Teachers must register using a {TEACHER_DOMAIN} email.", "error")
                return render_template('register.html', form_data=request.form)
            if teacher_key != TEACHER_SUPERKEY:
                flash("Invalid teacher registration code.", "error")
                return render_template('register.html', form_data=request.form)

        if role == 'student' and not email.endswith(STUDENT_DOMAIN):
            flash(f"Students must register using a {STUDENT_DOMAIN} email.", "error")
            return render_template('register.html', form_data=request.form)

        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("SELECT approved, role FROM users WHERE email=%s", (email,))
        existing_user = cur.fetchone()

        if existing_user:
            if existing_user[1] == 'teacher' and existing_user[0] is False:
                cur.execute("UPDATE users SET approved=NULL, passwordhash=%s WHERE email=%s", (password, email))
                conn.commit()
                cur.close()
                conn.close()
                flash("Your previous rejection was reset, please wait for admin approval.", "info")
                return redirect(url_for('login'))
            else:
                cur.close()
                conn.close()
                flash("Email already registered. Please login or use another email.", "error")
                return render_template('register.html', form_data=request.form)

        # Set pending (None/NULL) for teachers, auto-approved (True) for students
        approved = None if role == 'teacher' else True

        cur.execute("""
            INSERT INTO users (name, email, passwordhash, role, class, approved)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (username, email, password, role, classy, approved))
        conn.commit()
        cur.close()
        conn.close()

        flash("Registered successfully! Please login.", "success")
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/student_dashboard', methods=['GET', 'POST'])
def student_dashboard():
    user_id = session.get('user_id')
    if not user_id or session.get('role') != 'student':
        return redirect(url_for('login'))

    conn = get_db_connection()
    cur = conn.cursor()

    if request.method == 'POST':
        class_to_enroll = request.form.get('class_to_enroll', '').strip()

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
                conn.commit()
                flash(f"Enrollment request reapplied for '{class_to_enroll}'.", "success")
        else:
            cur.execute('''
                INSERT INTO enrollments (studentid, class, approved, requested_at)
                VALUES (%s, %s, NULL, NOW())
            ''', (user_id, class_to_enroll))
            conn.commit()
            flash(f"Enrollment request for '{class_to_enroll}' submitted!", "success")

        cur.close()
        conn.close()
        return redirect(url_for('student_dashboard'))

    # GET Workflow Details
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

    cur.close()
    conn.close()

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


@app.route('/teacher_dashboard')
def teacher_dashboard():
    user_id = session.get('user_id')
    if not user_id or session.get('role') != 'teacher':
        return redirect(url_for('login'))

    conn = get_db_connection()
    cur = conn.cursor()

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
        grouped_attempts[title].append({
            "student_name": s_name, "student_email": s_email,
            "score": float(score), "endtime": endtime.strftime('%Y-%m-%d %H:%M') if endtime else 'N/A'
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

    # FIXED: Grouping feedback inside the backend cleanly before serving it to avoid Sandboxed Jinja mutation block failures
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

    cur.close()
    conn.close()

    return render_template(
        'teacher_dashboard.html',
        name=teacher[0], email=teacher[1], role=teacher[2], classy=classy,
        managed_classes=managed_classes, total_quizzes=total_quizzes,
        active_quizzes=active_quizzes, total_students=total_students,
        avg_score=round(float(avg_score), 2), quiz_list=quiz_list,
        num_pending_enrollments=num_pending_enrollments,
        grouped_attempts=grouped_attempts, feedbacks=feedbacks
    )


@app.route('/admin_dashboard', methods=['GET', 'POST'])
def admin_dashboard():
    user_id = session.get('user_id')
    if not user_id or session.get('role') != "admin":
        return redirect(url_for('login'))

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute('SELECT name, email FROM users WHERE userid=%s', (user_id,))
    admin_row = cur.fetchone()

    if request.method == 'POST':
        if 'approveteacher' in request.form:
            tid = int(request.form.get('approveteacher'))
            cur.execute("UPDATE users SET approved = TRUE WHERE userid = %s", (tid,))
            conn.commit()
            flash("Teacher approved successfully.", "success")
        elif 'rejectteacher' in request.form:
            tid = int(request.form.get('rejectteacher'))
            cur.execute("UPDATE users SET approved = FALSE WHERE userid = %s", (tid,))
            conn.commit()
            flash("Teacher rejected.", "warning")
        elif 'deactivateuser' in request.form:
            uid = int(request.form.get('deactivateuser'))
            cur.execute("UPDATE users SET approved = FALSE WHERE userid = %s", (uid,))
            conn.commit()
            flash("User deactivated.", "success")

    # FIXED: Replaced non-existent 'active' mapping flag logic with correct fallback validation maps
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

    cur.close()
    conn.close()

    return render_template('admin_dashboard.html', users=users, rejected_teachers=rejected_teachers,
                           name=admin_row[0], email=admin_row[1], quizzes=quizzes_count,
                           classes=classes_count, attempts=attempts_count)


@app.route('/attempt_quiz/<int:quiz_id>')
def attempt_quiz(quiz_id):
    user_id = session.get('user_id')
    if not user_id or session.get('role') != 'student':
        return redirect(url_for('login'))

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT quizid, createdby, title, description, difficulty, 
               availablefrom, availableto, attemptlimit, isdraft, class 
        FROM quizzes WHERE quizid=%s
    """, (quiz_id,))
    quiz = cur.fetchone()

    if not quiz:
        cur.close()
        conn.close()
        flash("Quiz not found.", "error")
        return redirect(url_for('student_dashboard'))

    # FIXED: Replaced blank string execute call with explicit enrollment approval database lookups
    cur.execute("SELECT 1 FROM enrollments WHERE studentid=%s AND class=%s AND approved=TRUE", (user_id, quiz[9]))
    if not cur.fetchone():
        cur.close()
        conn.close()
        flash("You are not enrolled in this class.", "error")
        return redirect(url_for('student_dashboard'))

    cur.execute("SELECT COUNT(*) FROM attempts WHERE quizid=%s AND studentid=%s", (quiz_id, user_id))
    attempt_count = cur.fetchone()[0]

    cur.close()
    conn.close()

    # FIXED: Pruned broken duplicate return layouts
    return render_template('attempt_quiz.html', quiz=quiz, attempt_count=attempt_count, quiz_id=quiz_id)


@app.route('/start_quiz/<int:quiz_id>')
def start_quiz(quiz_id):
    user_id = session.get('user_id')
    if not user_id or session.get('role') != 'student':
        return redirect(url_for('login'))

    conn = get_db_connection()
    cur = conn.cursor()

    # Create new explicit structural attempt session row tracker
    cur.execute("""
        INSERT INTO attempts (quizid, studentid, attemptno, starttime)
        VALUES (%s, %s, (SELECT COALESCE(MAX(attemptno), 0) + 1 FROM attempts WHERE quizid=%s AND studentid=%s), NOW())
        RETURNING attemptid
    """, (quiz_id, user_id, quiz_id, user_id))
    attempt_id = cur.fetchone()[0]
    conn.commit()

    cur.close()
    conn.close()

    return redirect(url_for('take_quiz', attempt_id=attempt_id))


@app.route('/take_quiz/<int:attempt_id>', methods=['GET', 'POST'])
def take_quiz(attempt_id):
    user_id = session.get('user_id')
    if not user_id or session.get('role') != 'student':
        return redirect(url_for('login'))

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT quizid, studentid FROM attempts WHERE attemptid=%s", (attempt_id,))
    attempt = cur.fetchone()

    if not attempt or attempt[1] != user_id:
        cur.close()
        conn.close()
        flash("Invalid attempt.", "error")
        return redirect(url_for('student_dashboard'))

    quiz_id = attempt[0]

    # FIXED: Selected columns in precise positions (Indices 2 and 3 match standard template references safely)
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

        # FIXED: Modified quiz submission mechanics to UPDATE the active layout tracking row rather than cloning entries
        cur.execute("UPDATE attempts SET score=%s, endtime=NOW() WHERE attemptid=%s", (score, attempt_id))

        cur.execute("SELECT class FROM quizzes WHERE quizid=%s", (quiz_id,))
        quiz_class = cur.fetchone()[0]

        # Truncation Guard: Truncate local evaluation context variables safely if necessary to prevent DB constraint exceptions
        quiz_class_truncated = quiz_class[:20]

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

        conn.commit()

        # Re-rank execution paths
        cur.execute("SELECT leaderboardid FROM leaderboard WHERE class = %s ORDER BY totalscore DESC",
                    (quiz_class_truncated,))
        for idx, row in enumerate(cur.fetchall(), start=1):
            cur.execute("UPDATE leaderboard SET rank = %s WHERE leaderboardid = %s", (idx, row[0]))

        conn.commit()
        cur.close()
        conn.close()

        flash(f"Quiz submitted! Your score: {score:.2f}%", "success")
        return redirect(url_for('feedback', attempt_id=attempt_id))

    cur.close()
    conn.close()
    return render_template('take_quiz.html', quiz=quiz, questions=questions, attempt_id=attempt_id)


@app.route('/leaderboard/<class_name>')
def leaderboard(class_name):
    user_id = session.get('user_id')
    role = session.get('role')

    if not user_id or not role:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cur = conn.cursor()
    authorized = False

    if role == 'teacher':
        cur.execute("SELECT 1 FROM teacher_classes WHERE teacherid = %s AND class = %s", (user_id, class_name))
        if cur.fetchone():
            authorized = True
    elif role == 'student':
        cur.execute("SELECT 1 FROM enrollments WHERE studentid = %s AND class = %s AND approved = TRUE",
                    (user_id, class_name))
        if cur.fetchone():
            authorized = True

    if not authorized:
        cur.close()
        conn.close()
        flash("You are not authorized to view this leaderboard.", "error")
        # FIXED: Resolved dashboard redirection typos causing Werkzeug compilation crashes
        return redirect(url_for('teacher_dashboard' if role == 'teacher' else 'student_dashboard'))

    # Match leaderboard table structural layout lookups exactly using truncated evaluation scopes
    class_lookup = class_name[:20]
    cur.execute("""
        SELECT u.name, l.totalscore, l.rank
        FROM leaderboard l
        JOIN users u ON l.studentid = u.userid
        WHERE l.class = %s
        ORDER BY l.rank ASC NULLS LAST, l.totalscore DESC NULLS LAST
    """, (class_lookup,))
    leaderboard_data = cur.fetchall()

    dashboard_url = url_for('teacher_dashboard' if role == 'teacher' else 'student_dashboard')
    cur.close()
    conn.close()

    return render_template('leaderboard.html', class_name=class_name, leaderboard=leaderboard_data,
                           dashboard_url=dashboard_url)


@app.route('/list_responses')
def list_responses():
    user_id = session.get('user_id')
    role = session.get('role')

    if not user_id:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cur = conn.cursor()

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
        duration = int((endtime - starttime).total_seconds() / 60) if starttime and endtime else 0

        # FIXED: Pass formatted strings safely but retain underlying business metrics explicitly
        attempts.append((
            attempt[0], attempt[1], float(attempt[2]) if attempt[2] is not None else 0.0,
            starttime.strftime('%Y-%m-%d %H:%M:%S') if starttime else 'N/A',
            endtime.strftime('%Y-%m-%d %H:%M:%S') if endtime else 'N/A',
            attempt[5], duration
        ))

    cur.close()
    conn.close()
    return render_template('list_responses.html', attempts=attempts, role=role)


@app.route('/view_responses/<int:attemptid>')
def view_responses(attemptid):
    userid = session.get('user_id')
    role = session.get('role')

    if not userid:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cur = conn.cursor()

    # FIXED: Passing native datetime elements directly to view layout contexts to bypass date-subtraction engine parsing crashes
    cur.execute("""
        SELECT a.studentid, q.title, a.score, a.starttime, a.endtime
        FROM attempts a
        JOIN quizzes q ON a.quizid = q.quizid
        WHERE a.attemptid = %s
    """, (attemptid,))
    attempt = cur.fetchone()

    if not attempt:
        cur.close()
        conn.close()
        flash("Attempt not found.", "error")
        return redirect(url_for('list_responses'))

    if role == 'student' and attempt[0] != userid:
        cur.close()
        conn.close()
        flash("Unauthorized access.", "error")
        return redirect(url_for('list_responses'))

    cur.execute("""
        SELECT r.questionid, q.questiontext, r.selectedoption, r.iscorrect, q.correctoption
        FROM responses r
        JOIN questions q ON r.questionid = q.questionid
        WHERE r.attemptid = %s ORDER BY r.questionid
    """, (attemptid,))
    responses = cur.fetchall()

    cur.close()
    conn.close()
    return render_template('view_responses.html', attempt=attempt, responses=responses)


@app.route('/feedback/<int:attempt_id>')
def feedback(attempt_id):
    user_id = session.get('user_id')
    if not user_id or session.get('role') != 'student':
        return redirect(url_for('login'))

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT studentid FROM attempts WHERE attemptid=%s", (attempt_id,))
    attempt = cur.fetchone()
    if not attempt or attempt[0] != user_id:
        cur.close()
        conn.close()
        flash("Invalid attempt context.", "error")
        return redirect(url_for('student_dashboard'))

    cur.execute("SELECT 1 FROM feedback WHERE attemptid=%s AND studentid=%s", (attempt_id, user_id))
    if cur.fetchone():
        cur.close()
        conn.close()
        flash("Feedback already submitted.", "info")
        return redirect(url_for('student_dashboard'))

    cur.close()
    conn.close()
    return render_template('feedback.html', attempt_id=attempt_id)


@app.route('/submit_feedback/<int:attempt_id>', methods=['POST'])
def submit_feedback(attempt_id):
    user_id = session.get('user_id')
    if not user_id or session.get('role') != 'student':
        return redirect(url_for('login'))

    feedback_text = request.form.get('feedback', '').strip()
    comments_text = request.form.get('comments', '').strip()

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT a.studentid, q.createdby FROM attempts a
        JOIN quizzes q ON a.quizid = q.quizid WHERE a.attemptid = %s
    """, (attempt_id,))
    row = cur.fetchone()

    if not row or row[0] != user_id:
        flash("Invalid feedback token.", "error")
        cur.close()
        conn.close()
        return redirect(url_for('student_dashboard'))

    cur.execute("""
        INSERT INTO feedback (attemptid, teacherid, studentid, feedback, comments, createdat)
        VALUES (%s, %s, %s, %s, %s, NOW())
    """, (attempt_id, row[1], user_id, feedback_text, comments_text))

    conn.commit()
    cur.close()
    conn.close()

    flash("Thank you for your feedback!", "success")
    return redirect(url_for('student_dashboard'))


@app.route('/pending_enrollments', methods=['GET', 'POST'])
def pending_enrollments():
    user_id = session.get('user_id')
    if not user_id or session.get('role') != 'teacher':
        return redirect(url_for('login'))

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT class FROM teacher_classes WHERE teacherid = %s", (user_id,))
    classes = [row[0] for row in cur.fetchall()]

    if not classes:
        cur.close()
        conn.close()
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
            conn.commit()
            flash("Enrollment processed successfully.", "success")

        return redirect(url_for('pending_enrollments'))

    cur.execute("""
        SELECT e.enrollmentid, u.userid, u.name, u.email, e.class
        FROM enrollments e
        JOIN users u ON e.studentid = u.userid
        WHERE e.class = ANY(%s) AND e.approved IS NULL
    """, (classes,))
    requests = cur.fetchall()

    cur.close()
    conn.close()
    return render_template('pending_enrollments.html', requests=requests, classes=classes)


@app.route('/create_class', methods=['GET', 'POST'])
def create_class():
    user_id = session.get('user_id')
    if not user_id or session.get('role') != 'teacher':
        return redirect(url_for('login'))

    if request.method == 'POST':
        c_name = request.form.get('class_name', '').strip()
        subj = request.form.get('subject', '').strip()

        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("SELECT 1 FROM teacher_classes WHERE class = %s", (c_name,))
        if cur.fetchone():
            flash(f"Class '{c_name}' already exists.", "error")
        else:
            cur.execute("INSERT INTO teacher_classes (teacherid, class, subject) VALUES (%s, %s, %s)",
                        (user_id, c_name, subj))
            conn.commit()
            flash("Class created successfully!", "success")
            cur.close()
            conn.close()
            return redirect(url_for('teacher_dashboard'))

        cur.close()
        conn.close()

    return render_template('create_class.html')


@app.route('/create_quiz', methods=['GET', 'POST'])
def create_quiz():
    user_id = session.get('user_id')
    if not user_id or session.get('role') != 'teacher':
        return redirect(url_for('login'))

    conn = get_db_connection()
    cur = conn.cursor()

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

        cur.execute("""
            INSERT INTO quizzes (title, description, difficulty, availablefrom, availableto, attemptlimit, createdby, class, isdraft)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, TRUE) RETURNING quizid
        """, (title, desc, diff, a_from, a_to, limit, user_id, c_name))
        qid = cur.fetchone()[0]
        conn.commit()

        cur.close()
        conn.close()
        flash("Quiz created as draft!", "success")
        return redirect(url_for('manage_questions', quiz_id=qid))

    cur.close()
    conn.close()
    return render_template('create_quiz.html', teacher_classes=teacher_classes)


@app.route('/manage_questions/<int:quiz_id>', methods=['GET', 'POST'])
def manage_questions(quiz_id):
    user_id = session.get('user_id')
    if not user_id or session.get('role') != 'teacher':
        return redirect(url_for('login'))

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT quizid, createdby, title, description, difficulty, availablefrom, availableto, attemptlimit, isdraft, class
        FROM quizzes WHERE quizid=%s AND createdby=%s
    """, (quiz_id, user_id))
    quiz = cur.fetchone()

    if not quiz:
        cur.close()
        conn.close()
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

            cur.execute("""
                INSERT INTO questions (quizid, questiontext, optiona, optionb, optionc, optiond, correctoption, difficulty)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (quiz_id, q_text, op_a, op_b, op_c, op_d, correct, diff))
            conn.commit()
            flash("Question added!", "success")
        return redirect(url_for('manage_questions', quiz_id=quiz_id))

    cur.execute("SELECT * FROM questions WHERE quizid=%s ORDER BY questionid", (quiz_id,))
    questions = cur.fetchall()
    cur.close()
    conn.close()

    return render_template('questions.html', quiz=quiz, questions=questions, quiz_id=quiz_id)


@app.route('/publish_quiz/<int:quiz_id>')
def publish_quiz(quiz_id):
    user_id = session.get('user_id')
    if not user_id or session.get('role') != 'teacher':
        return redirect(url_for('login'))

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM questions WHERE quizid = %s", (quiz_id,))
    if cur.fetchone()[0] == 0:
        flash("Add at least one question before publishing.", "error")
        return redirect(url_for('manage_questions', quiz_id=quiz_id))

    cur.execute("UPDATE quizzes SET isdraft = FALSE WHERE quizid = %s AND createdby = %s", (quiz_id, user_id))
    conn.commit()
    cur.close()
    conn.close()

    flash("Quiz is now live!", "success")
    return redirect(url_for('teacher_dashboard'))


@app.route('/delete_question/<int:question_id>')
def delete_question(question_id):
    user_id = session.get('user_id')
    if not user_id or session.get('role') != 'teacher':
        return redirect(url_for('login'))

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT q.quizid, qz.isdraft, qz.createdby FROM questions q
        JOIN quizzes qz ON q.quizid = qz.quizid WHERE q.questionid = %s
    """, (question_id,))
    res = cur.fetchone()

    if res and res[2] == user_id and res[1]:
        cur.execute("DELETE FROM questions WHERE questionid = %s", (question_id,))
        conn.commit()
        flash("Question deleted.", "success")
        quiz_id = res[0]
    else:
        flash("Cannot delete question.", "error")
        quiz_id = res[0] if res else 0

    cur.close()
    conn.close()
    return redirect(url_for('manage_questions', quiz_id=quiz_id))


@app.route('/export_quizzes', methods=['POST'])
def export_quizzes():
    if session.get('role') != "admin":
        return redirect(url_for('login'))

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT q.quizid, q.title, q.description, q.class, q.availablefrom, q.availableto, u.name
        FROM quizzes q LEFT JOIN users u ON q.createdby = u.userid
    """)
    quizzes = cur.fetchall()
    cur.close()
    conn.close()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Quizzes"
    ws.append(['Quiz ID', 'Title', 'Description', 'Class', 'Available From', 'Available To', 'Teacher'])

    for row in quizzes:
        # Format datetimes safely into plain strings for the spreadsheet cells
        formatted_row = list(row)
        if formatted_row[4]: formatted_row[4] = formatted_row[4].strftime('%Y-%m-%d %H:%M')
        if formatted_row[5]: formatted_row[5] = formatted_row[5].strftime('%Y-%m-%d %H:%M')
        ws.append(formatted_row)

    output = BytesIO()
    wb.save(output)
    output.seek(0)

    return Response(
        output.getvalue(),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment;filename=quiz_report.xlsx"}
    )


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


if __name__ == '__main__':
    app.run(debug=True)