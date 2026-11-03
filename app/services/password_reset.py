"""Private, one-time password reset for active sign-in accounts."""

from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import re
import secrets

from flask import current_app
from sqlalchemy import func, update

from app.extensions import db
from app.models import (
    Administrator, IndependentWorkerRegistration, OnboardingAgent,
    PasswordResetRequest, PasswordResetToken, Supervisor,
)
from app.services.invitation_email import email_settings, send_password_reset_email, send_password_changed_email

LIFETIME = timedelta(minutes=30)
WINDOW = timedelta(hours=1)
INVALID_LINK = 'This reset link is invalid, expired, or already used. Request a new link.'
TOKEN_PATTERN = re.compile(r'[A-Za-z0-9_-]{43}\Z')


class ResetUnavailable(ValueError):
    pass


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _digest(kind, value):
    key = current_app.secret_key
    if isinstance(key, str):
        key = key.encode('utf-8')
    return hmac.new(key, f'{kind}:{value}'.encode('utf-8'), hashlib.sha256).hexdigest()


def _account_for_email(email):
    supervisor = Supervisor.query.filter_by(email=email).first()
    if supervisor is not None:
        return supervisor if supervisor.is_active and not supervisor.password_hash.startswith('!pending-') else None
    worker = OnboardingAgent.query.filter_by(email=email).first()
    if worker is not None:
        if (worker.is_active and not worker.password_hash.startswith('!pending-')
                and db.session.get(IndependentWorkerRegistration, worker.id) is not None):
            return worker
        return None
    return Administrator.query.filter_by(email=email).first()


def request_reset(email, ip_address):
    """Record every well-formed request; the caller always shows one generic response."""
    now = utcnow()
    email_digest = _digest('email', email)
    ip_digest = _digest('ip', ip_address or 'unknown')
    since = now - WINDOW
    ip_count = db.session.query(func.count(PasswordResetRequest.id)).filter(
        PasswordResetRequest.ip_digest == ip_digest,
        PasswordResetRequest.requested_at >= since,
    ).scalar()
    if ip_count >= 20:
        return
    email_count = db.session.query(func.count(PasswordResetRequest.id)).filter(
        PasswordResetRequest.email_digest == email_digest,
        PasswordResetRequest.requested_at >= since,
    ).scalar()
    db.session.add(PasswordResetRequest(
        email_digest=email_digest, ip_digest=ip_digest, requested_at=now,
    ))
    db.session.commit()
    if email_count >= 3:
        return

    account = _account_for_email(email)
    if account is None:
        return
    try:
        settings = email_settings()
    except Exception:
        return
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode('ascii')).hexdigest()
    identity = {
        'agent': {'worker_id': account.id},
        'supervisor': {'supervisor_id': account.id},
        'administrator': {'administrator_id': account.id},
    }[account.role]
    try:
        db.session.query(PasswordResetToken).filter_by(**identity).filter(
            PasswordResetToken.used_at.is_(None),
        ).update({'used_at': now}, synchronize_session=False)
        row = PasswordResetToken(
            **identity, token_hash=token_hash,
            issued_at=now, expires_at=now + LIFETIME,
        )
        db.session.add(row)
        db.session.commit()
        send_password_reset_email(account.email, account.name, token, row.expires_at, settings)
    except Exception:
        db.session.rollback()
        # If delivery was not confirmed, a generated link must not remain usable.
        if 'row' in locals() and row.id is not None:
            try:
                db.session.execute(update(PasswordResetToken).where(
                    PasswordResetToken.id == row.id,
                    PasswordResetToken.used_at.is_(None),
                ).values(used_at=utcnow()))
                db.session.commit()
            except Exception:
                db.session.rollback()


def redeem_reset(token, password):
    if not TOKEN_PATTERN.fullmatch(token or ''):
        raise ResetUnavailable(INVALID_LINK)
    if not 12 <= len(password) <= 128 or not password.strip():
        raise ValueError('Choose a password of 12 to 128 characters.')
    digest = hashlib.sha256(token.encode('ascii')).hexdigest()
    now = utcnow()
    try:
        row = PasswordResetToken.query.filter_by(token_hash=digest, used_at=None).filter(
            PasswordResetToken.expires_at > now,
        ).first()
        if row is None:
            raise ResetUnavailable(INVALID_LINK)
        if row.worker_id is not None:
            account = db.session.get(OnboardingAgent, row.worker_id, populate_existing=True)
            if (account is None or not account.is_active
                    or db.session.get(IndependentWorkerRegistration, account.id) is None):
                raise ResetUnavailable(INVALID_LINK)
        elif row.supervisor_id is not None:
            account = db.session.get(Supervisor, row.supervisor_id, populate_existing=True)
            if account is None or not account.is_active:
                raise ResetUnavailable(INVALID_LINK)
        else:
            account = db.session.get(Administrator, row.administrator_id, populate_existing=True)
            if account is None:
                raise ResetUnavailable(INVALID_LINK)
        if account.password_hash.startswith('!pending-'):
            raise ResetUnavailable(INVALID_LINK)
        account.set_password(password)
        claimed = db.session.execute(update(PasswordResetToken).where(
            PasswordResetToken.id == row.id,
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.expires_at > utcnow(),
        ).values(used_at=utcnow()).execution_options(synchronize_session=False)).rowcount
        if claimed != 1:
            raise ResetUnavailable(INVALID_LINK)
        identity = {
            'agent': {'worker_id': account.id},
            'supervisor': {'supervisor_id': account.id},
            'administrator': {'administrator_id': account.id},
        }[account.role]
        db.session.query(PasswordResetToken).filter_by(**identity).filter(
            PasswordResetToken.used_at.is_(None),
        ).update({'used_at': utcnow()}, synchronize_session=False)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    try:
        send_password_changed_email(account.email, account.name, email_settings())
    except Exception:
        pass
