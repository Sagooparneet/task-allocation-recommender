import json
from pathlib import Path
import pytest
from sqlalchemy import text
from app.extensions import db
from app.models import OnboardingAgent, IndependentWorkerRegistration, WorkerSourceBinding, AgentSkill, Skill, Administrator
from app.services.independent_workers import PENDING_PASSWORD
from app.services.netease_recommendation_service import NetEaseRecommendationService
from test_admin_workers import login
from test_workflow import create_test_task


def form(client):
    assert client.get('/admin/workers/new').status_code == 200
    with client.session_transaction() as session:
        token = session['worker_create_csrf_token']
    skill = Skill.query.filter_by(name='NetEase capability 56').one()
    return {'csrf_token':token, 'name':'New Worker', 'email':'new.worker@example.com',
            'city':'Nairobi', 'services':[str(skill.id)], 'confirmed':'yes'}


def test_creation_preserves_existing_workers_bindings_and_recommendations(app, client):
    task_id = create_test_task(app)
    baseline = NetEaseRecommendationService().get_recommendations(task_id)
    before = db.session.execute(text('SELECT * FROM onboarding_agents ORDER BY id')).all()
    old_ids = [r.id for r in OnboardingAgent.query.all()]
    old_links = db.session.execute(text('SELECT * FROM agent_skills ORDER BY id')).all()
    tasks = db.session.execute(text('SELECT * FROM tasks ORDER BY id')).all()
    binding = Path(app.instance_path) / 'netease_agent_bindings.json'
    original_binding = binding.read_bytes()
    login(client)
    data = form(client)
    data.update(email=' NEW.WORKER@EXAMPLE.COM ', source_worker_id='6376',
                availability='true', account_disabled='false', workload='99', performance_score='100',
                password='forged-password', role='administrator')
    response = client.post('/admin/workers/new', data=data)
    assert response.status_code == 302
    worker = OnboardingAgent.query.filter_by(email='new.worker@example.com').one()
    registration = db.session.get(IndependentWorkerRegistration, worker.id)
    assert registration.created_by_admin_id == Administrator.query.filter_by(email='admin@test.com').one().id
    assert registration.created_at is not None
    assert worker.name == 'New Worker' and worker.location == 'Nairobi'
    assert worker.account_disabled and not worker.availability
    assert worker.password_hash == PENDING_PASSWORD and worker.workload == 0
    assert worker.performance_score is None
    assert not db.session.get(WorkerSourceBinding, worker.id)
    assert AgentSkill.query.filter_by(agent_id=worker.id).one().proficiency_level == 'Administrator confirmed'
    assert db.session.query(*OnboardingAgent.__table__.columns).filter(OnboardingAgent.id.in_(old_ids)).order_by(OnboardingAgent.id).all() == before
    assert db.session.execute(text('SELECT * FROM agent_skills WHERE agent_id != :id ORDER BY id'), {'id':worker.id}).all() == old_links
    assert db.session.execute(text('SELECT * FROM tasks ORDER BY id')).all() == tasks
    assert binding.read_bytes() == original_binding
    assert NetEaseRecommendationService().get_recommendations(task_id) == baseline
    page = client.get(response.location)
    assert b'Awaiting account setup' in page.data and b'No recorded performance history' in page.data
    assert b'Reactivate account' not in page.data
    assert b'New Worker' in client.get('/admin/workers?q=new.worker').data
    # Ordinary reactivation must not bypass pending credential setup.
    assert client.post(f'/admin/workers/{worker.id}/account-status', data={'action':'reactivate','confirm':'yes'}).status_code == 302
    db.session.expire_all()
    assert worker.account_disabled
    # No binding means no model eligibility, even if flags were changed separately.
    worker.account_disabled=False; worker.availability=True; db.session.commit()
    assert NetEaseRecommendationService().get_recommendations(task_id) == baseline
    client.get('/auth/logout')
    assert b'Invalid email or password' in client.post('/auth/login', data={'email':worker.email,'password':'forged-password'}).data


