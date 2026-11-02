"""Offline checks: fake OAuth responses, genuine Windows encryption on Windows."""
import importlib.util
import base64
import hashlib
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest


SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


load('check_gmail_oauth_client')
storage = load('gmail_local_credentials')
setup = load('connect_gmail_sender')


class Credentials:
    valid = True
    granted_scopes = [storage.SENDING_SCOPE]
    scopes = [storage.SENDING_SCOPE]

    def to_json(self):
        return json.dumps({'token': 'fake-access-token', 'refresh_token': 'fake-refresh-token',
                           'token_uri': 'https://oauth2.googleapis.com/token',
                           'client_id': 'fake.apps.googleusercontent.com',
                           'client_secret': 'fake-client-secret', 'scopes': self.scopes})


class Flow:
    credentials = Credentials()

    def __init__(self):
        self.calls = []

    def fetch_token(self, **kwargs):
        self.calls.append(kwargs)


@pytest.fixture
def attempt(tmp_path):
    saved = []
    flow = Flow()
    value = setup.AuthorizationAttempt(flow, 'expected-state', tmp_path / 'token',
                                       saver=lambda credentials, path: saved.append((credentials, path)))
    value.saved = saved
    return value


def test_success_exchanges_once_and_saves_without_returning_tokens(attempt):
    attempt.complete({'state': ['expected-state'], 'code': ['fake-code']})
    assert attempt.success and len(attempt.saved) == 1
    assert attempt.flow.calls == [{'code': 'fake-code', 'timeout': 30, 'allow_redirects': False}]
    assert 'fake-access-token' not in attempt.message
    with pytest.raises(setup.SetupError):
        attempt.complete({'state': ['expected-state'], 'code': ['fake-code']})
    assert len(attempt.flow.calls) == 1


@pytest.mark.parametrize('state', [[], ['wrong'], ['expected-state', 'expected-state'], ['é']])
def test_wrong_or_duplicate_state_never_exchanges(attempt, state):
    with pytest.raises(setup.SetupError):
        attempt.complete({'state': state, 'code': ['fake-code']})
    assert not attempt.flow.calls and not attempt.saved and not attempt.used


def test_expired_attempt_never_exchanges(attempt):
    attempt.deadline = 0
    with pytest.raises(setup.SetupError):
        attempt.complete({'state': ['expected-state'], 'code': ['fake-code']})
    assert not attempt.flow.calls


def test_denied_permission_does_not_save_or_echo_google_error(attempt):
    attempt.complete({'state': ['expected-state'], 'error': ['private-sensitive-error']})
    assert attempt.used and not attempt.success and not attempt.saved
    assert 'private-sensitive-error' not in attempt.message


@pytest.mark.parametrize('code', [[], [''], ['a', 'b'], ['x' * 4097]])
def test_missing_or_ambiguous_code_is_rejected(attempt, code):
    attempt.complete({'state': ['expected-state'], 'code': code})
    assert attempt.used and not attempt.success and not attempt.flow.calls


def test_network_exception_is_redacted(attempt):
    def fail(**kwargs):
        raise RuntimeError('private-refresh-token private-client-secret')
    attempt.flow.fetch_token = fail
    attempt.complete({'state': ['expected-state'], 'code': ['fake-code']})
    assert not attempt.success and not attempt.saved
    assert 'private-' not in attempt.message


def test_storage_failure_is_not_success(attempt):
    def fail(*args):
        raise OSError('private details')
    attempt.saver = fail
    attempt.complete({'state': ['expected-state'], 'code': ['fake-code']})
    assert not attempt.success and 'private details' not in attempt.message


def test_refuses_storage_inside_repository(tmp_path, monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))
    with pytest.raises(ValueError):
        storage.credential_path(tmp_path)


