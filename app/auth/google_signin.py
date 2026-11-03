"""Google OpenID Connect sign-in for already approved IntelliTask accounts."""

from datetime import datetime, timezone
import base64
import hashlib
import json
import secrets
import time
from pathlib import Path
from urllib.parse import urlencode

from flask import current_app, flash, redirect, request, session, url_for
from flask_login import current_user, login_user
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2 import id_token
import requests

from app.extensions import db
from app.models import (Administrator, GoogleIdentity, IndependentWorkerRegistration,
                        OnboardingAgent, Supervisor)


AUTH_URL = 'https://accounts.google.com/o/oauth2/v2/auth'
TOKEN_URL = 'https://oauth2.googleapis.com/token'
CALLBACK_PATH = '/auth/google/callback'
ATTEMPT_KEY = 'google_signin_attempt'


def settings():
    """A private Web client file is convenient locally; env values work on hosting."""
    client_id = current_app.config.get('INTELLITASK_GOOGLE_SIGNIN_CLIENT_ID')
    secret = current_app.config.get('INTELLITASK_GOOGLE_SIGNIN_CLIENT_SECRET')
    redirect_uri = current_app.config.get('INTELLITASK_GOOGLE_SIGNIN_REDIRECT_URI')
    filename = current_app.config.get('INTELLITASK_GOOGLE_SIGNIN_CLIENT_FILE')
    if filename:
        try:
            content = json.loads(Path(filename).read_text(encoding='utf-8'))['web']
            client_id = content['client_id']
            secret = content['client_secret']
            allowed = content['redirect_uris']
        except (OSError, ValueError, KeyError, TypeError):
            return None
        if redirect_uri not in allowed:
            return None
    if not all((client_id, secret, redirect_uri)):
        return None
    if not redirect_uri.endswith(CALLBACK_PATH):
        return None
    if not (redirect_uri.startswith('https://') or
            redirect_uri.startswith('http://127.0.0.1:5001/') or
            redirect_uri.startswith('http://localhost:5001/')):
        return None
    return client_id, secret, redirect_uri


def google_signin_available():
    return settings() is not None


def start():
    if current_user.is_authenticated:
        from app.auth.routes import redirect_by_role
        return redirect_by_role(current_user)
    configured = settings()
    if configured is None:
        flash('Google sign-in is not available yet. Use your password.', 'info')
        return redirect(url_for('auth.login'))
    client_id, _, redirect_uri = configured
    state, nonce, verifier = (secrets.token_urlsafe(32) for _ in range(3))
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode('ascii')).digest()).rstrip(b'=').decode('ascii')
    session[ATTEMPT_KEY] = {'state': state, 'nonce': nonce, 'verifier': verifier,
                            'started': time.time()}
    query = urlencode({'client_id': client_id, 'redirect_uri': redirect_uri,
                       'response_type': 'code', 'scope': 'openid email',
                       'state': state, 'nonce': nonce, 'prompt': 'select_account',
                       'code_challenge': challenge, 'code_challenge_method': 'S256'})
    response = redirect(AUTH_URL + '?' + query)
    response.headers['Cache-Control'] = 'no-store'
    response.headers['Referrer-Policy'] = 'no-referrer'
    return response


def _exchange(code, configured, verifier):
    client_id, secret, redirect_uri = configured
    response = requests.post(TOKEN_URL, data={
        'code': code, 'client_id': client_id, 'client_secret': secret,
        'redirect_uri': redirect_uri, 'grant_type': 'authorization_code',
        'code_verifier': verifier,
    }, timeout=15)
    response.raise_for_status()
    token = response.json().get('id_token')
    if not isinstance(token, str) or not token:
        raise ValueError('Missing ID token')
    return id_token.verify_oauth2_token(token, GoogleRequest(), client_id)


def _account_for_email(email):
    matches = []
    for model in (Supervisor, OnboardingAgent, Administrator):
        account = model.query.filter_by(email=email).first()
        if account is not None:
            matches.append(account)
    if len(matches) != 1:
        return None
    account = matches[0]
    if not account.is_active or account.password_hash.startswith('!pending-'):
        return None
    if account.role == 'agent' and db.session.get(IndependentWorkerRegistration, account.id) is None:
        return None
    return account


def _linked_account(identity):
    if identity.worker_id is not None:
        return db.session.get(OnboardingAgent, identity.worker_id)
    if identity.supervisor_id is not None:
        return db.session.get(Supervisor, identity.supervisor_id)
    return db.session.get(Administrator, identity.administrator_id)


def _identity_fields(account):
    return {'agent': {'worker_id': account.id},
            'supervisor': {'supervisor_id': account.id},
            'administrator': {'administrator_id': account.id}}[account.role]


def _approved_account(claims):
    subject = claims.get('sub')
    raw_email = claims.get('email')
    email = raw_email.strip().lower() if isinstance(raw_email, str) else ''
    if (not isinstance(subject, str) or not subject or len(subject) > 255 or
            not isinstance(email, str) or not email or claims.get('email_verified') is not True):
        return None
    # Google is authoritative for Gmail and hosted Google Workspace addresses.
    # Another provider's verified address may have changed hands after verification.
    if not (email.endswith('@gmail.com') or claims.get('hd')):
        return None
    identity = db.session.get(GoogleIdentity, subject)
    account = _linked_account(identity) if identity else _account_for_email(email)
    if (account is None or not account.is_active or
            account.password_hash.startswith('!pending-') or
            account.email.lower() != email):
        return None
    if account.role == 'agent' and db.session.get(IndependentWorkerRegistration, account.id) is None:
        return None
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if identity is None:
        fields = _identity_fields(account)
        if GoogleIdentity.query.filter_by(**fields).first() is not None:
            return None
        db.session.add(GoogleIdentity(subject=subject, linked_at=now,
                                      last_login_at=now, **fields))
    else:
        identity.last_login_at = now
    db.session.commit()
    return account


def callback():
    attempt = session.pop(ATTEMPT_KEY, None)
    if current_user.is_authenticated:
        from app.auth.routes import redirect_by_role
        return redirect_by_role(current_user)
    configured = settings()
    state = request.args.get('state', '')
    code = request.args.get('code', '')
    if (not isinstance(attempt, dict) or configured is None or
            not isinstance(state, str) or not secrets.compare_digest(state, attempt.get('state', '')) or
            time.time() - attempt.get('started', 0) > 600 or
            not isinstance(code, str) or not code or len(code) > 4096 or
            request.args.get('error')):
        flash('Google sign-in could not be completed. Please try again.', 'error')
        return redirect(url_for('auth.login'))
    try:
        claims = _exchange(code, configured, attempt['verifier'])
        if not secrets.compare_digest(claims.get('nonce', ''), attempt['nonce']):
            raise ValueError('Nonce mismatch')
        account = _approved_account(claims)
    except Exception:
        account = None
    if account is None:
        flash('Google sign-in is available only for an active account with the same registered email. You can still use your password.', 'error')
        return redirect(url_for('auth.login'))
    session.clear()
    login_user(account, fresh=True)
    flash('Login successful.', 'success')
    from app.auth.routes import redirect_by_role
    return redirect_by_role(account)
