"""Google sign-in links only existing, active, verified accounts."""

from urllib.parse import parse_qs, urlsplit

import pytest
from flask import g

from app.extensions import db
from app.models import GoogleIdentity, IndependentWorkerRegistration, OnboardingAgent, Supervisor
from app.auth import google_signin


@pytest.fixture
def configured(app):
    app.config.update(
        INTELLITASK_GOOGLE_SIGNIN_CLIENT_ID='test-client',
        INTELLITASK_GOOGLE_SIGNIN_CLIENT_SECRET='test-secret',
        INTELLITASK_GOOGLE_SIGNIN_REDIRECT_URI='http://127.0.0.1:5001/auth/google/callback',
        INTELLITASK_GOOGLE_SIGNIN_CLIENT_FILE=None,
    )
    return app


def begin(client):
    response = client.get('/auth/google')
    assert response.status_code == 302
    query = parse_qs(urlsplit(response.headers['Location']).query)
    assert query['scope'] == ['openid email']
    assert query['code_challenge_method'] == ['S256']
    assert query['redirect_uri'] == ['http://127.0.0.1:5001/auth/google/callback']
    return query


def callback(client, query, *, state=None):
    return client.get('/auth/google/callback', query_string={
        'state': state if state is not None else query['state'][0], 'code': 'sample-code',
    })


def test_button_requires_configuration(app, client):
    app.config.update(
        INTELLITASK_GOOGLE_SIGNIN_CLIENT_FILE=None,
        INTELLITASK_GOOGLE_SIGNIN_CLIENT_ID=None,
        INTELLITASK_GOOGLE_SIGNIN_CLIENT_SECRET=None,
        INTELLITASK_GOOGLE_SIGNIN_REDIRECT_URI=None,
    )
    assert b'Continue with Google' not in client.get('/auth/login').data
    assert client.get('/auth/google').status_code == 302


def test_supervisor_links_once_and_signs_in(configured, client, monkeypatch):
    assert b'Continue with Google' in client.get('/auth/login').data
    query = begin(client)
    monkeypatch.setattr(google_signin, '_exchange', lambda code, settings, verifier: {
        'sub': 'google-subject-1', 'email': 'supervisor@gmail.com',
        'email_verified': True, 'nonce': query['nonce'][0],
    })
    with configured.app_context():
        supervisor = Supervisor.query.filter_by(email='supervisor@test.com').one()
        supervisor.email = 'supervisor@gmail.com'
        db.session.commit()
        supervisor_id = supervisor.id
    response = callback(client, query)
    assert response.status_code == 302
    assert '/supervisor/dashboard' in response.headers['Location']
    with configured.app_context():
        assert GoogleIdentity.query.one().supervisor_id == supervisor_id
    g.pop('_login_user', None)
    assert client.get('/supervisor/dashboard').status_code == 200
    client.get('/auth/logout')
    g.pop('_login_user', None)
    second = begin(client)
    monkeypatch.setattr(google_signin, '_exchange', lambda code, settings, verifier: {
        'sub': 'google-subject-1', 'email': 'supervisor@gmail.com',
        'email_verified': True, 'nonce': second['nonce'][0],
    })
    assert '/supervisor/dashboard' in callback(client, second).headers['Location']
    with configured.app_context():
        assert GoogleIdentity.query.count() == 1


def test_rejects_wrong_state_and_nonce(configured, client, monkeypatch):
    query = begin(client)
    assert callback(client, query, state='wrong').headers['Location'].endswith('/auth/login')
    assert callback(client, query).headers['Location'].endswith('/auth/login')
    query = begin(client)
    monkeypatch.setattr(google_signin, '_exchange', lambda code, settings, verifier: {
        'sub': 's', 'email': 'supervisor@gmail.com', 'email_verified': True, 'nonce': 'wrong',
    })
    assert callback(client, query).headers['Location'].endswith('/auth/login')
    with configured.app_context():
        assert GoogleIdentity.query.count() == 0


def test_no_account_or_dataset_worker_created(configured, client, monkeypatch):
    query = begin(client)
    monkeypatch.setattr(google_signin, '_exchange', lambda code, settings, verifier: {
        'sub': 'unknown', 'email': 'unknown@gmail.com',
        'email_verified': True, 'nonce': query['nonce'][0],
    })
    assert callback(client, query).headers['Location'].endswith('/auth/login')
    with configured.app_context():
        worker = OnboardingAgent.query.first()
        worker.email = 'dataset@gmail.com'
        db.session.commit()
    query = begin(client)
    monkeypatch.setattr(google_signin, '_exchange', lambda code, settings, verifier: {
        'sub': 'dataset', 'email': 'dataset@gmail.com',
        'email_verified': True, 'nonce': query['nonce'][0],
    })
    assert callback(client, query).headers['Location'].endswith('/auth/login')
    with configured.app_context():
        assert GoogleIdentity.query.count() == 0
        assert OnboardingAgent.query.count() == 2


def test_disabled_supervisor_and_unverified_email_rejected(configured, client, monkeypatch):
    with configured.app_context():
        supervisor = Supervisor.query.first()
        supervisor.email = 'supervisor@gmail.com'
        supervisor.account_disabled = True
        db.session.commit()
    query = begin(client)
    monkeypatch.setattr(google_signin, '_exchange', lambda code, settings, verifier: {
        'sub': 'disabled', 'email': 'supervisor@gmail.com',
        'email_verified': True, 'nonce': query['nonce'][0],
    })
    assert callback(client, query).headers['Location'].endswith('/auth/login')
    with configured.app_context():
        Supervisor.query.first().account_disabled = False
        db.session.commit()
    query = begin(client)
    monkeypatch.setattr(google_signin, '_exchange', lambda code, settings, verifier: {
        'sub': 'unverified', 'email': 'supervisor@gmail.com',
        'email_verified': False, 'nonce': query['nonce'][0],
    })
    assert callback(client, query).headers['Location'].endswith('/auth/login')


def test_third_party_email_requires_another_signin_method(configured, client, monkeypatch):
    query = begin(client)
    monkeypatch.setattr(google_signin, '_exchange', lambda code, settings, verifier: {
        'sub': 'third-party', 'email': 'supervisor@test.com',
        'email_verified': True, 'nonce': query['nonce'][0],
    })
    assert callback(client, query).headers['Location'].endswith('/auth/login')
    with configured.app_context():
        assert GoogleIdentity.query.count() == 0
