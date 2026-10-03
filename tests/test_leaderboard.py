from tests.conftest import login_helper
from tests.test_student import test_student_full_quiz_attempt_flow

def test_leaderboard_access_and_ranks(client):
    # Execute full student quiz attempt to seed leaderboard entry
    test_student_full_quiz_attempt_flow(client)

    # Login as student (Alice)
    login_helper(client, 'alice@student.annauniv.edu', 'pass')

    # View leaderboard for CS101
    res = client.get('/leaderboard/CS101')
    assert res.status_code == 200
    assert b"Leaderboard" in res.data or b"CS101" in res.data
    assert b"Alice Student" in res.data

    # View leaderboard for un-enrolled class (CS999) -> Unauthorized redirect
    res = client.get('/leaderboard/CS999', follow_redirects=True)
    assert res.status_code == 200
    assert b"Student Dashboard" in res.data or b"You are not authorized" in res.data
