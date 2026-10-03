from tests.conftest import login_helper
from tests.test_teacher import setup_approved_teacher
from database import db_session

def test_student_full_quiz_attempt_flow(client):
    # 1. Setup teacher and published quiz
    setup_approved_teacher(client)
    client.post('/create_class', data={'class_name': 'CS101', 'subject': 'Algorithms'}, follow_redirects=True)
    client.post('/create_quiz', data={
        'title': 'Algo Quiz',
        'description': 'Sorting',
        'difficulty': 'Easy',
        'available_from': '2026-01-01T00:00',
        'available_to': '2026-12-31T23:59',
        'attempt_limit': '1',
        'class': 'CS101'
    }, follow_redirects=True)
    client.post('/manage_questions/1', data={
        'question_text': 'Which sorting algorithm is O(n log n)?',
        'option_a': 'Merge Sort',
        'option_b': 'Bubble Sort',
        'option_c': 'Selection Sort',
        'option_d': 'Insertion Sort',
        'correct_option': 'Merge Sort',
        'difficulty': 'Easy'
    }, follow_redirects=True)
    client.get('/publish_quiz/1')
    client.get('/logout')

    # 2. Register Student & Request Enrollment
    client.post('/register', data={
        'name': 'Alice Student',
        'email': 'alice@student.annauniv.edu',
        'password': 'pass',
        'role': 'student',
        'class': 'CS101'
    }, follow_redirects=True)
    login_helper(client, 'alice@student.annauniv.edu', 'pass')

    # Enroll in CS101
    res = client.post('/student_dashboard', data={'class_to_enroll': 'CS101'}, follow_redirects=True)
    assert b"Student Dashboard" in res.data
    
    # Verify enrollment created in DB (pending approval)
    with db_session() as (conn, cur):
        cur.execute("SELECT approved FROM enrollments WHERE class='CS101'")
        assert cur.fetchone()[0] is None

    client.get('/logout')

    # 3. Teacher approves enrollment
    login_helper(client, 'teacher1@faculty.annauniv.edu', 'pass')
    res = client.post('/pending_enrollments', data={'enrollment_id': '1', 'action': 'approve'}, follow_redirects=True)
    
    # Verify enrollment approved in DB
    with db_session() as (conn, cur):
        cur.execute("SELECT approved FROM enrollments WHERE enrollmentid=1")
        assert bool(cur.fetchone()[0]) is True

    client.get('/logout')

    # 4. Student attempts & takes quiz
    login_helper(client, 'alice@student.annauniv.edu', 'pass')
    res = client.get('/attempt_quiz/1', follow_redirects=True)
    assert b"Algo Quiz" in res.data

    # Start quiz
    res = client.get('/start_quiz/1', follow_redirects=True)
    assert b"Which sorting algorithm" in res.data

    # Submit quiz answers
    res = client.post('/take_quiz/1', data={'question_1': 'Merge Sort'}, follow_redirects=True)
    assert res.status_code == 200

    # Verify attempt score in DB (100%)
    with db_session() as (conn, cur):
        cur.execute("SELECT score FROM attempts WHERE attemptid=1")
        assert float(cur.fetchone()[0]) == 100.0

    # 5. Submit feedback
    res = client.post('/submit_feedback/1', data={
        'feedback': 'Great quiz!',
        'comments': 'Very clear questions.'
    }, follow_redirects=True)
    assert b"Student Dashboard" in res.data

    # Verify feedback saved in DB
    with db_session() as (conn, cur):
        cur.execute("SELECT feedback, comments FROM feedback WHERE attemptid=1")
        fb = cur.fetchone()
        assert fb[0] == 'Great quiz!'
        assert fb[1] == 'Very clear questions.'

    # 6. View list responses & response details
    res = client.get('/list_responses')
    assert b"Algo Quiz" in res.data

    res = client.get('/view_responses/1')
    assert b"Merge Sort" in res.data
