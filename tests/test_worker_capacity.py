from pathlib import Path
from datetime import datetime, timezone
import pytest
from sqlalchemy import text
from app.extensions import db
from app.models import OnboardingAgent, Task, TaskAssignment, Supervisor
from app.services.netease_recommendation_service import NetEaseRecommendationService
from app.services.worker_capacity import active_task_count
from test_admin_workers import login, worker, add_assignment
from test_workflow import create_test_task


def form(client, task_id, agent_id):
    login(client, 'supervisor@test.com')
    assert client.get(f'/supervisor/task/{task_id}/recommendations').status_code == 200
    with client.session_transaction() as session:
        return {'agent_id': agent_id, 'assignment_csrf_token': session['assignment_csrf_token']}


@pytest.mark.parametrize('count,eligible', [(0, True), (2, True), (3, False), (4, False)])
def test_capacity_uses_actual_active_assignments_and_preserves_records(app, count, eligible):
    agent = worker()
    task_id = create_test_task(app)
    for i in range(count):
        add_assignment(agent, f'Existing {i}', 'Assigned' if i % 2 else 'In progress')
    add_assignment(agent, 'Completed work', 'Completed')
    agent.workload = 99 if eligible else 0  # A stale counter must not decide eligibility.
    db.session.commit()
    before = db.session.execute(text('SELECT * FROM task_assignments ORDER BY id')).all()
    binding = Path(app.instance_path) / 'netease_agent_bindings.json'
    binding_before = binding.read_bytes()
    assert active_task_count(agent.id) == count
    rows = NetEaseRecommendationService().get_recommendations(task_id)
    assert bool(rows) == eligible
    if rows:
        assert rows[0]['workload'] == count
    assert db.session.execute(text('SELECT * FROM task_assignments ORDER BY id')).all() == before
    assert binding.read_bytes() == binding_before
    assert agent.availability is True


def test_third_assignment_allowed_fourth_rejected_across_supervisors(app, client):
    agent = worker()
    add_assignment(agent, 'First')
    add_assignment(agent, 'Second', 'In progress')
    other = Supervisor(name='Another supervisor', email='other@test.invalid', password_hash='disabled')
    db.session.add(other); db.session.flush()
    assignment = TaskAssignment.query.filter_by(agent_id=agent.id).first()
    assignment.supervisor_id = other.id
    assignment.task.supervisor_id = other.id
    db.session.commit()
    task_id = create_test_task(app)
    data = form(client, task_id, agent.id)
    assert client.post(f'/supervisor/task/{task_id}/assign', data=data).status_code == 302
    db.session.expire_all()
    assert active_task_count(agent.id) == 3
    assert TaskAssignment.query.filter_by(task_id=task_id).count() == 1
    fourth = create_test_task(app)
    client.post(f'/supervisor/task/{fourth}/assign', data=data)
    db.session.expire_all()
    assert db.session.get(Task, fourth).status == 'Pending'
    assert TaskAssignment.query.filter_by(task_id=fourth).count() == 0
    assert active_task_count(agent.id) == 3


def test_capacity_rechecked_after_candidate_selection_rolls_back_task_claim(app, client, monkeypatch):
    agent = worker()
    task_id = create_test_task(app)
    data = form(client, task_id, agent.id)
    stale = NetEaseRecommendationService().get_eligible_candidates(task_id)
    for i in range(3):
        add_assignment(agent, f'Newly assigned {i}')
    before_workload = agent.workload
    monkeypatch.setattr(NetEaseRecommendationService, 'get_eligible_candidates', lambda self, task_id: stale)
    response = client.post(f'/supervisor/task/{task_id}/assign', data=data, follow_redirects=True)
    assert b'already has 3 active tasks' in response.data
    db.session.expire_all()
    assert db.session.get(Task, task_id).status == 'Pending'
    assert not TaskAssignment.query.filter_by(task_id=task_id).first()
    assert agent.workload == before_workload
    assert active_task_count(agent.id) == 3


def test_completion_reopens_slot_without_changing_model_scores(app, client):
    agent = worker()
    task_id = create_test_task(app)
    baseline = NetEaseRecommendationService().get_recommendations(task_id)[0]
    for i in range(3):
        add_assignment(agent, f'Work {i}', 'In progress')
    assignment = TaskAssignment.query.filter_by(agent_id=agent.id).first()
    assignment.started_at = datetime(2026, 1, 1)
    agent.workload = 3
    db.session.commit()
    assert not NetEaseRecommendationService().get_recommendations(task_id)
    login(client, agent.email)
    client.get('/agent/dashboard')
    with client.session_transaction() as session:
        data = {'task_progress_csrf_token': session['task_progress_csrf_token']}
    assert client.post(f'/agent/assignment/{assignment.id}/complete', data=data).status_code == 302
    db.session.expire_all()
    assert active_task_count(agent.id) == 2
    result = NetEaseRecommendationService().get_recommendations(task_id)[0]
    for key in ('score', 'components', 'match_percentage', 'historical_success_rate', 'model_weights'):
        assert result[key] == baseline[key]
    assert result['workload'] == 2
