from tests.conftest import login_helper
from database import db_session

def test_admin_teacher_approvals_and_export(client):
    # Register teacher
    client.post('/register', data={
        'name': 'Pending Teacher',
        'email': 'pending@faculty.annauniv.edu',
        'password': 'pass',
        'role': 'teacher',
        'class': 'CS102',
        'teacher_key': '1'
    }, follow_redirects=True)

    # Login as admin
    login_helper(client, 'admin@annauniv.edu', 'admin123')

    # View dashboard
    res = client.get('/admin_dashboard')
    assert b"Admin Dashboard" in res.data
    assert b"Pending Teacher" in res.data

    # Get teacher ID from DB
    with db_session() as (conn, cur):
        cur.execute("SELECT userid FROM users WHERE email='pending@faculty.annauniv.edu'")
        tid = cur.fetchone()[0]

    # Approve teacher
    res = client.post('/admin_dashboard', data={'approveteacher': str(tid)}, follow_redirects=True)
    assert res.status_code == 200

    # Verify teacher is approved in DB
    with db_session() as (conn, cur):
        cur.execute("SELECT approved FROM users WHERE userid=%s", (tid,))
        assert bool(cur.fetchone()[0]) is True

    # Deactivate user
    res = client.post('/admin_dashboard', data={'deactivateuser': str(tid)}, follow_redirects=True)
    assert res.status_code == 200

    # Verify teacher is deactivated in DB
    with db_session() as (conn, cur):
        cur.execute("SELECT approved FROM users WHERE userid=%s", (tid,))
        assert bool(cur.fetchone()[0]) is False

    # Test export quizzes endpoint
    res = client.post('/export_quizzes')
    assert res.status_code == 200
    assert res.mimetype == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
