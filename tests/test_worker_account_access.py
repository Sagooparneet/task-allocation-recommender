from pathlib import Path
from sqlalchemy import text
from app.extensions import db
from app.models import OnboardingAgent, TaskAssignment, Task
from app.services.netease_recommendation_service import NetEaseRecommendationService
from test_admin_workers import login, worker, add_assignment
from test_workflow import create_test_task


def test_disabled_password_login_is_rejected(app, client):
    agent = worker()
    agent.account_disabled = True
    db.session.commit()
    assert not agent.is_active
    response = login(client, agent.email)
    assert b'Invalid email or password' in response.data
    with client.session_transaction() as session:
        assert '_user_id' not in session


def test_existing_session_revoked_and_history_preserved(app, client):
    agent = worker()
    add_assignment(agent, 'Existing work')
    assignment = TaskAssignment.query.filter_by(agent_id=agent.id).first()
    assignment_id = assignment.id
    with app.app_context():
        login(client, agent.email)
    with app.app_context():
        assert client.get('/agent/dashboard').status_code == 200
    with client.session_transaction() as session:
        token = session['task_progress_csrf_token']
    agent.account_disabled = True
    db.session.commit()
    before = db.session.execute(text('SELECT * FROM task_assignments')).all()
    with app.app_context():
        response = client.post(f'/agent/assignment/{assignment_id}/start', data={'task_progress_csrf_token':token})
        assert response.status_code == 302 and '/auth/login' in response.location
    with client.session_transaction() as session:
        assert '_user_id' not in session
    assert db.session.execute(text('SELECT * FROM task_assignments')).all() == before
    agent.account_disabled = False
    db.session.commit()
    with app.app_context():
        assert client.get('/agent/dashboard').status_code == 302


def test_disabled_worker_excluded_without_changing_scores_or_bindings(app, client):
    task_id = create_test_task(app)
    agent = worker()
    binding = Path(app.instance_path) / 'netease_agent_bindings.json'
    before_binding = binding.read_bytes()
    before = NetEaseRecommendationService().get_recommendations(task_id)
    assert before
    agent.account_disabled = True
    db.session.commit()
    assert not NetEaseRecommendationService().get_recommendations(task_id)
    assert agent.availability is True
    agent.account_disabled = False
    db.session.commit()
    assert NetEaseRecommendationService().get_recommendations(task_id) == before
    assert binding.read_bytes() == before_binding


def test_stale_recommendation_rejects_disabled_worker(app, client):
    task_id = create_test_task(app)
    login(client, 'supervisor@test.com')
    client.get(f'/supervisor/task/{task_id}/recommendations')
    with client.session_transaction() as session:
        token = session['assignment_csrf_token']
    agent = worker()
    agent.account_disabled = True
    db.session.commit()
    client.post(f'/supervisor/task/{task_id}/assign', data={'agent_id':agent.id,'assignment_csrf_token':token})
    db.session.expire_all()
    assert db.session.get(Task, task_id).status == 'Pending'
    assert TaskAssignment.query.filter_by(task_id=task_id).count() == 0


def test_unavailable_is_not_disabled(app, client):
    agent = worker()
    agent.availability = False
    db.session.commit()
    assert agent.is_active and not agent.account_disabled
    assert login(client, agent.email).status_code == 302
    assert client.get('/agent/dashboard').status_code == 200


def test_assignment_rechecks_disabled_flag_after_candidate_read(app, client, monkeypatch):
    task_id = create_test_task(app)
    login(client, 'supervisor@test.com')
    client.get(f'/supervisor/task/{task_id}/recommendations')
    with client.session_transaction() as session:
        token = session['assignment_csrf_token']
    agent = worker()
    old_workload = agent.workload
    original = NetEaseRecommendationService.get_eligible_candidates
    def changed_after_read(service, task_id):
        result = original(service, task_id)
        agent.account_disabled = True
        db.session.commit()
        return result
    monkeypatch.setattr(NetEaseRecommendationService, 'get_eligible_candidates', changed_after_read)
    client.post(f'/supervisor/task/{task_id}/assign', data={'agent_id':agent.id,'assignment_csrf_token':token})
    db.session.expire_all()
    assert db.session.get(Task, task_id).status == 'Pending'
    assert TaskAssignment.query.filter_by(task_id=task_id).count() == 0
    assert agent.workload == old_workload
