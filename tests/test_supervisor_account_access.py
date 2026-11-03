from sqlalchemy import text

from app.extensions import db
from app.models import Supervisor, Task, TaskAssignment, OnboardingAgent


def login(client):
    return client.post('/auth/login', data={
        'email': 'supervisor@test.com', 'password': 'password123'})


def supervisor():
    return Supervisor.query.filter_by(email='supervisor@test.com').one()


def test_existing_supervisor_access_preserved(app, client):
    assert supervisor().account_disabled is False
    assert supervisor().is_active
    assert login(client).status_code == 302
    assert client.get('/supervisor/dashboard').status_code == 200


def test_disabled_supervisor_cannot_sign_in(app, client):
    record = supervisor()
    record.account_disabled = True
    db.session.commit()
    response = login(client)
    assert response.status_code == 200
    assert b'Invalid email or password' in response.data
    with client.session_transaction() as values:
        assert '_user_id' not in values


def test_existing_session_revoked_without_changing_task_records(app, client):
    record = supervisor()
    worker = OnboardingAgent.query.first()
    task = Task(task_type='Preserved task', supervisor_id=record.id, status='Assigned')
    db.session.add(task)
    db.session.flush()
    db.session.add(TaskAssignment(task_id=task.id, agent_id=worker.id,
                                  supervisor_id=record.id, status='Assigned'))
    db.session.commit()
    assert login(client).status_code == 302
    with app.app_context():
        assert client.get('/supervisor/dashboard').status_code == 200
    before = {table: tuple(db.session.execute(text(f'SELECT * FROM {table}')).all())
              for table in ('tasks', 'task_assignments', 'worker_source_bindings')}
    record.account_disabled = True
    db.session.commit()
    with app.app_context():
        response = client.get('/supervisor/dashboard')
    assert response.status_code == 302 and '/auth/login' in response.location
    with client.session_transaction() as values:
        assert '_user_id' not in values
    assert before == {table: tuple(db.session.execute(text(f'SELECT * FROM {table}')).all())
                      for table in before}
    record.account_disabled = False
    db.session.commit()
    with app.app_context():
        assert client.get('/supervisor/dashboard').status_code == 302
    assert login(client).status_code == 302
    assert client.get('/supervisor/dashboard').status_code == 200
