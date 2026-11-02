from datetime import datetime, timedelta

import pytest

from app.extensions import db
from app.models import Task, TaskAssignment, Supervisor, OnboardingAgent
import app.services.supervisor_reports as reports
from flask import template_rendered


NOW = datetime(2026, 11, 5, 12, 0)


@pytest.fixture(autouse=True)
def fixed_report_clock(monkeypatch):
    monkeypatch.setattr(reports, 'kenya_now', lambda: NOW)


def login(client, email='supervisor@test.com'):
    with client.application.app_context():
        return client.post('/auth/login', data={'email': email, 'password': 'password123'})


def get_report(app, client, **query):
    captured = []
    def record(sender, template, context, **extra):
        if template.name == 'supervisor/reports.html':
            captured.append(context)
    with app.app_context(), template_rendered.connected_to(record, app):
        response = client.get('/supervisor/reports', query_string=query)
    return response, captured[-1] if captured else {}


def task(title, status='Pending', created=None, owner=None, deadline=None, assigned=False):
    owner = owner or Supervisor.query.filter_by(email='supervisor@test.com').one()
    value = Task(task_type=title, supervisor_id=owner.id, status=status,
                 created_at=created or datetime(2026, 11, 2, 10), deadline=deadline)
    db.session.add(value)
    db.session.flush()
    if assigned:
        worker = OnboardingAgent.query.first()
        db.session.add(TaskAssignment(task_id=value.id, agent_id=worker.id,
                                      supervisor_id=owner.id, status=status))
    db.session.commit()
    return value


def test_counts_and_rows_are_owned_not_request_selected(app, client):
    for status in ('Pending', 'Assigned', 'In progress', 'Completed'):
        task('Owned ' + status, status, deadline=NOW - timedelta(minutes=1), assigned=status != 'Pending')
    other = Supervisor(name='Other supervisor', email='other-report@example.com')
    other.set_password('password123')
    db.session.add(other)
    db.session.commit()
    task('PRIVATE OTHER TASK', 'Assigned', owner=other, deadline=NOW - timedelta(days=1), assigned=True)
    login(client)
    response, context = get_report(app, client, supervisor_id=other.id)
    assert response.status_code == 200
    assert context['report']['counts'] == {'total': 4, 'waiting': 1, 'assigned': 1,
        'in_progress': 1, 'completed': 1, 'other': 0, 'overdue': 3}
    assert context['report']['page'].total == 4
    assert b'PRIVATE OTHER TASK' not in response.data
    assert response.headers['Cache-Control'] == 'no-store, private'


def test_date_range_includes_both_whole_days_and_filters_all_counts(app, client):
    task('Before range', created=datetime(2026, 11, 1, 23, 59, 59, 999999))
    task('Start boundary', 'Assigned', created=datetime(2026, 11, 2), deadline=NOW-timedelta(hours=1))
    task('End boundary', 'Completed', created=datetime(2026, 11, 3, 23, 59, 59, 999999), deadline=NOW-timedelta(days=1))
    task('After range', created=datetime(2026, 11, 4))
    login(client)
    response, context = get_report(app, client, start_date='2026-11-02', end_date='2026-11-03')
    assert response.status_code == 200
    assert context['report']['counts']['total'] == 2
    assert context['report']['counts']['assigned'] == 1
    assert context['report']['counts']['completed'] == 1
    assert context['report']['counts']['overdue'] == 1
    assert {row.task_type for row in context['report']['page'].items} == {'Start boundary', 'End boundary'}
    assert b'Before range' not in response.data and b'After range' not in response.data


@pytest.mark.parametrize('query,expected', [
    ({'start_date': '2026-11-03'}, {'Second'}),
    ({'end_date': '2026-11-02'}, {'First'}),
])
def test_open_ended_dates(app, client, query, expected):
    task('First', created=datetime(2026, 11, 2))
    task('Second', created=datetime(2026, 11, 3))
    login(client)
    response, context = get_report(app, client, **query)
    assert response.status_code == 200
    assert {item.task_type for item in context['report']['page'].items} == expected