@pytest.mark.skipif(os.name != 'nt', reason='Windows DPAPI integration check')
def test_windows_encryption_roundtrip_and_no_plaintext_on_disk(tmp_path):
    path = tmp_path / 'sender.dpapi'
    storage.save_credentials(Credentials(), path)
    raw = path.read_bytes()
    assert raw.startswith(storage.MAGIC)
    assert b'fake-refresh-token' not in raw and b'fake-client-secret' not in raw
    recovered = storage.load_credentials(path)
    assert recovered.refresh_token == 'fake-refresh-token'
    assert recovered.client_id == 'fake.apps.googleusercontent.com'
    assert recovered.scopes == [storage.SENDING_SCOPE]


def test_missing_refresh_token_preserves_previous_connection(tmp_path):
    path = tmp_path / 'sender.dpapi'
    path.write_bytes(b'previous-connection')
    credentials = Credentials()
    credentials.to_json = lambda: json.dumps({'token': 'fake-token'})
    with pytest.raises(ValueError):
        storage.save_credentials(credentials, path)
    assert path.read_bytes() == b'previous-connection'


def test_extra_mail_permissions_are_rejected_before_writing(tmp_path):
    credentials = Credentials()
    credentials.granted_scopes = [storage.SENDING_SCOPE, 'https://mail.google.com/']
    path = tmp_path / 'sender.dpapi'
    with pytest.raises(ValueError):
        storage.save_credentials(credentials, path)
    assert not path.exists()


def test_callback_cleans_address_and_logs_no_secrets(attempt):
    # Exercise the HTTP dispatcher without a real server or network.
    handler = setup.handler_for(attempt, 'https://accounts.google.com/example', 'start-key')
    instance = object.__new__(handler)
    instance.headers = {'Host': 'localhost:5001'}
    instance.path = '/admin/email/oauth/callback?state=expected-state&code=fake-code'
    instance.server = SimpleNamespace(finished=False)
    replies = []
    instance.reply = lambda *args, **kwargs: replies.append((args, kwargs))
    instance.do_GET()
    assert replies == [((303,), {'location': '/gmail-setup-complete'})]
    instance.path = '/gmail-setup-complete'
    instance.do_GET()
    assert instance.server.finished and attempt.success


def test_bad_host_cannot_start_or_complete_setup(attempt):
    handler = setup.handler_for(attempt, 'https://accounts.google.com/example', 'start-key')
    instance = object.__new__(handler)
    instance.headers = {'Host': 'attacker.invalid'}
    instance.path = '/admin/email/oauth/callback?state=expected-state&code=fake-code'
    replies = []
    instance.reply = lambda *args, **kwargs: replies.append(args)
    instance.do_GET()
    assert replies[0][0] == 400 and not attempt.flow.calls


def test_real_library_generates_google_url_with_pkce_and_sending_only():
    document = {'web': {'client_id': 'fake.apps.googleusercontent.com',
                        'client_secret': 'fake-secret-not-a-real-credential',
                        'auth_uri': 'https://accounts.google.com/o/oauth2/v2/auth',
                        'token_uri': 'https://oauth2.googleapis.com/token',
                        'redirect_uris': [setup.CALLBACK]}}
    verifier = 'v' * 86
    flow = setup.Flow.from_client_config(document, scopes=[storage.SENDING_SCOPE],
                                         redirect_uri=setup.CALLBACK, code_verifier=verifier)
    url, state = flow.authorization_url(access_type='offline', prompt='consent select_account',
                                        login_hint=setup.SENDER, include_granted_scopes='false')
    parsed = urlsplit(url)
    values = parse_qs(parsed.query)
    assert parsed.scheme == 'https' and parsed.hostname == 'accounts.google.com'
    assert values['state'] == [state]
    assert values['redirect_uri'] == [setup.CALLBACK]
    assert values['scope'] == [storage.SENDING_SCOPE]
    assert values['code_challenge_method'] == ['S256']
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
    assert values['code_challenge'] == [challenge]
    assert 'fake-secret-not-a-real-credential' not in url and verifier not in url
