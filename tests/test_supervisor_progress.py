from datetime import datetime, timedelta, timezone

from app.extensions import db
from app.models import Task, TaskAssignment, Supervisor, OnboardingAgent
from test_dashboard_overview import contexts, login
from test_start_task import prepare


def add_task(title, status, owner=None, started=None, completed=None, deadline=None):
    owner = owner or Supervisor.query.filter_by(email='supervisor@test.com').one()
    task = Task(task_type=title, status=status, supervisor_id=owner.id,
                deadline=deadline, priority='Medium', location='Nairobi')
    db.session.add(task)
    db.session.flush()
    if status != 'Pending':
        db.session.add(TaskAssignment(task_id=task.id, supervisor_id=owner.id,
            agent_id=OnboardingAgent.query.first().id, status=status,
            started_at=started, completed_at=completed))
    db.session.commit()
    return task.id


def test_progress_totals_chart_and_overdue_are_owner_scoped(app, client):
    now = datetime.now(timezone(timedelta(hours=3))).replace(tzinfo=None)
    for status in ['Pending', 'Assigned', 'In progress', 'Completed']:
        add_task('Owned ' + status, status, deadline=now - timedelta(days=1))
    other = Supervisor(name='Other owner', email='other-progress@test.com')
    other.set_password('password123')
    db.session.add(other)
    db.session.commit()
    add_task('PRIVATE progress', 'In progress', owner=other, started=datetime(2026, 1, 1, 7))
    login(client)
    with contexts(app) as captured:
        response = client.get('/supervisor/dashboard')
    result = captured[-1]
    assert result['total_tasks'] == 4
    assert [result[k] for k in ('pending_tasks','assigned_tasks','in_progress_tasks','completed_tasks')] == [1,1,1,1]
    assert result['other_tasks'] == 0 and result['overdue_tasks'] == 3
    assert [result[k] for k in ('completed_end','in_progress_end','assigned_end','pending_end')] == [25,50,75,100]
    assert b'PRIVATE progress' not in response.data
    assert b'1 in progress' in response.data
    assert b'supervisor-progress.css' in response.data


def test_progress_filter_search_and_pagination_preserve_totals(app, client):
    for index in range(11):
        add_task(f'Working 100% {index}', 'In progress')
    add_task('Waiting task', 'Pending')
    login(client)
    with contexts(app) as captured:
        response = client.get('/supervisor/dashboard', query_string={'q':'%', 'status':'In progress', 'page':2})
    result = captured[-1]
    assert result['task_page'].total == 11 and len(result['task_page'].items) == 1
    assert result['total_tasks'] == 12 and result['in_progress_tasks'] == 11
    assert b'Waiting task' not in response.data
    assert b'status=In+progress' in response.data and b'q=%25' in response.data


def test_known_times_use_kenya_time_and_historical_times_are_not_invented(app, client):
    recorded = add_task('Recorded completion', 'Completed',
                        started=datetime(2026, 10, 30, 7, 15), completed=datetime(2026, 10, 30, 8, 20))
    historical = add_task('Historical completion', 'Completed')
    login(client)
    with contexts(app) as captured:
        response = client.get('/supervisor/dashboard')
    assert b'Started 30 Oct 2026, 10:15 EAT' in response.data
    assert b'Completed 30 Oct 2026, 11:20 EAT' in response.data
    assert captured[-1]['progress_details'][historical] == [{'started': None, 'completed': None}]
    assert captured[-1]['progress_details'][recorded][0]['started'] == '30 Oct 2026, 10:15'


def test_worker_actions_update_supervisor_totals_and_times(app, client):
    assignment_id, _, data = prepare(client)
    supervisor_client = app.test_client()
    # This suite keeps an outer app context alive. Give each browser request
    # its own context, as production does, so Flask-Login's cached user cannot
    # leak between the two independently authenticated test clients.
    with app.app_context():
        login(supervisor_client)
    def visit(browser, path, data=None):
        with app.app_context():
            return browser.get(path) if data is None else browser.post(path, data=data)
    with contexts(app) as captured:
        visit(supervisor_client, '/supervisor/dashboard')
    assert captured[-1]['assigned_tasks'] == 1 and captured[-1]['in_progress_tasks'] == 0
    assert visit(client, f'/agent/assignment/{assignment_id}/start', data=data).status_code == 302
    with contexts(app) as captured:
        response = visit(supervisor_client, '/supervisor/dashboard')
    assert captured[-1]['assigned_tasks'] == 0 and captured[-1]['in_progress_tasks'] == 1
    assert b'Started ' in response.data
    assert visit(client, f'/agent/assignment/{assignment_id}/complete', data=data).status_code == 302
    with contexts(app) as captured:
        response = visit(supervisor_client, '/supervisor/dashboard')
    assert captured[-1]['in_progress_tasks'] == 0 and captured[-1]['completed_tasks'] == 1
    assert captured[-1]['completion_percent'] == 100
    assert b'Completed ' in response.data


def test_empty_dashboard_and_progress_asset(app, client):
    login(client)
    with contexts(app) as captured:
        response = client.get('/supervisor/dashboard?status=In+progress')
    assert response.status_code == 200
    assert captured[-1]['in_progress_tasks'] == 0
    assert captured[-1]['progress_details'] == {}
    assert client.get('/static/css/supervisor-progress.css').status_code == 200