@pytest.mark.parametrize('query,field', [
    ({'start_date': '2026-02-30'}, 'start_date'),
    ({'end_date': 'not-a-date'}, 'end_date'),
    ({'start_date': '2026-1-2'}, 'start_date'),
    ({'start_date': '2026-11-04', 'end_date': '2026-11-02'}, 'end_date'),
])
def test_invalid_filters_show_linked_errors_not_unfiltered_results(app, client, query, field):
    task('Do not show unfiltered tasks')
    login(client)
    response, context = get_report(app, client, **query)
    assert response.status_code == 422 and context['report'] is None
    assert field in context['errors']
    assert f'href="#{field}"'.encode() in response.data
    assert b'aria-invalid="true"' in response.data
    assert b'Do not show unfiltered tasks' not in response.data


def test_empty_report_has_zero_counts_and_clear_message(app, client):
    login(client)
    response, context = get_report(app, client)
    assert response.status_code == 200
    assert all(value == 0 for value in context['report']['counts'].values())
    assert b'No tasks found for this period.' in response.data


def test_deadline_boundary_missing_deadline_and_completed_are_not_overdue(app, client):
    task('No deadline')
    task('Due now', deadline=NOW)
    task('Future deadline', deadline=NOW+timedelta(minutes=1))
    task('Completed earlier', 'Completed', deadline=NOW-timedelta(days=1))
    task('Overdue active', 'In progress', deadline=NOW-timedelta(microseconds=1))
    login(client)
    response, context = get_report(app, client)
    assert context['report']['counts']['overdue'] == 1
    assert b'Not set' in response.data and b'EAT' in response.data


def test_assignment_history_does_not_duplicate_tasks_and_names_are_escaped(app, client):
    worker = OnboardingAgent.query.first()
    worker.profile_display_name = '<script>unsafe-name</script>'
    db.session.commit()
    value = task('Assigned title', 'Assigned', assigned=True)
    # Legacy duplicate rows must not multiply task totals or displayed names.
    db.session.add(TaskAssignment(task_id=value.id, agent_id=worker.id,
                                  supervisor_id=value.supervisor_id, status='Assigned'))
    db.session.commit()
    task('Waiting title')
    login(client)
    response, context = get_report(app, client)
    assert context['report']['counts']['total'] == 2
    assert len(context['report']['workers'][value.id]) == 1
    assert b'&lt;script&gt;unsafe-name&lt;/script&gt;' in response.data
    assert b'<script>unsafe-name' not in response.data and b'Not assigned' in response.data


def test_pagination_keeps_dates_and_totals(app, client):
    for index in range(12):
        task(f'Report item {index:02}')
    task('Out of range', created=datetime(2026, 10, 1))
    login(client)
    response, context = get_report(app, client, start_date='2026-11-01', end_date='2026-11-03', page=2)
    assert response.status_code == 200
    assert context['report']['counts']['total'] == 12
    assert context['report']['page'].total == 12 and len(context['report']['page'].items) == 2
    assert b'start_date=2026-11-01' in response.data and b'end_date=2026-11-03' in response.data
    response, context = get_report(app, client, page=999)
    assert b'No tasks on this page.' in response.data and context['report']['counts']['total'] == 13


def test_nonstandard_status_is_not_hidden_from_totals(app, client):
    task('Legacy state', status='On hold')
    login(client)
    response, context = get_report(app, client)
    assert context['report']['counts']['other'] == 1
    assert b'On hold' in response.data and b'another recorded status' in response.data


@pytest.mark.parametrize('email', ['admin@test.com', 'netease-6376@demo.invalid'])
def test_other_roles_cannot_view_reports_or_navigation(app, client, email):
    login(client, email)
    response, _ = get_report(app, client)
    assert response.status_code == 403
    path = '/admin/dashboard' if email == 'admin@test.com' else '/agent/dashboard'
    with app.app_context():
        html = client.get(path).data
    assert b'href="/supervisor/reports"' not in html


