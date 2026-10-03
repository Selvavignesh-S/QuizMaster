from tests.conftest import login_helper

def test_admin_default_login(client):
    res = login_helper(client, 'admin@annauniv.edu', 'admin123')
    assert res.status_code == 200
    assert b"Admin Dashboard" in res.data or b"Super Admin" in res.data or b"quizzes" in res.data.lower()

def test_student_registration_and_login(client):
    # Register valid student
    res = client.post('/register', data={
        'name': 'John Student',
        'email': 'john@student.annauniv.edu',
        'password': 'password123',
        'role': 'student',
        'class': 'CS101'
    }, follow_redirects=True)
    assert b"Registered successfully!" in res.data

    # Login as student
    res = login_helper(client, 'john@student.annauniv.edu', 'password123')
    assert res.status_code == 200
    assert b"Student Dashboard" in res.data or b"John Student" in res.data

def test_student_registration_invalid_domain(client):
    res = client.post('/register', data={
        'name': 'Bad Student',
        'email': 'bad@gmail.com',
        'password': 'password123',
        'role': 'student',
        'class': 'CS101'
    }, follow_redirects=True)
    assert b"Students must register using a @student.annauniv.edu email" in res.data

def test_teacher_registration_pending_approval(client):
    # Register teacher with superkey
    res = client.post('/register', data={
        'name': 'Prof Smith',
        'email': 'smith@faculty.annauniv.edu',
        'password': 'teacherpass',
        'role': 'teacher',
        'class': 'CS101',
        'teacher_key': '1'
    }, follow_redirects=True)
    assert b"Registered successfully!" in res.data

    # Attempt teacher login (should show pending status)
    res = login_helper(client, 'smith@faculty.annauniv.edu', 'teacherpass')
    assert b"Teacher account status pending" in res.data

def test_teacher_registration_invalid_key(client):
    res = client.post('/register', data={
        'name': 'Fake Teacher',
        'email': 'fake@faculty.annauniv.edu',
        'password': 'teacherpass',
        'role': 'teacher',
        'class': 'CS101',
        'teacher_key': 'wrong_key'
    }, follow_redirects=True)
    assert b"Invalid teacher registration code" in res.data

def test_logout(client):
    login_helper(client, 'admin@annauniv.edu', 'admin123')
    res = client.get('/logout', follow_redirects=True)
    assert b"Please log in" in res.data or b"Login" in res.data