@pytest.mark.parametrize('email', ['supervisor@test.com','netease-6376@demo.invalid'])
def test_only_administrator_can_create(client, email):
    login(client, email)
    assert client.get('/admin/workers/new').status_code == 403
    assert client.post('/admin/workers/new',data={}).status_code == 403


def test_anonymous_get_and_post_cannot_create(client):
    assert client.get('/admin/workers/new').status_code == 302
    assert client.post('/admin/workers/new',data={}).status_code == 302
    assert IndependentWorkerRegistration.query.count() == 0


def test_token_required_get_read_only_and_replay_rejected(client):
    login(client)
    data = form(client)
    assert IndependentWorkerRegistration.query.count() == 0
    assert client.post('/admin/workers/new',data={**data,'csrf_token':'wrong'}).status_code == 400
    assert client.post('/admin/workers/new',data=data).status_code == 302
    assert client.post('/admin/workers/new',data=data).status_code == 400
    assert IndependentWorkerRegistration.query.count() == 1


@pytest.mark.parametrize('email', ['SUPERVISOR@TEST.COM','ADMIN@TEST.COM','NETEASE-6376@DEMO.INVALID'])
def test_existing_role_email_cannot_be_reused(client,email):
    login(client)
    before = OnboardingAgent.query.count()
    data = form(client); data['email'] = email
    response = client.post('/admin/workers/new',data=data)
    assert response.status_code == 422 and b'href="#email"' in response.data
    assert OnboardingAgent.query.count() == before
    assert IndependentWorkerRegistration.query.count() == 0


@pytest.mark.parametrize('updates,field', [
    ({'name':''},'name'), ({'name':'A'*101},'name'), ({'name':'Hidden\u200bName'},'name'),
    ({'email':'not-an-email'},'email'), ({'email':'person@demo.invalid'},'email'),
    ({'city':'Remote'},'city'), ({'services':[]},'services'),
    ({'services':['999999']},'services'), ({'services':['bad']},'services'),
    ({'confirmed':''},'confirmed'),
])
def test_invalid_fields_retain_entries_without_creating_records(client,updates,field):
    login(client)
    data = form(client);data.update(updates)
    before = OnboardingAgent.query.count()
    response = client.post('/admin/workers/new',data=data)
    assert response.status_code == 422
    assert f'href="#{field}"'.encode() in response.data
    assert b'aria-invalid="true"' in response.data
    assert OnboardingAgent.query.count() == before
    assert IndependentWorkerRegistration.query.count() == 0


def test_duplicate_new_worker_email_is_rejected(client):
    login(client)
    assert client.post('/admin/workers/new',data=form(client)).status_code == 302
    response = client.post('/admin/workers/new',data=form(client))
    assert response.status_code == 422 and b'already used' in response.data
    assert IndependentWorkerRegistration.query.count() == 1


def test_orphan_source_binding_collision_rolls_back_new_account(app,client):
    login(client)
    data = form(client)
    count = OnboardingAgent.query.count()
    next_id = max(w.id for w in OnboardingAgent.query.all()) + 1
    binding = Path(app.instance_path)/'netease_agent_bindings.json'
    mapping = json.loads(binding.read_text(encoding='utf-8'))
    mapping['worker_bindings'][str(next_id)] = '99999'
    binding.write_text(json.dumps(mapping),encoding='utf-8')
    before = binding.read_bytes()
    response = client.post('/admin/workers/new',data=data)
    assert response.status_code == 422 and b'could not be added safely' in response.data
    assert OnboardingAgent.query.count() == count
    assert IndependentWorkerRegistration.query.count() == 0
    assert binding.read_bytes() == before


def test_database_binding_mode_creates_no_source_binding(app,client):
    app.config['NETEASE_BINDING_STORAGE']='database'
    login(client)
    assert client.post('/admin/workers/new',data=form(client)).status_code == 302
    worker = OnboardingAgent.query.filter_by(email='new.worker@example.com').one()
    assert db.session.get(IndependentWorkerRegistration,worker.id)
    assert not db.session.get(WorkerSourceBinding,worker.id)
