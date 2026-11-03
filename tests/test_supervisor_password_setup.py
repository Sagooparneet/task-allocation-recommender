from datetime import timedelta
import hashlib
import re

import pytest

from app.extensions import db
from app.models import Administrator, OnboardingAgent, Supervisor, SupervisorSetupInvitation, Task
from app.services.supervisor_setup import PENDING_PASSWORD, utcnow

PASSWORD = 'new-supervisor-passphrase-123'


@pytest.fixture()
def pending_supervisor(app):
    record = Supervisor(name='New Supervisor', email='new.supervisor@example.com',
                        password_hash=PENDING_PASSWORD, account_disabled=True)
    db.session.add(record)
    db.session.commit()
    return record.id


def login(client, email='admin@test.com'):
    return visit(client, 'POST', '/auth/login', data={'email': email, 'password': 'password123'})


def visit(client, method, path, **kwargs):
    with client.application.app_context():
        return client.open(path, method=method, **kwargs)


def invite(client, supervisor_id):
    login(client)
    path = f'/admin/supervisors/{supervisor_id}/setup'
    assert client.get(path).status_code == 200
    with client.session_transaction() as session:
        csrf = session['supervisor_setup_admin_csrf']
    response = client.post(path, data={'csrf_token': csrf, 'confirm': 'yes'})
    assert response.status_code == 200
    token = re.search(r'id="invitation-code" readonly value="([A-Za-z0-9_-]{43})"',
                      response.get_data(as_text=True)).group(1)
    return token, response


def setup_form(client, token, **changes):
    assert visit(client, 'GET', '/auth/supervisor-setup').status_code == 200
    with client.session_transaction() as session:
        data = {'csrf_token': session['supervisor_setup_public_csrf'],
                'setup_token': token, 'email': 'new.supervisor@example.com',
                'password': PASSWORD, 'password_confirm': PASSWORD}
    data.update(changes)
    return data


def test_invitation_activates_only_pending_supervisor(app, client, pending_supervisor):
    existing = Supervisor.query.filter_by(email='supervisor@test.com').one()
    original = (existing.password_hash, existing.account_disabled)
    counts = (OnboardingAgent.query.count(), Task.query.count())
    token, response = invite(client, pending_supervisor)
    assert response.headers['Cache-Control'] == 'no-store, private'
    assert response.headers['Referrer-Policy'] == 'no-referrer'
    row = db.session.get(SupervisorSetupInvitation, pending_supervisor, populate_existing=True)
    assert row.token_hash == hashlib.sha256(token.encode()).hexdigest()
    assert row.expires_at - row.issued_at == timedelta(hours=24)
    assert row.created_by_admin_id == Administrator.query.first().id
    assert row.consumed_at is None
    assert token.encode() not in client.get(f'/admin/supervisors/{pending_supervisor}/setup').data
    with client.session_transaction() as session:
        assert token not in str(dict(session))
    public = app.test_client()
    result = visit(public, 'POST', '/auth/supervisor-setup', data=setup_form(public, token))
    assert result.status_code == 302 and result.location.endswith('/auth/login')
    record = db.session.get(Supervisor, pending_supervisor, populate_existing=True)
    assert not record.account_disabled and record.check_password(PASSWORD)
    assert record.password_hash != PASSWORD
    assert db.session.get(SupervisorSetupInvitation, pending_supervisor, populate_existing=True).consumed_at is not None
    assert (existing.password_hash, existing.account_disabled) == original
    assert (OnboardingAgent.query.count(), Task.query.count()) == counts
    signed_in = visit(public, 'POST', '/auth/login', data={'email': record.email, 'password': PASSWORD})
    assert signed_in.status_code == 302 and signed_in.location.endswith('/supervisor/dashboard')
    assert visit(public, 'GET', '/supervisor/dashboard').status_code == 200
    assert client.get(f'/admin/supervisors/{pending_supervisor}/setup').status_code == 409


def test_reissue_invalidates_old_code_and_replay(app, client, pending_supervisor):
    first, _ = invite(client, pending_supervisor)
    second, _ = invite(client, pending_supervisor)
    assert first != second
    public = app.test_client()
    assert visit(public, 'POST', '/auth/supervisor-setup', data=setup_form(public, first)).status_code == 422
    assert visit(public, 'POST', '/auth/supervisor-setup', data=setup_form(public, second)).status_code == 302
    previous = db.session.get(Supervisor, pending_supervisor, populate_existing=True).password_hash
    assert visit(public, 'POST', '/auth/supervisor-setup', data=setup_form(public, second)).status_code == 422
    assert db.session.get(Supervisor, pending_supervisor, populate_existing=True).password_hash == previous


@pytest.mark.parametrize('case', ['expired', 'used', 'wrong_email', 'wrong_code'])
def test_invalid_code_cannot_enable_supervisor(app, client, pending_supervisor, case):
    token, _ = invite(client, pending_supervisor)
    row = db.session.get(SupervisorSetupInvitation, pending_supervisor, populate_existing=True)
    if case == 'expired':
        row.issued_at = utcnow() - timedelta(days=2)
        row.expires_at = utcnow() - timedelta(days=1)
    if case == 'used':
        row.consumed_at = utcnow()
    db.session.commit()
    public = app.test_client()
    data = setup_form(public, token)
    if case == 'wrong_email':
        data['email'] = 'other@example.com'
    if case == 'wrong_code':
        data['setup_token'] = 'A' * 43
    result = visit(public, 'POST', '/auth/supervisor-setup', data=data)
    assert result.status_code == 422
    assert b'invalid, expired, or already used' in result.data
    assert token.encode() not in result.data and PASSWORD.encode() not in result.data
    record = db.session.get(Supervisor, pending_supervisor, populate_existing=True)
    assert record.account_disabled and record.password_hash == PENDING_PASSWORD


def test_admin_only_csrf_and_existing_accounts(app, client, pending_supervisor):
    path = f'/admin/supervisors/{pending_supervisor}/setup'
    assert visit(client, 'POST', path).status_code == 302
    login(client, 'supervisor@test.com')
    assert visit(client, 'GET', path).status_code == 403
    visit(client, 'GET', '/auth/logout')
    login(client)
    existing = Supervisor.query.filter_by(email='supervisor@test.com').one()
    assert visit(client, 'GET', f'/admin/supervisors/{existing.id}/setup').status_code == 409
    assert visit(client, 'GET', path).status_code == 200
    assert visit(client, 'POST', path, data={'csrf_token': 'wrong', 'confirm': 'yes'}).status_code == 400
    assert SupervisorSetupInvitation.query.count() == 0
    token, _ = invite(client, pending_supervisor)
    public = app.test_client()
    assert visit(public, 'POST', '/auth/supervisor-setup', data=setup_form(public, token, csrf_token='wrong')).status_code == 400
    assert db.session.get(SupervisorSetupInvitation, pending_supervisor).consumed_at is None
    assert visit(client, 'POST', '/auth/supervisor-setup', data={'setup_token': token}).status_code == 403


def test_invalid_password_does_not_consume_code(app, client, pending_supervisor):
    token, _ = invite(client, pending_supervisor)
    public = app.test_client()
    result = visit(public, 'POST', '/auth/supervisor-setup', data=setup_form(public, token,
        password='short', password_confirm='different'))
    assert result.status_code == 422 and b'aria-invalid="true"' in result.data
    assert db.session.get(SupervisorSetupInvitation, pending_supervisor).consumed_at is None
