from datetime import datetime, timedelta, timezone

from app.extensions import db
from app.models import Task, TaskAssignment, OnboardingAgent, Supervisor


def add_task(app, name, status='Assigned', offset=1, other=False):
    with app.app_context():
        agent = OnboardingAgent.query.filter_by(
            email='netease-13495@demo.invalid' if other else 'netease-6376@demo.invalid'
        ).one()
        supervisor = Supervisor.query.one()
        now = datetime.now(timezone(timedelta(hours=3))).replace(tzinfo=None)
        task = Task(task_type=name, description='Review the documents carefully.',
                    location='Nairobi', priority='High', status=status,
                    deadline=now + timedelta(days=offset) if offset is not None else None,
                    supervisor_id=supervisor.id)
        db.session.add(task)
        db.session.flush()
        assignment = TaskAssignment(task_id=task.id, agent_id=agent.id,
                                    supervisor_id=supervisor.id, status=status)
        db.session.add(assignment)
        db.session.commit()
        return assignment.id


def login(client, email='netease-6376@demo.invalid'):
    return client.post('/auth/login', data={'email': email, 'password': 'password123'})


def test_dashboard_scopes_counts_and_contents_to_signed_in_agent(app, client):
    add_task(app, 'My overdue work', offset=-1)
    add_task(app, 'My finished work', status='Completed', offset=-2)
    add_task(app, 'PRIVATE other worker task', other=True, offset=-1)
    login(client)
    page = client.get('/agent/dashboard').get_data(as_text=True)
    assert 'My overdue work' in page
    assert 'My finished work' in page
    assert 'PRIVATE' not in page
    assert '1 task needs attention.' in page
    assert '50%' in page
    assert '2 results' in page
    assert 'View task details' in page
    assert 'Review the documents carefully.' in page


def test_overdue_filter_excludes_completed_and_other_agents(app, client):
    add_task(app, 'Late open', offset=-1)
    add_task(app, 'Late closed', status='Completed', offset=-1)
    add_task(app, 'Other late', other=True, offset=-1)
    add_task(app, 'Future open', offset=1)
    login(client)
    page = client.get('/agent/dashboard?status=Overdue').get_data(as_text=True)
    assert 'Late open' in page
    assert all(name not in page for name in ['Late closed', 'Other late', 'Future open'])


def test_search_treats_wildcards_literally_and_keeps_filters_in_pagination(app, client):
    for i in range(11):
        add_task(app, f'Check 100% item {i}')
    add_task(app, 'Unrelated item')
    login(client)
    page = client.get('/agent/dashboard?q=%25&status=Active').get_data(as_text=True)
    assert '11 results' in page
    assert 'Page 1 of 2' in page
    assert 'Unrelated item' not in page
    assert 'q=%25' in page and 'status=Active' in page
    page2 = client.get('/agent/dashboard?page=2&q=%25&status=Active').get_data(as_text=True)
    assert 'Page 2 of 2' in page2
    assert '11 results' in page2


def test_dashboard_handles_empty_and_historical_missing_deadline(app, client):
    login(client)
    response = client.get('/agent/dashboard')
    assert response.status_code == 200
    assert b'No assignments yet' in response.data
    add_task(app, 'Historical assignment', offset=None)
    response = client.get('/agent/dashboard')
    assert response.status_code == 200
    assert b'Deadline not set' in response.data
    assert client.get('/static/css/agent-dashboard.css').status_code == 200


def test_agent_dashboard_requires_agent_role(app, client):
    assert client.get('/agent/dashboard').status_code == 302
    login(client, 'supervisor@test.com')
    response = client.get('/agent/dashboard')
    assert response.status_code == 302
    assert b'My assignments' not in response.data


def test_completion_updates_dashboard_and_hides_repeat_action(app, client):
    assignment_id = add_task(app, 'Finish this task')
    login(client)
    client.get('/agent/dashboard')
    with client.session_transaction() as session:
        data = {'task_progress_csrf_token': session['task_progress_csrf_token']}
    client.post(f'/agent/assignment/{assignment_id}/start', data=data)
    response = client.post(f'/agent/assignment/{assignment_id}/complete', data=data, follow_redirects=True)
    assert response.status_code == 200
    assert b'Work finished' in response.data
    assert b'Mark complete</button>' not in response.data
    assert b'100%' in response.data
    with app.app_context():
        assignment = db.session.get(TaskAssignment, assignment_id)
        assert assignment.status == assignment.task.status == 'Completed'
        assert assignment.agent.workload == 0
