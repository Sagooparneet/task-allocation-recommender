"""First-time setup requires a separate code delivered to the registered email."""

from datetime import timedelta

import pytest

from app.extensions import db
from app.models import (
    Administrator, IndependentWorkerRegistration, OnboardingAgent,
    SetupEmailVerification, Supervisor, WorkerSetupInvitation,
    SupervisorSetupInvitation,
)
from app.services.independent_workers import PENDING_PASSWORD as WORKER_PENDING
from app.services.supervisor_setup import PENDING_PASSWORD as SUPERVISOR_PENDING
from app.services.worker_setup import issue_invitation as invite_worker
from app.services.supervisor_setup import issue_invitation as invite_supervisor
from app.services.invitation_email import EmailDeliveryError
import app.services.setup_email_codes as codes

PASSWORD = 'a-unique-password-long-enough-123'


@pytest.fixture()
def mail(monkeypatch):
    sent = []
    monkeypatch.setattr(codes, 'email_settings', lambda: ('sender@test.invalid', object(), 'http://localhost:5001'))
    monkeypatch.setattr(codes, 'send_verification_code',
                        lambda recipient, name, code, expiry, settings: sent.append((recipient, code, expiry)))
    return sent


def pending_account(role):
    admin_id = Administrator.query.first().id
    if role == 'worker':
        account = OnboardingAgent(name='Invited Worker', email='invited.worker@example.com',
                                  password_hash=WORKER_PENDING, account_disabled=True,
                                  availability=False, workload=0)
        db.session.add(account)
        db.session.flush()
        db.session.add(IndependentWorkerRegistration(agent_id=account.id, created_by_admin_id=admin_id))
    else:
        account = Supervisor(name='Invited Supervisor', email='invited.supervisor@example.com',
                             password_hash=SUPERVISOR_PENDING, account_disabled=True)
        db.session.add(account)
    db.session.commit()
    token, _ = (invite_worker if role == 'worker' else invite_supervisor)(account.id, admin_id)
    return account, token


def form(client, role, token, email, action, **extra):
    path = f'/auth/{role}-setup'
    assert client.get(path).status_code == 200
    with client.session_transaction() as session:
        csrf = session[f'{role}_setup_public_csrf']
    return path, {'csrf_token': csrf, 'setup_token': token, 'email': email,
                  'action': action, **extra}


@pytest.mark.parametrize('role', ['worker', 'supervisor'])
def test_code_required_before_new_account_is_enabled(app, role, mail):
    account, token = pending_account(role)
    client = app.test_client()
    path, data = form(client, role, token, account.email, 'send_code')
    response = client.post(path, data=data)
    assert response.status_code == 302
    assert response.location.endswith('#' + token)
    verification_page = client.get(response.location)
    assert verification_page.status_code == 200
    assert b'Email verification code' in verification_page.data
    assert token.encode() not in verification_page.data
    assert len(mail) == 1 and mail[0][0] == account.email
    code = mail[0][1]
    assert len(code) == 6 and code.isdigit()
    row = SetupEmailVerification.query.first()
    assert row.expires_at - row.issued_at == timedelta(minutes=10)
    assert code not in row.code_hash
    assert db.session.get(type(account), account.id, populate_existing=True).account_disabled
    assert (WorkerSetupInvitation if role == 'worker' else SupervisorSetupInvitation).query.first().consumed_at is None

    complete = {**data, 'action': 'complete', 'verification_code': code,
                'password': PASSWORD, 'password_confirm': PASSWORD}
    response = client.post(path, data=complete)
    assert response.status_code == 302 and response.location.endswith('/auth/login')
    account = db.session.get(type(account), account.id, populate_existing=True)
    assert not account.account_disabled and account.check_password(PASSWORD)
    assert SetupEmailVerification.query.count() == 0
    assert (WorkerSetupInvitation if role == 'worker' else SupervisorSetupInvitation).query.first().consumed_at is not None
    assert client.post(path, data=complete).status_code == 400  # setup CSRF was cleared


