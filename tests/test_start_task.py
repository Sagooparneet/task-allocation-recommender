import pytest
from app.extensions import db
from app.models import Task, TaskAssignment, Supervisor, OnboardingAgent


def prepare(client, status='Assigned', other_owner=False):
    client.post('/auth/login', data={'email': 'netease-6376@demo.invalid', 'password': 'password123'})
    agent = OnboardingAgent.query.filter_by(email='netease-13495@demo.invalid' if other_owner else 'netease-6376@demo.invalid').one()
    supervisor = Supervisor.query.first()
    task = Task(task_type='Start test', supervisor_id=supervisor.id, status=status)
    db.session.add(task)
    db.session.flush()
    assignment = TaskAssignment(task_id=task.id, agent_id=agent.id, supervisor_id=supervisor.id, status=status)
    db.session.add(assignment)
    db.session.commit()
    assignment_id, workload = assignment.id, agent.workload
    client.get('/agent/dashboard')
    with client.session_transaction() as session:
        token = session['task_progress_csrf_token']
    return assignment_id, workload, {'task_progress_csrf_token': token}


def test_start_is_repeat_safe_and_keeps_workload(app, client):
    assignment_id, workload, data = prepare(client)
    response = client.post(f'/agent/assignment/{assignment_id}/start', data=data, follow_redirects=True)
    db.session.expire_all()
    saved = db.session.get(TaskAssignment, assignment_id)
    first = saved.started_at
    assert first is not None
    assert saved.status == saved.task.status == 'In progress'
    assert saved.agent.workload == workload
    assert saved.completed_at is None
    assert b'Started ' in response.data and b'EAT' in response.data
    client.post(f'/agent/assignment/{assignment_id}/start', data=data)
    db.session.expire_all()
    assert saved.started_at == first and saved.agent.workload == workload
    assert b'Start test' in client.get('/agent/dashboard?status=In+progress').data
    assert b'Start test' not in client.get('/agent/dashboard?status=Assigned').data


@pytest.mark.parametrize('status', ['Completed', 'Pending'])
def test_invalid_status_cannot_start(app, client, status):
    assignment_id, workload, data = prepare(client, status=status)
    client.post(f'/agent/assignment/{assignment_id}/start', data=data)
    db.session.expire_all()
    saved = db.session.get(TaskAssignment, assignment_id)
    assert saved.status == saved.task.status == status
    assert saved.started_at is None and saved.agent.workload == workload


def test_another_workers_assignment_is_rejected(app, client):
    assignment_id, _, data = prepare(client, other_owner=True)
    assert client.post(f'/agent/assignment/{assignment_id}/start', data=data).status_code == 404
    db.session.expire_all()
    assert db.session.get(TaskAssignment, assignment_id).started_at is None


def test_start_requires_valid_token(app, client):
    assignment_id, _, _ = prepare(client)
    assert client.post(f'/agent/assignment/{assignment_id}/start').status_code == 400
    assert client.post(f'/agent/assignment/{assignment_id}/start', data={'task_progress_csrf_token': 'wrong'}).status_code == 400
    assert db.session.get(TaskAssignment, assignment_id).started_at is None


def test_supervisor_cannot_start_worker_assignment(app, client):
    assignment_id, _, data = prepare(client)
    client.get('/auth/logout')
    client.post('/auth/login', data={'email': 'supervisor@test.com', 'password': 'password123'})
    assert client.post(f'/agent/assignment/{assignment_id}/start', data=data).status_code == 403


def test_mismatched_assignment_rolls_back_task_status(app, client):
    assignment_id, _, data = prepare(client)
    assignment = db.session.get(TaskAssignment, assignment_id)
    assignment.status = 'Completed'
    db.session.commit()
    client.post(f'/agent/assignment/{assignment_id}/start', data=data)
    db.session.expire_all()
    assert assignment.task.status == 'Assigned'
    assert assignment.status == 'Completed' and assignment.started_at is None
