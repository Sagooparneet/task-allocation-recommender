from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

from flask import template_rendered
from app.extensions import db
from app.models import Task, Supervisor


def login(client):
    client.post('/auth/login', data={'email': 'supervisor@test.com', 'password': 'password123'})


@contextmanager
def contexts(app):
    captured = []
    def record(sender, template, context, **extra):
        if template.name == 'supervisor/dashboard.html':
            captured.append(context)
    template_rendered.connect(record, app)
    try:
        yield captured
    finally:
        template_rendered.disconnect(record, app)


def test_overview_counts_and_list_are_owner_scoped(app, client):
    now = datetime.now(timezone(timedelta(hours=3))).replace(tzinfo=None)
    with app.app_context():
        owner = Supervisor.query.first()
        other = Supervisor(name='Another supervisor', email='another@test.com')
        other.set_password('password123')
        db.session.add(other)
        db.session.flush()
        for title, status, deadline, supervisor_id in [
            ('Your waiting task', 'Pending', now - timedelta(days=1), owner.id),
            ('Your assigned task', 'Assigned', now + timedelta(days=1), owner.id),
            ('Your completed task', 'Completed', now - timedelta(days=1), owner.id),
            ('Private task belonging to someone else', 'Pending', now - timedelta(days=1), other.id),
        ]:
            db.session.add(Task(task_type=title, status=status, deadline=deadline,
                                location='Nairobi', priority='High', supervisor_id=supervisor_id))
        db.session.commit()
    login(client)
    with contexts(app) as results:
        response = client.get('/supervisor/dashboard')
    context = results[-1]
    assert context['total_tasks'] == 3
    assert context['pending_tasks'] == context['assigned_tasks'] == context['completed_tasks'] == 1
    assert context['overdue_tasks'] == 1
    assert context['priorities'] == {'High': 3}
    assert b'Private task belonging' not in response.data
    assert len(context['task_page'].items) == 3


def test_search_status_and_pagination(app, client):
    with app.app_context():
        owner = Supervisor.query.first()
        for i in range(12):
            db.session.add(Task(task_type=f'Findable task {i}', location='Nairobi',
                                status='Pending', supervisor_id=owner.id))
        db.session.add(Task(task_type='Special 100% task', location='Nairobi',
                            status='Completed', supervisor_id=owner.id))
        db.session.commit()
    login(client)
    with contexts(app) as results:
        client.get('/supervisor/dashboard?status=Pending&page=2')
    assert len(results[-1]['task_page'].items) == 2
    assert results[-1]['task_page'].total == 12
    with contexts(app) as results:
        client.get('/supervisor/dashboard', query_string={'q': '%', 'status': 'Completed'})
    assert results[-1]['task_page'].total == 1
    assert results[-1]['task_page'].items[0].task_type == 'Special 100% task'
    with contexts(app) as results:
        client.get('/supervisor/dashboard', query_string={'q': 'No such task'})
    assert results[-1]['task_page'].total == 0


def test_empty_overview_renders_without_fake_counts(app, client):
    login(client)
    with contexts(app) as results:
        response = client.get('/supervisor/dashboard')
    assert response.status_code == 200
    assert results[-1]['total_tasks'] == results[-1]['completion_percent'] == 0
    assert b'Your next task starts here' in response.data
    assert b'Your progress will appear' in response.data


def test_theme_assets_and_role_navigation(client):
    response = client.get('/auth/login')
    assert b'intellitask-mark.svg' in response.data
    assert b'autocomplete="current-password"' in response.data
    for path in ['css/intellitask-theme.css', 'js/intellitask-ui.js', 'img/intellitask-mark.svg']:
        assert client.get('/static/' + path).status_code == 200
    client.post('/auth/login', data={'email': 'netease-6376@demo.invalid', 'password': 'password123'})
    page = client.get('/agent/dashboard').data
    assert b'My tasks' in page
    assert b'href="/supervisor/task/create"' not in page
