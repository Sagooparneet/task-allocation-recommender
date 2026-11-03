"""Password-reset links must be private, single-use, and limited to active accounts."""

from datetime import timedelta
import hashlib

import pytest
from flask import g

from app.extensions import db
from app.models import (
    Administrator, IndependentWorkerRegistration, OnboardingAgent,
    PasswordResetRequest, PasswordResetToken, Supervisor,
)
from app.services import password_reset as reset


@pytest.fixture
def mail(monkeypatch, app):
    sent = []
    changed = []
    monkeypatch.setattr(reset, 'email_settings', lambda: ('sender@test.invalid', object(), 'http://127.0.0.1:5001'))
    monkeypatch.setattr(reset, 'send_password_reset_email',
                        lambda recipient, name, token, expiry, settings: sent.append((recipient, token)))
    monkeypatch.setattr(reset, 'send_password_changed_email',
                        lambda recipient, name, settings: changed.append(recipient))
    return sent, changed


def csrf(client):
    response = client.get('/auth/forgot-password')
    assert response.status_code == 200
    with client.session_transaction() as state:
        return state['password_reset_public_csrf']


def request_link(client, email):
    token = csrf(client)
    return client.post('/auth/forgot-password', data={'csrf_token': token, 'email': email}, follow_redirects=True)


def reset_form(client, token, password='A long new password 123'):
    client.get('/auth/reset-password')
    with client.session_transaction() as state:
        csrf_token = state['password_reset_public_csrf']
    return client.post('/auth/reset-password', data={
        'csrf_token': csrf_token, 'reset_token': token,
        'password': password, 'password_confirm': password,
    })


def test_supervisor_reset_is_one_time_and_revokes_prior_session(app, client, mail):
    assert client.post('/auth/login', data={
        'email': 'supervisor@test.com', 'password': 'password123',
    }).status_code == 302
    old_browser = client
    second_browser = app.test_client()
    g.pop('_login_user', None)
    response = request_link(second_browser, 'supervisor@test.com')
    assert response.status_code == 200
    assert b'If an active account matches' in response.data
    sent, changed = mail
    assert len(sent) == 1 and sent[0][0] == 'supervisor@test.com'
    token = sent[0][1]
    assert token.encode() not in response.data
    with app.app_context():
        row = PasswordResetToken.query.one()
        assert row.token_hash == hashlib.sha256(token.encode()).hexdigest()
        assert row.expires_at - row.issued_at == timedelta(minutes=30)
    assert reset_form(second_browser, token).status_code == 302
    assert changed == ['supervisor@test.com']
    assert b'invalid, expired, or already used' in reset_form(second_browser, token).data
    with app.app_context():
        account = Supervisor.query.filter_by(email='supervisor@test.com').one()
        assert account.check_password('A long new password 123')
        assert not account.check_password('password123')
    g.pop('_login_user', None)
    assert old_browser.get('/supervisor/dashboard').status_code == 302
    g.pop('_login_user', None)
    assert second_browser.post('/auth/login', data={
        'email': 'supervisor@test.com', 'password': 'A long new password 123',
    }).status_code == 302


def test_unknown_and_dataset_worker_receive_same_message_without_email(app, client, mail):
    unknown = request_link(client, 'unknown@example.com')
    dataset = request_link(client, 'netease-6376@demo.invalid')
    assert unknown.status_code == dataset.status_code == 200
    assert unknown.data == dataset.data
    assert mail[0] == []
    with app.app_context():
        assert PasswordResetRequest.query.count() == 2
        assert PasswordResetToken.query.count() == 0


def test_rate_limit_and_expiration(app, client, mail):
    for _ in range(4):
        assert request_link(client, 'supervisor@test.com').status_code == 200
    assert len(mail[0]) == 3
    with app.app_context():
        rows = PasswordResetToken.query.order_by(PasswordResetToken.id).all()
        assert len(rows) == 3
        assert all(row.used_at is not None for row in rows[:-1])
        rows[-1].issued_at = reset.utcnow() - timedelta(hours=1)
        rows[-1].expires_at = reset.utcnow() - timedelta(seconds=1)
        db.session.commit()
    assert b'invalid, expired, or already used' in reset_form(client, mail[0][-1][1]).data


def test_disabled_supervisor_and_bad_csrf_do_not_send(app, client, mail):
    with app.app_context():
        Supervisor.query.filter_by(email='supervisor@test.com').one().account_disabled = True
        db.session.commit()
    assert request_link(client, 'supervisor@test.com').status_code == 200
    assert mail[0] == []
    assert client.post('/auth/forgot-password', data={
        'csrf_token': 'wrong', 'email': 'admin@test.com',
    }).status_code == 400


def test_administrator_can_reset_and_bad_password_does_not_consume(app, client, mail):
    request_link(client, 'admin@test.com')
    token = mail[0][0][1]
    client.get('/auth/reset-password')
    with client.session_transaction() as state:
        csrf_token = state['password_reset_public_csrf']
    response = client.post('/auth/reset-password', data={
        'csrf_token': csrf_token, 'reset_token': token,
        'password': 'short', 'password_confirm': 'short',
    })
    assert response.status_code == 422
    assert reset_form(client, token).status_code == 302


def test_no_account_enumeration_on_valid_requests(app, client, mail):
    real = request_link(client, 'supervisor@test.com')
    fake = request_link(client, 'person@example.com')
    assert real.status_code == fake.status_code
    assert real.data == fake.data
    assert b'supervisor@test.com' not in real.data


def test_independent_worker_can_reset_but_disabled_worker_cannot(app, client, mail):
    with app.app_context():
        worker = OnboardingAgent(
            name='Independent Worker', email='independent@example.com',
            availability=True, workload=0,
        )
        worker.set_password('Old worker password 123')
        db.session.add(worker)
        db.session.flush()
        db.session.add(IndependentWorkerRegistration(
            agent_id=worker.id, created_by_admin_id=Administrator.query.one().id,
        ))
        db.session.commit()
        worker_id = worker.id
    assert request_link(client, 'independent@example.com').status_code == 200
    token = mail[0][-1][1]
    assert reset_form(client, token).status_code == 302
    with app.app_context():
        worker = db.session.get(OnboardingAgent, worker_id)
        assert worker.check_password('A long new password 123')
        worker.account_disabled = True
        db.session.commit()
    assert request_link(client, 'independent@example.com').status_code == 200
    assert len(mail[0]) == 1