def test_wrong_code_is_limited_and_never_enables_worker(app, mail):
    account, token = pending_account('worker')
    client = app.test_client()
    path, data = form(client, 'worker', token, account.email, 'send_code')
    assert client.post(path, data=data).status_code == 302
    correct = mail[0][1]
    wrong = '000000' if correct != '000000' else '111111'
    complete = {**data, 'action': 'complete', 'verification_code': wrong,
                'password': PASSWORD, 'password_confirm': PASSWORD}
    for _ in range(codes.MAX_FAILED_ATTEMPTS):
        response = client.post(path, data=complete)
        assert response.status_code == 422
        assert b'aria-invalid="true"' in response.data
    challenge = SetupEmailVerification.query.first()
    assert challenge.failed_attempts == codes.MAX_FAILED_ATTEMPTS
    complete['verification_code'] = correct
    assert client.post(path, data=complete).status_code == 422
    assert db.session.get(OnboardingAgent, account.id, populate_existing=True).account_disabled
    assert db.session.get(WorkerSetupInvitation, account.id).consumed_at is None


def test_resend_throttles_and_rotates_the_code(app, mail):
    account, token = pending_account('worker')
    client = app.test_client()
    path, data = form(client, 'worker', token, account.email, 'send_code')
    assert client.post(path, data=data).status_code == 302
    first_hash = SetupEmailVerification.query.first().code_hash
    assert client.post(path, data=data).status_code == 422
    assert len(mail) == 1
    challenge = SetupEmailVerification.query.first()
    challenge.issued_at -= timedelta(minutes=2)
    challenge.last_sent_at -= timedelta(minutes=2)
    db.session.commit()
    assert client.post(path, data=data).status_code == 302
    assert len(mail) == 2
    assert SetupEmailVerification.query.first().send_count == 2
    assert SetupEmailVerification.query.first().code_hash != first_hash


def test_invalid_invitation_and_wrong_email_do_not_send(app, mail):
    account, token = pending_account('supervisor')
    client = app.test_client()
    path, data = form(client, 'supervisor', token, account.email, 'send_code')
    assert client.post(path, data={**data, 'email': 'other@example.com'}).status_code == 422
    assert client.post(path, data={**data, 'setup_token': 'A' * 43}).status_code == 422
    assert mail == []
    assert SetupEmailVerification.query.count() == 0
    assert db.session.get(Supervisor, account.id).account_disabled


def test_expired_code_and_reissued_invitation_cannot_activate(app, mail):
    account, token = pending_account('worker')
    client = app.test_client()
    path, data = form(client, 'worker', token, account.email, 'send_code')
    assert client.post(path, data=data).status_code == 302
    challenge = SetupEmailVerification.query.first()
    challenge.issued_at -= timedelta(minutes=11)
    challenge.expires_at = codes.utcnow() - timedelta(seconds=1)
    db.session.commit()
    complete = {**data, 'action': 'complete', 'verification_code': mail[0][1],
                'password': PASSWORD, 'password_confirm': PASSWORD}
    assert client.post(path, data=complete).status_code == 422
    assert db.session.get(OnboardingAgent, account.id, populate_existing=True).account_disabled
    replacement, _ = invite_worker(account.id, Administrator.query.first().id)
    assert replacement != token
    assert client.post(path, data=complete).status_code == 422
    assert db.session.get(WorkerSetupInvitation, account.id).consumed_at is None


def test_three_sends_per_invitation_and_delivery_failure_stay_safe(app, mail, monkeypatch):
    account, token = pending_account('supervisor')
    client = app.test_client()
    path, data = form(client, 'supervisor', token, account.email, 'send_code')
    assert client.post(path, data=data).status_code == 302
    for _ in range(2):
        challenge = SetupEmailVerification.query.first()
        challenge.issued_at -= timedelta(minutes=2)
        challenge.last_sent_at -= timedelta(minutes=2)
        db.session.commit()
        assert client.post(path, data=data).status_code == 302
    assert client.post(path, data=data).status_code == 422
    assert len(mail) == 3
    assert db.session.get(Supervisor, account.id, populate_existing=True).account_disabled

    replacement, _ = invite_supervisor(account.id, Administrator.query.first().id)
    monkeypatch.setattr(codes, 'send_verification_code',
                        lambda *args: (_ for _ in ()).throw(EmailDeliveryError('Unconfirmed')))
    assert client.post(path, data={**data, 'setup_token': replacement}).status_code == 422
    assert db.session.get(Supervisor, account.id, populate_existing=True).account_disabled
    assert db.session.get(SupervisorSetupInvitation, account.id).consumed_at is None
