"""Administrator service edits affect future independent-worker matching only."""
import re
from pathlib import Path

import pytest

from app.extensions import db
from app.models import (AgentSkill, OnboardingAgent, Skill, Task, TaskAssignment,
                        TaskSkill, Supervisor)
from app.services.independent_worker_matching import matching_workers
from app.services.netease_recommendation_service import NetEaseRecommendationService
from test_admin_workers import login
from test_independent_worker_matching import new_worker
from test_workflow import create_test_task


def edit_form(client, worker_id):
    page = client.get(f'/admin/workers/{worker_id}/services')
    assert page.status_code == 200
    with client.session_transaction() as state:
        token = state['worker_services_csrf_token']
    original = re.search(rb'name="original_services" value="([^"]*)"', page.data)
    assert original is not None
    return {'csrf_token': token, 'original_services': original.group(1).decode(),
            'confirmed': 'yes'}


def test_edit_changes_future_matches_and_preserves_history(app, client):
    task_id = create_test_task(app)
    model_before = NetEaseRecommendationService().get_recommendations(task_id)
    binding_file = Path(app.instance_path) / 'netease_agent_bindings.json'
    bindings_before = binding_file.read_bytes()
    worker = new_worker()
    worker_id = worker.id
    supervisor = Supervisor.query.first()
    db.session.add(TaskAssignment(task_id=task_id, agent_id=worker_id,
        supervisor_id=supervisor.id, status='Completed'))
    sim = Skill(name='SIM Registration')
    db.session.add(sim)
    db.session.flush()
    future = Task(task_type='SIM registration', supervisor_id=supervisor.id,
                  status='Pending')
    db.session.add(future)
    db.session.flush()
    db.session.add(TaskSkill(task_id=future.id, skill_id=sim.id))
    db.session.commit()
    assert any(item['agent_id'] == worker_id for item in matching_workers(task_id))
    assert matching_workers(future.id) == []
    original_assignment = db.session.query(*TaskAssignment.__table__.columns).all()
    dataset_links = db.session.query(*AgentSkill.__table__.columns).filter(
        AgentSkill.agent_id != worker_id).order_by(AgentSkill.id).all()
    login(client)
    form = edit_form(client, worker_id)
    response = client.post(f'/admin/workers/{worker_id}/services', data={
        **form, 'services': ['SIM Registration'], 'workload': '99',
        'source_worker_id': '6376'})
    assert response.status_code == 302
    assert matching_workers(task_id) == []
    assert any(item['agent_id'] == worker_id for item in matching_workers(future.id))
    assert db.session.query(*TaskAssignment.__table__.columns).all() == original_assignment
    assert db.session.query(*AgentSkill.__table__.columns).filter(
        AgentSkill.agent_id != worker_id).order_by(AgentSkill.id).all() == dataset_links
    assert db.session.get(OnboardingAgent, worker_id).workload == 0
    assert binding_file.read_bytes() == bindings_before
    assert NetEaseRecommendationService().get_recommendations(task_id) == model_before
    profile = client.get(response.location)
    assert b'SIM Registration' in profile.data and b'Edit services' in profile.data


def test_dataset_worker_is_read_only_and_other_roles_are_denied(app, client):
    dataset_id = OnboardingAgent.query.filter_by(email='netease-6376@demo.invalid').one().id
    login(client)
    assert b'Edit services' not in client.get(f'/admin/workers/{dataset_id}').data
    for method in ('get', 'post'):
        assert getattr(client, method)(f'/admin/workers/{dataset_id}/services').status_code == 404
    worker_id = new_worker().id
    client.get('/auth/logout')
    for email in ('supervisor@test.com', 'netease-6376@demo.invalid'):
        login(client, email)
        assert client.get(f'/admin/workers/{worker_id}/services').status_code == 403
        assert client.post(f'/admin/workers/{worker_id}/services').status_code == 403
        client.get('/auth/logout')


@pytest.mark.parametrize('services,confirmed', [([], 'yes'), (['made up'], 'yes'),
    (['KYC Verification', 'KYC Verification'], 'yes'), (['KYC Verification'], '')])
def test_invalid_selection_keeps_existing_services(app, client, services, confirmed):
    worker_id = new_worker().id
    login(client)
    form = edit_form(client, worker_id)
    before = [(row.id, row.skill_id) for row in AgentSkill.query.filter_by(agent_id=worker_id).all()]
    response = client.post(f'/admin/workers/{worker_id}/services', data={
        **form, 'services': services, 'confirmed': confirmed})
    assert response.status_code == 422 and b'aria-invalid="true"' in response.data
    assert [(row.id, row.skill_id) for row in AgentSkill.query.filter_by(agent_id=worker_id).all()] == before


def test_csrf_replay_and_stale_edit_are_rejected(app, client):
    worker_id = new_worker().id
    login(client)
    form = edit_form(client, worker_id)
    assert client.post(f'/admin/workers/{worker_id}/services', data={
        **form, 'csrf_token': 'wrong', 'services': ['KYC Verification']}).status_code == 400
    sim = Skill(name='SIM Registration')
    db.session.add(sim)
    db.session.flush()
    db.session.add(AgentSkill(agent_id=worker_id, skill_id=sim.id,
                              proficiency_level='Administrator confirmed'))
    db.session.commit()
    response = client.post(f'/admin/workers/{worker_id}/services', data={
        **form, 'services': ['KYC Verification']})
    assert response.status_code == 422 and b'changed in another session' in response.data
    assert AgentSkill.query.filter_by(agent_id=worker_id).count() == 2
