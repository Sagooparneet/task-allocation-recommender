from pathlib import Path
import pytest
from app.extensions import db
from app.models import OnboardingAgent, Task, TaskSkill, Skill, Supervisor
from app.services.account_display_name import account_display_name
from app.services.worker_directory import directory_names
from app.services.netease_recommendation_service import NetEaseRecommendationService
from test_admin_workers import login, worker


def form(client, agent):
    assert client.get(f'/admin/workers/{agent.id}/edit').status_code == 200
    with client.session_transaction() as session:
        return {'csrf_token':session['worker_edit_csrf_token'],
                'original_display_name':agent.profile_display_name or ''}


def test_edit_updates_names_but_preserves_identity_and_scores(app, client):
    agent = worker()
    task = Task(task_type='Name regression', supervisor_id=Supervisor.query.first().id, status='Pending')
    db.session.add(task)
    db.session.flush()
    db.session.add(TaskSkill(task_id=task.id, skill_id=Skill.query.filter_by(name='NetEase capability 56').one().id))
    db.session.commit()
    before = NetEaseRecommendationService().get_recommendations(task.id)
    assert before and before[0]['agent_id'] == agent.id
    original = (agent.name, agent.email, agent.password_hash, agent.workload, agent.availability, agent.performance_score)
    bindings = Path(app.instance_path) / 'netease_agent_bindings.json'
    mapping_before = bindings.read_bytes()
    login(client)
    data = form(client, agent)
    data.update(display_name='Updated Worker Name', email='intruder@test.invalid', workload='0', availability='', name='Changed source', password='changed')
    response = client.post(f'/admin/workers/{agent.id}/edit', data=data, follow_redirects=True)
    assert response.status_code == 200 and b'Updated Worker Name' in response.data
    db.session.expire_all()
    assert (agent.name, agent.email, agent.password_hash, agent.workload, agent.availability, agent.performance_score) == original
    assert bindings.read_bytes() == mapping_before
    assert account_display_name(agent) == directory_names()[agent.id] == 'Updated Worker Name'
    after = NetEaseRecommendationService().get_recommendations(task.id)
    assert after[0]['agent_name'] == 'Updated Worker Name'
    assert [{k:v for k,v in row.items() if k != 'agent_name'} for row in after] == [{k:v for k,v in row.items() if k != 'agent_name'} for row in before]
    assert b'Updated Worker Name' in client.get('/admin/workers?q=Updated+Worker').data


@pytest.mark.parametrize('value', ['', ' ', 'x'*101, 'Name\x00Here', 'Name\u202eHere'])
def test_invalid_name_is_accessible_and_not_saved(app, client, value):
    agent = worker()
    login(client)
    data = form(client, agent)
    data['display_name'] = value
    response = client.post(f'/admin/workers/{agent.id}/edit', data=data)
    assert response.status_code == 422
    assert b'href="#display_name"' in response.data and b'aria-invalid="true"' in response.data
    db.session.expire_all()
    assert agent.profile_display_name is None


@pytest.mark.parametrize('email', ['supervisor@test.com', 'netease-6376@demo.invalid'])
def test_edit_is_admin_only(app, client, email):
    login(client, email)
    assert client.get(f'/admin/workers/{worker().id}/edit').status_code == 403
    assert client.post(f'/admin/workers/{worker().id}/edit', data={'display_name':'No'}).status_code == 403


def test_token_missing_worker_and_stale_edit(app, client):
    agent = worker()
    login(client)
    data = form(client, agent)
    assert client.post(f'/admin/workers/{agent.id}/edit', data={'display_name':'No'}).status_code == 400
    assert client.get('/admin/workers/999999/edit').status_code == 404
    agent.profile_display_name = 'Newer saved name'
    db.session.commit()
    data['display_name'] = 'Old form edit'
    assert client.post(f'/admin/workers/{agent.id}/edit', data=data).status_code == 422
    db.session.expire_all()
    assert agent.profile_display_name == 'Newer saved name'


def test_html_is_escaped_and_unicode_name_is_supported(app, client):
    agent = worker()
    login(client)
    data = form(client, agent)
    data['display_name'] = '<script>alert(1)</script> José'
    response = client.post(f'/admin/workers/{agent.id}/edit', data=data, follow_redirects=True)
    assert response.status_code == 200
    assert b'<script>alert(1)</script>' not in response.data
    assert b'&lt;script&gt;' in response.data


def test_supervisor_snapshot_uses_name_without_mutating_cached_dataset(app, client, monkeypatch):
    from copy import deepcopy
    from app.services.netease_dataset_profiles import load_dataset_profiles
    agent = worker()
    agent.profile_display_name = 'Supervisor-visible name'
    db.session.commit()
    profiles = {'6376': deepcopy(load_dataset_profiles()['6376'])}
    before = deepcopy(profiles)
    monkeypatch.setattr('app.supervisor.routes.load_dataset_profiles', lambda: profiles)
    login(client, 'supervisor@test.com')
    response = client.get('/supervisor/dashboard')
    assert response.status_code == 200 and b'Supervisor-visible name' in response.data
    assert profiles == before
