from pathlib import Path
import pytest
from sqlalchemy import text
from app.extensions import db
from app.models import OnboardingAgent, Task, TaskAssignment
from app.services.netease_recommendation_service import NetEaseRecommendationService
from test_admin_workers import login, worker, add_assignment
from test_workflow import create_test_task


def availability_form(client, agent):
    assert client.get(f'/admin/workers/{agent.id}/availability').status_code == 200
    with client.session_transaction() as session:
        return {'csrf_token': session['worker_availability_csrf_token'],
                'original_availability': 'available' if agent.availability else 'unavailable'}


def test_availability_changes_only_the_flag_and_restores_ranking(app, client):
    agent = worker()
    add_assignment(agent, 'Existing task')
    task_id = create_test_task(app)
    before = NetEaseRecommendationService().get_recommendations(task_id)
    assert before and before[0]['agent_id'] == agent.id
    columns = [column for column in OnboardingAgent.__table__.columns if column.name != 'availability']
    def account_snapshot():
        return tuple(db.session.query(*columns).filter(OnboardingAgent.id == agent.id).one())
    account_before = account_snapshot()
    tasks_before = db.session.execute(text('SELECT * FROM tasks ORDER BY id')).all()
    assignments_before = db.session.execute(text('SELECT * FROM task_assignments ORDER BY id')).all()
    binding = Path(app.instance_path) / 'netease_agent_bindings.json'
    binding_before = binding.read_bytes()
    login(client)
    data = availability_form(client, agent)
    data.update(availability='unavailable', email='changed@test.invalid', workload='0', profile_display_name='Changed')
    assert client.post(f'/admin/workers/{agent.id}/availability', data=data).status_code == 302
    db.session.expire_all()
    assert agent.availability is False
    assert account_snapshot() == account_before
    assert db.session.execute(text('SELECT * FROM tasks ORDER BY id')).all() == tasks_before
    assert db.session.execute(text('SELECT * FROM task_assignments ORDER BY id')).all() == assignments_before
    assert binding.read_bytes() == binding_before
    assert not NetEaseRecommendationService().get_recommendations(task_id)
    assert agent.email.encode() in client.get('/admin/workers?availability=unavailable').data
    data = availability_form(client, agent)
    data['availability'] = 'available'
    client.post(f'/admin/workers/{agent.id}/availability', data=data)
    db.session.expire_all()
    assert NetEaseRecommendationService().get_recommendations(task_id) == before


def test_unavailable_worker_can_login_start_and_complete_existing_work(app, client):
    agent = worker()
    add_assignment(agent, 'Keep this assignment')
    assignment_id = TaskAssignment.query.filter_by(agent_id=agent.id).one().id
    login(client)
    data = availability_form(client, agent)
    data['availability'] = 'unavailable'
    client.post(f'/admin/workers/{agent.id}/availability', data=data)
    client.get('/auth/logout')
    response = login(client, 'netease-6376@demo.invalid')
    assert response.status_code == 302
    assert client.get('/agent/dashboard').status_code == 200
    with client.session_transaction() as session:
        progress = {'task_progress_csrf_token':session['task_progress_csrf_token']}
    assert client.post(f'/agent/assignment/{assignment_id}/start', data=progress).status_code == 302
    assert client.post(f'/agent/assignment/{assignment_id}/complete', data=progress).status_code == 302
    db.session.expire_all()
    assignment = db.session.get(TaskAssignment, assignment_id)
    assert assignment.status == assignment.task.status == 'Completed'
    assert assignment.completed_at is not None
    assert agent.availability is False and agent.workload == 0


def test_stale_recommendation_cannot_assign_unavailable_worker(app, client):
    agent_id = worker().id
    task_id = create_test_task(app)
    login(client, 'supervisor@test.com')
    assert client.get(f'/supervisor/task/{task_id}/recommendations').status_code == 200
    with client.session_transaction() as session:
        assignment_data = {'agent_id':agent_id, 'assignment_csrf_token':session['assignment_csrf_token']}
    admin = app.test_client()
    with app.app_context():
        login(admin)
    with app.app_context():
        agent = db.session.get(OnboardingAgent, agent_id)
        availability_data = availability_form(admin, agent)
    availability_data['availability'] = 'unavailable'
    with app.app_context():
        assert admin.post(f'/admin/workers/{agent_id}/availability', data=availability_data).status_code == 302
    with app.app_context():
        client.post(f'/supervisor/task/{task_id}/assign', data=assignment_data)
        assert db.session.get(Task, task_id).status == 'Pending'
        assert TaskAssignment.query.filter_by(task_id=task_id).count() == 0


@pytest.mark.parametrize('email', ['supervisor@test.com','netease-6376@demo.invalid'])
def test_availability_is_admin_only(app, client, email):
    login(client, email)
    path = f'/admin/workers/{worker().id}/availability'
    assert client.get(path).status_code == 403
    assert client.post(path, data={'availability':'unavailable'}).status_code == 403


def test_invalid_token_values_and_stale_form(app, client):
    agent = worker()
    login(client)
    path = f'/admin/workers/{agent.id}/availability'
    data = availability_form(client, agent)
    assert client.post(path, data={'availability':'unavailable'}).status_code == 400
    response = client.post(path, data={**data,'availability':'maybe'})
    assert response.status_code == 422 and b'aria-invalid="true"' in response.data
    assert b'href="#availability"' in response.data
    client.post(path, data={**data, 'availability':'unavailable'})
    # An older form must not undo a newer change, even with a valid token.
    assert client.post(path, data={**data,'availability':'available'}).status_code == 422
    db.session.expire_all()
    assert agent.availability is False
    assert client.get('/admin/workers/999999/availability').status_code == 404


def test_anonymous_cannot_change_availability_and_get_is_read_only(app, client):
    agent = worker()
    path = f'/admin/workers/{agent.id}/availability'
    assert client.post(path, data={'availability':'unavailable'}).status_code == 302
    assert agent.availability is True
    login(client)
    assert client.get(path + '?availability=unavailable').status_code == 200
    db.session.expire_all()
    assert agent.availability is True
