from tests.conftest import login_helper
from database import db_session

def setup_approved_teacher(client, email='teacher1@faculty.annauniv.edu', password='pass'):
    # Register teacher
    client.post('/register', data={
        'name': 'Teacher One',
        'email': email,
        'password': password,
        'role': 'teacher',
        'class': 'CS101',
        'teacher_key': '1'
    }, follow_redirects=True)

    # Login as admin and approve teacher
    login_helper(client, 'admin@annauniv.edu', 'admin123')
    with db_session(commit=True) as (conn, cur):
        cur.execute("SELECT userid FROM users WHERE email=%s", (email,))
        tid = cur.fetchone()[0]
        cur.execute("UPDATE users SET approved=TRUE WHERE userid=%s", (tid,))

    client.get('/logout')
    login_helper(client, email, password)

def test_teacher_create_class_and_quiz(client):
    setup_approved_teacher(client)

    # Create class
    res = client.post('/create_class', data={
        'class_name': 'CS101',
        'subject': 'Data Structures'
    }, follow_redirects=True)
    assert b"Teacher Dashboard" in res.data or b"Class created successfully!" in res.data

    # Create quiz
    res = client.post('/create_quiz', data={
        'title': 'Data Structures Quiz 1',
        'description': 'Arrays & Linked Lists',
        'difficulty': 'Medium',
        'available_from': '2026-01-01T00:00',
        'available_to': '2026-12-31T23:59',
        'attempt_limit': '2',
        'class': 'CS101'
    }, follow_redirects=True)
    assert b"Quiz created as draft!" in res.data

    # Manage questions (Add question)
    res = client.post('/manage_questions/1', data={
        'question_text': 'What is the time complexity of array lookup by index?',
        'option_a': 'O(1)',
        'option_b': 'O(n)',
        'option_c': 'O(log n)',
        'option_d': 'O(n^2)',
        'correct_option': 'O(1)',
        'difficulty': 'Easy'
    }, follow_redirects=True)
    assert b"Question added!" in res.data

    # Publish quiz
    res = client.get('/publish_quiz/1', follow_redirects=True)
    assert b"Teacher Dashboard" in res.data

    # Verify in DB that quiz is published (isdraft == False)
    with db_session() as (conn, cur):
        cur.execute("SELECT isdraft FROM quizzes WHERE quizid=1")
        assert bool(cur.fetchone()[0]) is False
