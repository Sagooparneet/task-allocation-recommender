from datetime import timedelta
import base64
import hashlib
from email import policy
from email.parser import BytesParser
import re
from types import SimpleNamespace

import pytest

from app.extensions import db
from app.models import Supervisor, SupervisorSetupInvitation, WorkerSetupInvitation
from app.services.supervisor_setup import issue_invitation, utcnow
import app.services.invitation_email as email_service
from test_supervisor_password_setup import pending_supervisor, visit, login, setup_form, PASSWORD


@pytest.fixture()
def fake_gmail(monkeypatch):
    calls = {'messages': [], 'requests': []}

    class Transport:
        def __init__(self, credentials):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def post(self, endpoint, **kwargs):
            calls['requests'].append((endpoint, kwargs))
            message = BytesParser(policy=policy.default).parsebytes(
                base64.urlsafe_b64decode(kwargs['json']['raw']))
            calls['messages'].append(message)
            return SimpleNamespace(status_code=200, json=lambda: {'id': 'fake-message-id'})

    monkeypatch.setattr(email_service, '_authorized_session', Transport)
    return calls


@pytest.fixture()
def gmail(app):
    app.config.update(INTELLITASK_GMAIL_ADDRESS='sender@gmail.com',
        INTELLITASK_INVITATION_BASE_URL='https://intellitask.example')
    app.extensions['intellitask_gmail_credentials'] = SimpleNamespace(refresh_token='fake-refresh-token')
    return app


def email_form(client, supervisor_id, **changes):
    login(client)
    visit(client, 'GET', f'/admin/supervisors/{supervisor_id}/setup')
    with client.session_transaction() as session:
        data = {'csrf_token': session['supervisor_setup_admin_csrf'],
                'confirm': 'yes', 'delivery': 'email'}
    data.update(changes)
    return data


def post(client, supervisor_id, data):
    return visit(client, 'POST', f'/admin/supervisors/{supervisor_id}/setup', data=data)


def test_email_goes_to_registered_supervisor_from_configured_sender_and_link(app, client, pending_supervisor, gmail, fake_gmail):
    response = post(client, pending_supervisor, email_form(client, pending_supervisor,
        recipient='attacker@example.com', base_url='https://attacker.example'))
    assert response.status_code == 200 and b'Invitation submitted to Gmail' in response.data
    message = fake_gmail['messages'][0]
    assert message['To'] == 'new.supervisor@example.com'
    assert message['From'] == 'sender@gmail.com'
    assert message['Subject'] == 'Set up your IntelliTask supervisor account'
    endpoint, kwargs = fake_gmail['requests'][0]
    assert endpoint == 'https://gmail.googleapis.com/gmail/v1/users/sender%40gmail.com/messages/send'
    assert kwargs['timeout'] == 20 and kwargs['allow_redirects'] is False
    body = message.get_content()
    token = re.search(r'https://intellitask.example/auth/supervisor-setup#([A-Za-z0-9_-]{43})', body).group(1)
    assert 'attacker' not in body and PASSWORD not in body
    row = db.session.get(SupervisorSetupInvitation, pending_supervisor, populate_existing=True)
    assert row.token_hash == hashlib.sha256(token.encode()).hexdigest()
    assert WorkerSetupInvitation.query.count() == 0
    public = app.test_client()
    assert visit(public, 'POST', '/auth/supervisor-setup', data=setup_form(public, token)).status_code == 302
    assert db.session.get(Supervisor, pending_supervisor, populate_existing=True).check_password(PASSWORD)


def test_unconfigured_email_does_not_replace_invitation(app, client, pending_supervisor, gmail, fake_gmail):
    data = email_form(client, pending_supervisor)
    token, _ = issue_invitation(pending_supervisor, 1)
    before = db.session.get(SupervisorSetupInvitation, pending_supervisor).token_hash
    app.extensions.pop('intellitask_gmail_credentials', None)
    response = post(client, pending_supervisor, data)
    assert response.status_code == 422 and b'has not been configured' in response.data
    assert db.session.get(SupervisorSetupInvitation, pending_supervisor, populate_existing=True).token_hash == before
    assert token.encode() not in response.data
    assert not fake_gmail['messages']


def test_delivery_failure_preserves_private_link_without_claiming_success(app, client, pending_supervisor, gmail, monkeypatch):
    class BrokenTransport:
        def __init__(self, *args):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def post(self, *args, **kwargs):
            raise OSError('private provider detail')

    monkeypatch.setattr(email_service, '_authorized_session', BrokenTransport)
    response = post(client, pending_supervisor, email_form(client, pending_supervisor))
    assert response.status_code == 200
    assert b'Email submission could not be confirmed' in response.data
    assert b'Invitation submitted to Gmail' not in response.data
    assert b'private provider detail' not in response.data
    token = re.search(r'id="invitation-code" readonly value="([A-Za-z0-9_-]{43})"',
                      response.get_data(as_text=True)).group(1)
    row = db.session.get(SupervisorSetupInvitation, pending_supervisor, populate_existing=True)
    assert row.token_hash == hashlib.sha256(token.encode()).hexdigest()
    assert row.consumed_at is None


def test_email_is_throttled_without_replacing_link(app, client, pending_supervisor, gmail, fake_gmail):
    data = email_form(client, pending_supervisor)
    assert post(client, pending_supervisor, data).status_code == 200
    first = db.session.get(SupervisorSetupInvitation, pending_supervisor, populate_existing=True).token_hash
    assert post(client, pending_supervisor, data).status_code == 422
    assert len(fake_gmail['messages']) == 1
    assert db.session.get(SupervisorSetupInvitation, pending_supervisor, populate_existing=True).token_hash == first
    row = db.session.get(SupervisorSetupInvitation, pending_supervisor)
    row.issued_at = utcnow() - timedelta(minutes=2)
    db.session.commit()
    assert post(client, pending_supervisor, data).status_code == 200
    assert len(fake_gmail['messages']) == 2
    assert db.session.get(SupervisorSetupInvitation, pending_supervisor, populate_existing=True).token_hash != first


def test_manual_works_without_gmail_and_invalid_requests_do_not_send(app, client, pending_supervisor, gmail, fake_gmail):
    data = email_form(client, pending_supervisor)
    assert post(client, pending_supervisor, {**data, 'csrf_token': 'wrong'}).status_code == 400
    assert post(client, pending_supervisor, {**data, 'confirm': ''}).status_code == 422
    assert post(client, pending_supervisor, {**data, 'delivery': 'invented'}).status_code == 422
    assert not fake_gmail['messages'] and SupervisorSetupInvitation.query.count() == 0
    app.extensions.pop('intellitask_gmail_credentials', None)
    response = post(client, pending_supervisor, {**data, 'delivery': 'manual'})
    assert response.status_code == 200 and b'No email has been sent' in response.data
    assert not fake_gmail['messages']


def test_other_roles_and_completed_accounts_cannot_send_email(app, client, pending_supervisor, gmail, fake_gmail):
    login(client, 'supervisor@test.com')
    assert post(client, pending_supervisor, {'confirm': 'yes', 'delivery': 'email'}).status_code == 403
    assert not fake_gmail['messages']
    visit(client, 'GET', '/auth/logout')
    login(client)
    record = db.session.get(Supervisor, pending_supervisor)
    record.set_password(PASSWORD)
    record.account_disabled = False
    db.session.commit()
    assert post(client, pending_supervisor, {'confirm': 'yes', 'delivery': 'email'}).status_code == 409
    assert not fake_gmail['messages']
