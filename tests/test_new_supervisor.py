from app.extensions import db
from app.models import Administrator, OnboardingAgent, Supervisor, Task
from app.services.supervisor_setup import PENDING_PASSWORD


def login(client, email='admin@test.com'):
    return client.post('/auth/login', data={'email': email, 'password': 'password123'})


def form(client, name='New Supervisor', email='new.supervisor@example.com'):
    client.get('/admin/supervisors/new')
    with client.session_transaction() as state:
        token = state['supervisor_create_csrf_token']
    return {'csrf_token': token, 'name': name, 'email': email}


def test_add_supervisor_stays_disabled_until_password_setup(app, client):
    login(client)
    original = Supervisor.query.filter_by(email='supervisor@test.com').one()
    original_hash = original.password_hash
    before = (OnboardingAgent.query.count(), Task.query.count())
    response = client.post('/admin/supervisors/new', data=form(client))
    assert response.status_code == 302
    record = Supervisor.query.filter_by(email='new.supervisor@example.com').one()
    assert record.name == 'New Supervisor'
    assert record.account_disabled is True
    assert record.password_hash == PENDING_PASSWORD
    assert (OnboardingAgent.query.count(), Task.query.count()) == before
    assert db.session.get(Supervisor, original.id).password_hash == original_hash
    listing = client.get('/admin/supervisors')
    assert b'New Supervisor' in listing.data
    assert b'Awaiting password setup' in listing.data
    assert b'Add supervisor' in listing.data
    assert client.get(f'/admin/supervisors/{record.id}/account-status').status_code == 409
    client.get('/auth/logout')
    failed = client.post('/auth/login', data={'email': record.email, 'password': 'password123'})
    assert b'Invalid email or password' in failed.data


def test_only_administrator_can_add_supervisor(app, client):
    assert client.get('/admin/supervisors/new').status_code == 302
    login(client, 'supervisor@test.com')
    assert client.get('/admin/supervisors/new').status_code == 403
    assert client.post('/admin/supervisors/new', data={'name':'Unauthorized', 'email':'other@example.com'}).status_code == 403
    assert Supervisor.query.count() == 1


def test_invalid_duplicate_and_cross_role_email_do_not_create_account(app, client):
    login(client)
    response = client.post('/admin/supervisors/new', data=form(client, name='', email='bad'))
    assert response.status_code == 422 and b'Please check the supervisor details' in response.data
    assert Supervisor.query.count() == 1
    for existing in ('supervisor@test.com', 'admin@test.com', 'netease-6376@demo.invalid'):
        response = client.post('/admin/supervisors/new', data=form(client, email=existing))
        assert response.status_code == 422
    assert Supervisor.query.count() == 1


def test_csrf_and_replay_protection(app, client):
    login(client)
    data = form(client)
    wrong = dict(data, csrf_token='wrong')
    assert client.post('/admin/supervisors/new', data=wrong).status_code == 400
    assert client.post('/admin/supervisors/new', data=data).status_code == 302
    assert client.post('/admin/supervisors/new', data=data).status_code == 400
    assert Supervisor.query.filter_by(email=data['email']).count() == 1
