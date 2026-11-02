"""One-time initial password setup; never resets existing or dataset accounts."""
from datetime import datetime, timedelta, timezone
import hashlib
import re
import secrets
from flask import make_response
from sqlalchemy import exists, update
from werkzeug.security import generate_password_hash
from app.extensions import db
from app.models import OnboardingAgent, IndependentWorkerRegistration, WorkerSetupInvitation
from app.services.independent_workers import PENDING_PASSWORD, require_unbound_identity

LIFETIME = timedelta(hours=24)
INVALID_INVITATION = 'This setup invitation is invalid, expired, or already used. Ask your administrator for a new one.'


class SetupUnavailable(ValueError):
    pass


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def private_response(body, status=None):
    response = make_response(body) if status is None else make_response(body, status)
    response.headers['Cache-Control'] = 'no-store, private'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['X-Robots-Tag'] = 'noindex, nofollow'
    return response


def lock_pending_worker(agent_id):
    # Same row is locked by issue and redemption before touching its invitation.
    # A no-op UPDATE works for both SQLite and PostgreSQL.
    changed = db.session.execute(update(OnboardingAgent).where(
        OnboardingAgent.id == agent_id,
        OnboardingAgent.password_hash == PENDING_PASSWORD,
        OnboardingAgent.account_disabled.is_(True),
        exists().where(IndependentWorkerRegistration.agent_id == OnboardingAgent.id),
    ).values(workload=OnboardingAgent.workload).execution_options(synchronize_session=False)).rowcount
    if changed != 1:
        raise SetupUnavailable(INVALID_INVITATION)
    require_unbound_identity(agent_id)


def issue_invitation(agent_id, administrator_id, minimum_interval=None):
    try:
        lock_pending_worker(agent_id)
        token = secrets.token_urlsafe(32)
        digest = hashlib.sha256(token.encode('ascii')).hexdigest()
        now = utcnow()
        invitation = db.session.get(WorkerSetupInvitation, agent_id, populate_existing=True)
        if (minimum_interval is not None and invitation is not None
                and now - invitation.issued_at < minimum_interval):
            raise ValueError('Please wait one minute before emailing another invitation.')
        if invitation is None:
            invitation = WorkerSetupInvitation(agent_id=agent_id)
            db.session.add(invitation)
        invitation.token_hash = digest
        invitation.created_by_admin_id = administrator_id
        invitation.issued_at = now
        invitation.expires_at = now + LIFETIME
        invitation.consumed_at = None
        expiry = invitation.expires_at
        db.session.commit()
        return token, expiry
    except Exception:
        db.session.rollback()
        raise


def redeem_invitation(token, email, password):
    if not re.fullmatch(r'[A-Za-z0-9_-]{43}', token or ''):
        raise SetupUnavailable(INVALID_INVITATION)
    if not 12 <= len(password) <= 128 or not password.strip():
        raise ValueError('Choose a password of 12 to 128 characters.')
    digest = hashlib.sha256(token.encode('ascii')).hexdigest()
    try:
        invitation = WorkerSetupInvitation.query.join(
            OnboardingAgent, OnboardingAgent.id == WorkerSetupInvitation.agent_id
        ).filter(WorkerSetupInvitation.token_hash == digest,
                 OnboardingAgent.email == email,
                 WorkerSetupInvitation.consumed_at.is_(None),
                 WorkerSetupInvitation.expires_at > utcnow()).first()
        if invitation is None:
            raise SetupUnavailable(INVALID_INVITATION)
        agent_id = invitation.agent_id
        # Hash before taking the write lock; then recheck expiry and current token.
        password_hash = generate_password_hash(password)
        lock_pending_worker(agent_id)
        now = utcnow()
        claimed = db.session.execute(update(WorkerSetupInvitation).where(
            WorkerSetupInvitation.agent_id == agent_id,
            WorkerSetupInvitation.token_hash == digest,
            WorkerSetupInvitation.consumed_at.is_(None),
            WorkerSetupInvitation.expires_at > now,
        ).values(consumed_at=now).execution_options(synchronize_session=False)).rowcount
        if claimed != 1:
            raise SetupUnavailable(INVALID_INVITATION)
        changed = db.session.execute(update(OnboardingAgent).where(
            OnboardingAgent.id == agent_id,
            OnboardingAgent.email == email,
            OnboardingAgent.password_hash == PENDING_PASSWORD,
            OnboardingAgent.account_disabled.is_(True),
        ).values(password_hash=password_hash, account_disabled=False, availability=False)
         .execution_options(synchronize_session=False)).rowcount
        if changed != 1:
            raise SetupUnavailable(INVALID_INVITATION)
        db.session.commit()
        return agent_id
    except Exception:
        db.session.rollback()
        raise