def test_signed_out_requests_require_login(app, client):
    response, _ = get_report(app, client)
    assert response.status_code == 302 and '/auth/login' in response.location


def test_report_is_read_only_and_does_not_load_model(app, client, monkeypatch):
    task('Read only report', 'Assigned', assigned=True)
    login(client)
    def snapshot():
        return {table.name: tuple(db.session.execute(table.select()).all())
                for table in db.metadata.sorted_tables}
    before = snapshot()
    def forbidden(*args, **kwargs):
        raise AssertionError('Report must not run model inference')
    monkeypatch.setattr('app.supervisor.routes.load_dataset_profiles', forbidden)
    monkeypatch.setattr('app.supervisor.routes.HybridRecommendationService', forbidden)
    response, _ = get_report(app, client)
    assert response.status_code == 200 and snapshot() == before
    with app.app_context():
        assert client.post('/supervisor/reports').status_code == 405


def test_supervisor_navigation_and_accessibility_styles(app, client):
    login(client)
    response, _ = get_report(app, client)
    html = response.get_data(as_text=True)
    assert 'href="/supervisor/reports" aria-current="page"' in html
    assert 'aria-label="Task report totals"' in html
    assert 'name="start_date"' in html and 'name="end_date"' in html
    assert html.index('supervisor-reports.css') < html.index('role-accessibility.css')


def test_graphs_follow_owner_dates_and_include_every_page(app, client):
    for index in range(12):
        value = task(f'Chart task {index}', 'Completed' if index < 3 else 'Pending')
        value.priority = 'High' if index < 6 else 'Low'
    db.session.commit()
    task('Excluded date', created=datetime(2026, 10, 1))
    other = Supervisor(name='Private owner', email='private-chart@example.com')
    other.set_password('password123')
    db.session.add(other)
    db.session.commit()
    task('Excluded owner', owner=other)
    login(client)
    response, context = get_report(app, client, start_date='2026-11-01', page=2)
    charts = context['report']['charts']
    assert len(context['report']['page'].items) == 2
    assert sum(row['count'] for row in charts['status']) == 12
    assert sum(row['count'] for row in charts['priority']) == 12
    assert next(row for row in charts['status'] if row['label'] == 'Completed')['percent'] == 25.0
    assert next(row for row in charts['priority'] if row['label'] == 'High')['percent'] == 50.0
    assert b'Task progress' in response.data and b'Task priorities' in response.data
    assert b'stroke-dasharray="50.0 50.0"' in response.data


def test_graphs_keep_unknown_values_visible(app, client):
    value = task('Old record', status='On hold')
    value.priority = 'Legacy urgency'
    db.session.commit()
    login(client)
    response, context = get_report(app, client)
    assert context['report']['charts']['priority'][-1]['label'] == 'Other / not recorded'
    assert context['report']['charts']['priority'][-1]['percent'] == 100.0
    assert context['report']['charts']['status'][-1]['count'] == 1
    assert b'Other / not recorded' in response.data and b'Other status' in response.data


def test_empty_graphs_do_not_invent_values(app, client):
    login(client)
    response, context = get_report(app, client)
    for rows in context['report']['charts'].values():
        assert all(row['count'] == 0 and row['percent'] == 0 for row in rows)
    assert response.data.count(b'No tasks to chart yet.') == 2
    assert b'width: nan' not in response.data


def test_graph_values_are_readable_without_javascript_or_colour(app, client):
    task('One waiting task')
    login(client)
    response, _ = get_report(app, client)
    html = response.get_data(as_text=True)
    assert 'aria-labelledby="report-chart-status"' in html
    assert 'Waiting</span>' in html
    assert '<strong>1</strong> <small>(100.0%)</small>' in html
    assert 'viewBox="0 0 120 120" aria-hidden="true"' in html
    assert 'category=Pending' in html
    assert 'col-12 col-lg-6' in html


