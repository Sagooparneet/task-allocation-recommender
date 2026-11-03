"""One-time initial setup for administrator-added supervisor accounts."""
from datetime import datetime, timedelta, timezone
import hashlib
import re
import secrets

from sqlalchemy import update
from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models import Supervisor, SupervisorSetupInvitation

PENDING_PASSWORD = '!pending-supervisor-setup'
LIFETIME = timedelta(hours=24)
INVALID_INVITATION = 'This setup invitation is invalid, expired, or already used. Ask your administrator for a new one.'


class SetupUnavailable(ValueError):
    pass


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def pending_account_setup(supervisor):
    return supervisor.account_disabled and supervisor.password_hash == PENDING_PASSWORD


def lock_pending_supervisor(supervisor_id):
    # Both issuance and redemption write this row before touching its invitation.
    # This also serializes the operations on SQLite, which ignores FOR UPDATE.
    changed = db.session.execute(update(Supervisor).where(
        Supervisor.id == supervisor_id,
        Supervisor.password_hash == PENDING_PASSWORD,
        Supervisor.account_disabled.is_(True),
    ).values(account_disabled=Supervisor.account_disabled)
        .execution_options(synchronize_session=False)).rowcount
    if changed != 1:
        raise SetupUnavailable(INVALID_INVITATION)


def issue_invitation(supervisor_id, administrator_id, minimum_interval=None):
    try:
        lock_pending_supervisor(supervisor_id)
        token = secrets.token_urlsafe(32)
        digest = hashlib.sha256(token.encode('ascii')).hexdigest()
        now = utcnow()
        invitation = db.session.get(SupervisorSetupInvitation, supervisor_id, populate_existing=True)
        if (minimum_interval is not None and invitation is not None
                and now - invitation.issued_at < minimum_interval):
            raise ValueError('Please wait one minute before emailing another invitation.')
        if invitation is None:
            invitation = SupervisorSetupInvitation(supervisor_id=supervisor_id)
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
        invitation = SupervisorSetupInvitation.query.join(
            Supervisor, Supervisor.id == SupervisorSetupInvitation.supervisor_id
        ).filter(SupervisorSetupInvitation.token_hash == digest,
                 Supervisor.email == email,
                 SupervisorSetupInvitation.consumed_at.is_(None),
                 SupervisorSetupInvitation.expires_at > utcnow()).first()
        if invitation is None:
            raise SetupUnavailable(INVALID_INVITATION)
        supervisor_id = invitation.supervisor_id
        password_hash = generate_password_hash(password)
        lock_pending_supervisor(supervisor_id)
        now = utcnow()
        claimed = db.session.execute(update(SupervisorSetupInvitation).where(
            SupervisorSetupInvitation.supervisor_id == supervisor_id,
            SupervisorSetupInvitation.token_hash == digest,
            SupervisorSetupInvitation.consumed_at.is_(None),
            SupervisorSetupInvitation.expires_at > now,
        ).values(consumed_at=now).execution_options(synchronize_session=False)).rowcount
        if claimed != 1:
            raise SetupUnavailable(INVALID_INVITATION)
        changed = db.session.execute(update(Supervisor).where(
            Supervisor.id == supervisor_id,
            Supervisor.email == email,
            Supervisor.password_hash == PENDING_PASSWORD,
            Supervisor.account_disabled.is_(True),
        ).values(password_hash=password_hash, account_disabled=False)
            .execution_options(synchronize_session=False)).rowcount
        if changed != 1:
            raise SetupUnavailable(INVALID_INVITATION)
        db.session.commit()
        return supervisor_id
    except Exception:
        db.session.rollback()
        raise
