from datetime import datetime
from pathlib import Path
import json

import pytest
from sqlalchemy import text
from app.extensions import db
from app.models import OnboardingAgent, Supervisor, Task, TaskAssignment
from app.services.worker_display_names import worker_display_name
from app.services.worker_directory import directory_names


def login(client, email='admin@test.com'):
    return client.post('/auth/login', data={'email':email, 'password':'password123'})


def worker():
    return OnboardingAgent.query.filter_by(email='netease-6376@demo.invalid').one()


def add_assignment(agent, title, status='Assigned'):
    supervisor = Supervisor.query.first()
    task = Task(task_type=title, supervisor_id=supervisor.id, status=status)
    db.session.add(task)
    db.session.flush()
    db.session.add(TaskAssignment(task_id=task.id, agent_id=agent.id,
        supervisor_id=supervisor.id, status=status,
        started_at=datetime(2026, 10, 30, 7) if status == 'Completed' else None,
        completed_at=datetime(2026, 10, 30, 8) if status == 'Completed' else None))
    db.session.commit()


@pytest.mark.parametrize('email', ['supervisor@test.com', 'netease-6376@demo.invalid'])
def test_directory_and_profile_are_admin_only(app, client, email):
    login(client, email)
    assert client.get('/admin/workers').status_code == 403
    assert client.get(f'/admin/workers/{worker().id}').status_code == 403


def test_anonymous_redirect_and_post_rejected(app, client):
    assert client.get('/admin/workers').status_code == 302
    assert client.get(f'/admin/workers/{worker().id}').status_code == 302
    login(client)
    assert client.post('/admin/workers').status_code == 405
    assert client.post(f'/admin/workers/{worker().id}').status_code == 405
    assert client.get('/admin/workers/999999').status_code == 404


def test_search_by_alias_email_and_number_and_availability(app, client):
    login(client)
    name = worker_display_name('6376')
    for search in (name, 'NETEASE-6376@DEMO.INVALID', str(worker().id)):
        response = client.get('/admin/workers', query_string={'q':search, 'availability':'available'})
        assert response.status_code == 200 and name.encode() in response.data
        assert b'netease-13495@demo.invalid' not in response.data
    assert b'No workers found' in client.get('/admin/workers?q=%25').data
    response = client.get('/admin/workers?availability=unavailable')
    assert b'netease-13495@demo.invalid' in response.data
    assert b'netease-6376@demo.invalid' not in response.data


def test_profile_has_only_this_workers_tasks_and_correct_times(app, client):
    agent = worker()
    add_assignment(agent, 'My active assignment')
    add_assignment(agent, 'My finished assignment', 'Completed')
    other = OnboardingAgent.query.filter(OnboardingAgent.id != agent.id).first()
    add_assignment(other, 'OTHER WORKER PRIVATE TASK')
    agent.workload = 99  # Display actual assignments rather than a stale counter.
    db.session.commit()
    login(client)
    response = client.get(f'/admin/workers/{agent.id}')
    assert response.status_code == 200
    assert b'1 active task.' in response.data
    assert b'OTHER WORKER PRIVATE TASK' not in response.data
    assert b'Started 30 Oct 2026, 10:00 EAT' in response.data
    assert b'Completed 30 Oct 2026, 11:00 EAT' in response.data
    assert b'KYC Verification' in response.data
    filtered = client.get(f'/admin/workers/{agent.id}?status=Completed')
    assert b'My finished assignment' in filtered.data
    assert b'My active assignment' not in filtered.data
    assert agent.password_hash.encode() not in response.data


def test_pagination_retains_filters_and_empty_profile(app, client):
    for index in range(21):
        db.session.add(OnboardingAgent(name=f'Extra worker {index}', email=f'extra{index}@test.invalid',
            password_hash='disabled', availability=True))
    db.session.commit()
    login(client)
    response = client.get('/admin/workers?q=Extra&availability=available&page=2')
    assert response.status_code == 200 and b'Page 2 of 2' in response.data
    assert b'q=Extra' in response.data and b'availability=available' in response.data
    assert b'No assignments yet' in client.get(f'/admin/workers/{worker().id}').data


def test_views_do_not_change_records_or_bindings(app, client):
    path = Path(app.instance_path) / 'netease_agent_bindings.json'
    bindings_before = path.read_bytes()
    tables = [row[0] for row in db.session.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"))]
    def snapshot():
        return {table: sorted([tuple(row) for row in db.session.execute(text('SELECT * FROM "' + table + '"'))], key=repr) for table in tables}
    before = snapshot()
    login(client)
    client.get('/admin/dashboard')
    client.get('/admin/workers')
    client.get(f'/admin/workers/{worker().id}')
    assert snapshot() == before and path.read_bytes() == bindings_before


def test_invalid_or_duplicate_mapping_falls_back_to_stored_names(app):
    path = Path(app.instance_path) / 'netease_agent_bindings.json'
    path.write_text('{broken', encoding='utf-8')
    assert directory_names()[worker().id] == worker().name
    agents = OnboardingAgent.query.all()
    path.write_text(json.dumps({'schema_version':1, 'status':'ready',
        'worker_bindings':{str(agent.id):'6376' for agent in agents}}), encoding='utf-8')
    assert directory_names()[worker().id] == worker().name


def test_unmapped_worker_content_is_escaped(app, client):
    agent = OnboardingAgent(name='<script>alert(1)</script>', email='new@test.invalid', password_hash='disabled')
    db.session.add(agent)
    db.session.commit()
    login(client)
    response = client.get(f'/admin/workers/{agent.id}')
    assert b'<script>alert(1)</script>' not in response.data
    assert b'&lt;script&gt;' in response.data


def test_database_bindings_require_matching_identity(app):
    from app.models import WorkerSourceBinding
    app.config['NETEASE_BINDING_STORAGE'] = 'database'
    agent = worker()
    db.session.add(WorkerSourceBinding(agent_id=agent.id, source_worker_id='6376'))
    db.session.commit()
    assert directory_names()[agent.id] == worker_display_name('6376')
    agent.email = 'different-person@test.invalid'
    db.session.commit()
    assert directory_names()[agent.id] == agent.name


def test_profile_pagination_and_navigation(app, client):
    agent = worker()
    for index in range(11):
        add_assignment(agent, f'Finished job {index}', 'Completed')
    login(client)
    response = client.get(f'/admin/workers/{agent.id}?status=Completed&page=2')
    assert b'Page 2 of 2' in response.data and b'status=Completed' in response.data
    assert b'aria-current="page"' in response.data
    assert b'data-role="administrator"' in response.data
    assert b'admin-workers.css' in response.data
    assert client.get('/static/css/admin-workers.css').status_code == 200
    assert b'href="/admin/workers"' in client.get('/admin/dashboard').data
