from app.extensions import db
from app.models import OnboardingAgent, Supervisor, WorkerSourceBinding
from app.services.account_display_name import account_display_name
from app.services.worker_display_names import worker_display_name


def test_file_binding_renders_alias_without_changing_account(app, client):
    with app.app_context():
        worker = OnboardingAgent.query.filter_by(email='netease-6376@demo.invalid').one()
        before = (worker.id, worker.name, worker.email, worker.password_hash, worker.workload)
    client.post('/auth/login', data={'email': 'netease-6376@demo.invalid', 'password': 'password123'})
    response = client.get('/agent/dashboard')
    assert response.status_code == 200
    assert worker_display_name('6376').encode() in response.data
    assert b'Grace Test' not in response.data
    with app.app_context():
        worker = db.session.get(OnboardingAgent, before[0])
        assert (worker.id, worker.name, worker.email, worker.password_hash, worker.workload) == before


def test_database_binding_uses_same_alias(app):
    app.config['NETEASE_BINDING_STORAGE'] = 'database'
    with app.app_context():
        worker = OnboardingAgent.query.filter_by(email='netease-6376@demo.invalid').one()
        db.session.add(WorkerSourceBinding(agent_id=worker.id, source_worker_id='6376'))
        db.session.commit()
        assert account_display_name(worker) == worker_display_name('6376')


def test_email_mismatch_does_not_borrow_history_identity(app):
    with app.app_context():
        worker = OnboardingAgent.query.filter_by(email='netease-6376@demo.invalid').one()
        worker.email = 'someone-else@example.com'
        assert account_display_name(worker) == worker.name


def test_supervisor_keeps_own_name_and_unmapped_agent_falls_back(app):
    app.config['NETEASE_BINDING_STORAGE'] = 'database'
    with app.app_context():
        supervisor = Supervisor.query.one()
        assert account_display_name(supervisor) == supervisor.name
        worker = OnboardingAgent.query.first()
        assert account_display_name(worker) == worker.name