def test_status_drilldown_keeps_whole_period_charts_and_owner_scope(app, client):
    task('Completed own', 'Completed')
    task('Waiting own')
    other = Supervisor(name='Another', email='drill-private@example.com')
    other.set_password('password123')
    db.session.add(other)
    db.session.commit()
    task('Private complete', 'Completed', owner=other)
    login(client)
    response, context = get_report(app, client, breakdown='status', category='Completed')
    report = context['report']
    assert report['counts']['total'] == 2
    assert report['page'].total == 1
    assert [value.task_type for value in report['page'].items] == ['Completed own']
    assert b'Private complete' not in response.data
    assert b'Show all tasks' in response.data
    assert b'aria-current="true"' in response.data


def test_priority_drilldown_preserves_dates_and_pagination(app, client):
    for index in range(12):
        value = task(f'High priority {index}')
        value.priority = 'High'
    db.session.commit()
    task('Other priority')
    old = task('Old high', created=datetime(2026, 10, 1))
    old.priority = 'High'
    db.session.commit()
    login(client)
    response, context = get_report(app, client, start_date='2026-11-01', breakdown='priority', category='High', page=2)
    assert context['report']['page'].total == 12
    assert len(context['report']['page'].items) == 2
    assert context['report']['counts']['total'] == 13
    assert b'breakdown=priority' in response.data and b'category=High' in response.data
    assert b'start_date=2026-11-01' in response.data


@pytest.mark.parametrize('query', [
    {'breakdown': 'status', 'category': 'invalid'},
    {'breakdown': 'owner', 'category': '1'},
    {'category': 'High'},
])
def test_invalid_chart_selection_is_rejected(app, client, query):
    login(client)
    response, _ = get_report(app, client, **query)
    assert response.status_code == 400


def test_other_chart_segment_and_zero_category_drilldown(app, client):
    task('Unknown status', status='Legacy')
    task('Waiting')
    login(client)
    response, context = get_report(app, client, breakdown='status', category='other')
    assert context['report']['page'].total == 1
    assert context['report']['page'].items[0].task_type == 'Unknown status'
    response, context = get_report(app, client, breakdown='priority', category='High')
    assert context['report']['page'].total == 0
    assert context['report']['counts']['total'] == 2


def test_doughnut_geometry_covers_full_circle_without_rounding_gaps(app, client):
    for status in ('Pending', 'Assigned', 'Completed'):
        task(status, status=status)
    login(client)
    response, context = get_report(app, client)
    for rows in context['report']['charts'].values():
        assert sum(row['arc'] for row in rows) == pytest.approx(100)
        assert all(row['arc'] + row['gap'] == pytest.approx(100) for row in rows)
    assert b'<svg class="report-donut"' in response.data


@pytest.mark.parametrize('field', ['start_date', 'end_date'])
def test_future_report_dates_rejected_on_server(app, client, field):
    task('Must not show unfiltered results')
    login(client)
    response, context = get_report(app, client, **{field: '2026-11-06'})
    assert response.status_code == 422
    assert context['report'] is None
    assert context['errors'][field] == 'Choose today or an earlier date.'
    assert f'href="#{field}"'.encode() in response.data
    assert b'Must not show unfiltered results' not in response.data
    assert response.data.count(b'max="2026-11-05"') == 2


def test_today_is_allowed_and_both_calendar_limits_use_kenya_date(app, client, monkeypatch):
    monkeypatch.setattr(reports, 'kenya_now', lambda: datetime(2026, 11, 2, 0, 5))
    task('Created today', created=datetime(2026, 11, 2, 0, 1))
    login(client)
    response, context = get_report(app, client, start_date='2026-11-02', end_date='2026-11-02')
    assert response.status_code == 200
    assert context['report']['counts']['total'] == 1
    assert response.data.count(b'max="2026-11-02"') == 2
    response, context = get_report(app, client, end_date='2026-11-03')
    assert response.status_code == 422


def test_both_future_dates_have_field_errors(app, client):
    login(client)
    response, context = get_report(app, client, start_date='2026-11-06', end_date='2026-11-07')
    assert response.status_code == 422
    assert set(context['errors']) == {'start_date', 'end_date'}
