from datetime import datetime, timedelta, timezone
import pytest
from app.extensions import db
from app.models import TaskAssignment
from test_start_task import prepare


def reload_assignment(assignment_id):
    db.session.expire_all()
    return db.session.get(TaskAssignment, assignment_id)


def test_completion_records_time_and_repeated_request_changes_nothing(app, client):
    assignment_id, workload, data = prepare(client)
    client.post(f'/agent/assignment/{assignment_id}/start', data=data)
    started = reload_assignment(assignment_id).started_at
    response = client.post(f'/agent/assignment/{assignment_id}/complete', data=data, follow_redirects=True)
    saved = reload_assignment(assignment_id)
    finished = saved.completed_at
    assert finished is not None and finished >= started
    assert saved.status == saved.task.status == 'Completed'
    assert saved.agent.workload == max(0, workload - 1)
    expected = (finished + timedelta(hours=3)).strftime('%d %b %Y, %H:%M')
    assert f'Completed {expected} EAT'.encode() in response.data
    assert b'Mark complete' not in response.data and b'Start task' not in response.data
    client.post(f'/agent/assignment/{assignment_id}/complete', data=data)
    client.post(f'/agent/assignment/{assignment_id}/start', data=data)
    saved = reload_assignment(assignment_id)
    assert (saved.started_at, saved.completed_at) == (started, finished)
    assert saved.agent.workload == max(0, workload - 1)
    assert b'Start test' in client.get('/agent/dashboard?status=Completed').data
    assert b'Start test' not in client.get('/agent/dashboard?status=Active').data


@pytest.mark.parametrize('status', ['Assigned', 'Pending', 'Completed'])
def test_completion_refuses_unstarted_or_historical_completed_tasks(app, client, status):
    assignment_id, workload, data = prepare(client, status=status)
    client.post(f'/agent/assignment/{assignment_id}/complete', data=data)
    saved = reload_assignment(assignment_id)
    assert saved.status == saved.task.status == status
    assert saved.started_at is None and saved.completed_at is None
    assert saved.agent.workload == workload


@pytest.mark.parametrize('token', [None, 'invalid'])
def test_completion_requires_token(app, client, token):
    assignment_id, workload, data = prepare(client)
    client.post(f'/agent/assignment/{assignment_id}/start', data=data)
    supplied = {} if token is None else {'task_progress_csrf_token': token}
    assert client.post(f'/agent/assignment/{assignment_id}/complete', data=supplied).status_code == 400
    saved = reload_assignment(assignment_id)
    assert saved.status == saved.task.status == 'In progress'
    assert saved.completed_at is None and saved.agent.workload == workload


def test_completion_rejects_other_owner_and_wrong_role(app, client):
    assignment_id, workload, data = prepare(client, other_owner=True)
    assert client.post(f'/agent/assignment/{assignment_id}/complete', data=data).status_code == 404
    client.get('/auth/logout')
    client.post('/auth/login', data={'email': 'supervisor@test.com', 'password': 'password123'})
    assert client.post(f'/agent/assignment/{assignment_id}/complete', data=data).status_code == 403
    saved = reload_assignment(assignment_id)
    assert saved.completed_at is None and saved.agent.workload == workload


@pytest.mark.parametrize('bad_start', [None, 'future'])
def test_invalid_start_time_rolls_back_task_completion(app, client, bad_start):
    assignment_id, workload, data = prepare(client, status='In progress')
    saved = reload_assignment(assignment_id)
    if bad_start == 'future':
        saved.started_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=1)
        db.session.commit()
    client.post(f'/agent/assignment/{assignment_id}/complete', data=data)
    saved = reload_assignment(assignment_id)
    assert saved.status == saved.task.status == 'In progress'
    assert saved.completed_at is None and saved.agent.workload == workload


def test_completion_is_post_only(app, client):
    assignment_id, _, _ = prepare(client)
    assert client.get(f'/agent/assignment/{assignment_id}/complete').status_code == 405
