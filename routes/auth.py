from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from database import db_session
from config import Config

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'], endpoint='login')
def login():
    # Clear any pending messages to avoid stale flashes on refresh
    _ = session.get('_flashes', [])

    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')

        with db_session() as (conn, cur):
            cur.execute(
                "SELECT userid, name, email, passwordhash, role, class, approved FROM users WHERE email=%s AND passwordhash=%s",
                (email, password)
            )
            user = cur.fetchone()

        if user:
            session['user_id'] = user[0]
            session['role'] = user[4]

            if user[4] == 'student':
                return redirect(url_for('student_dashboard'))
            elif user[4] == 'teacher':
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


@auth_bp.route('/register', methods=['GET', 'POST'], endpoint='register')
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
            if not email.endswith(Config.TEACHER_DOMAIN):
                flash(f"Teachers must register using a {Config.TEACHER_DOMAIN} email.", "error")
                return render_template('register.html', form_data=request.form)
            if teacher_key != Config.TEACHER_SUPERKEY:
                flash("Invalid teacher registration code.", "error")
                return render_template('register.html', form_data=request.form)

        if role == 'student' and not email.endswith(Config.STUDENT_DOMAIN):
            flash(f"Students must register using a {Config.STUDENT_DOMAIN} email.", "error")
            return render_template('register.html', form_data=request.form)

        with db_session(commit=True) as (conn, cur):
            cur.execute("SELECT approved, role FROM users WHERE email=%s", (email,))
            existing_user = cur.fetchone()

            if existing_user:
                if existing_user[1] == 'teacher' and existing_user[0] is False:
                    cur.execute("UPDATE users SET approved=NULL, passwordhash=%s WHERE email=%s", (password, email))
                    flash("Your previous rejection was reset, please wait for admin approval.", "info")
                    return redirect(url_for('login'))
                else:
                    flash("Email already registered. Please login or use another email.", "error")
                    return render_template('register.html', form_data=request.form)

            # Set pending (None/NULL) for teachers, auto-approved (True) for students
            approved = None if role == 'teacher' else True

            cur.execute("""
                INSERT INTO users (name, email, passwordhash, role, class, approved)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (username, email, password, role, classy, approved))

        flash("Registered successfully! Please login.", "success")
        return redirect(url_for('login'))

    return render_template('register.html')


@auth_bp.route('/logout', endpoint='logout')
def logout():
    session.clear()
    return redirect(url_for('login'))
