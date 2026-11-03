"""Email challenges for first-time setup of administrator-invited accounts."""

from datetime import timedelta
import hashlib
import hmac
import re
import secrets

from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db
from app.models import (
    OnboardingAgent, IndependentWorkerRegistration, WorkerSetupInvitation,
    Supervisor, SupervisorSetupInvitation, SetupEmailVerification,
)
from app.services.independent_workers import valid_email
from app.services.invitation_email import email_settings, send_verification_code
from app.services.worker_setup import lock_pending_worker, utcnow
from app.services.supervisor_setup import lock_pending_supervisor

CODE_LIFETIME = timedelta(minutes=10)
MIN_RESEND_INTERVAL = timedelta(minutes=1)
MAX_SENDS_PER_INVITATION = 3
MAX_FAILED_ATTEMPTS = 5
INVALID_SETUP = 'This setup invitation is invalid, expired, or already used. Ask your administrator for a new one.'
INVALID_CODE = 'The verification code is incorrect, expired, or used too many times. Request a new code if needed.'


class VerificationUnavailable(ValueError):
    pass


def _pending_invitation(role, token, email):
    if role not in ('worker', 'supervisor') or not valid_email(email):
        raise VerificationUnavailable(INVALID_SETUP)
    if not re.fullmatch(r'[A-Za-z0-9_-]{43}', token or ''):
        raise VerificationUnavailable(INVALID_SETUP)
    digest = hashlib.sha256(token.encode('ascii')).hexdigest()
    now = utcnow()
    if role == 'worker':
        invitation = WorkerSetupInvitation.query.join(
            OnboardingAgent, OnboardingAgent.id == WorkerSetupInvitation.agent_id
        ).join(
            IndependentWorkerRegistration,
            IndependentWorkerRegistration.agent_id == WorkerSetupInvitation.agent_id,
        ).filter(
            WorkerSetupInvitation.token_hash == digest,
            WorkerSetupInvitation.consumed_at.is_(None),
            WorkerSetupInvitation.expires_at > now,
            OnboardingAgent.email == email,
        ).first()
        if invitation is None:
            raise VerificationUnavailable(INVALID_SETUP)
        account_id = invitation.agent_id
        lock_pending_worker(account_id)
        account = db.session.get(OnboardingAgent, account_id, populate_existing=True)
        invitation = db.session.get(WorkerSetupInvitation, account_id, populate_existing=True)
    else:
        invitation = SupervisorSetupInvitation.query.join(
            Supervisor, Supervisor.id == SupervisorSetupInvitation.supervisor_id
        ).filter(
            SupervisorSetupInvitation.token_hash == digest,
            SupervisorSetupInvitation.consumed_at.is_(None),
            SupervisorSetupInvitation.expires_at > now,
            Supervisor.email == email,
        ).first()
        if invitation is None:
            raise VerificationUnavailable(INVALID_SETUP)
        account_id = invitation.supervisor_id
        lock_pending_supervisor(account_id)
        account = db.session.get(Supervisor, account_id, populate_existing=True)
        invitation = db.session.get(SupervisorSetupInvitation, account_id, populate_existing=True)
    if (invitation is None or account is None or account.email != email
            or invitation.consumed_at is not None or invitation.expires_at <= utcnow()
            or not hmac.compare_digest(invitation.token_hash, digest)):
        raise VerificationUnavailable(INVALID_SETUP)
    return account, digest


def _challenge(role, account_id):
    if role == 'worker':
        return SetupEmailVerification.query.filter_by(worker_id=account_id).first()
    return SetupEmailVerification.query.filter_by(supervisor_id=account_id).first()


def request_verification_code(role, token, email):
    """Store a hashed code, then submit it to the registered mailbox."""
    settings = email_settings()
    try:
        account, digest = _pending_invitation(role, token, email)
        now = utcnow()
        challenge = _challenge(role, account.id)
        same_invitation = challenge is not None and hmac.compare_digest(challenge.invitation_token_hash, digest)
        if same_invitation:
            if challenge.send_count >= MAX_SENDS_PER_INVITATION:
                raise VerificationUnavailable('The code limit for this invitation was reached. Ask your administrator for a new invitation.')
            if now - challenge.last_sent_at < MIN_RESEND_INTERVAL:
                raise VerificationUnavailable('Please wait one minute before requesting another code.')
        code = f'{secrets.randbelow(1_000_000):06d}'
        if challenge is None:
            challenge = SetupEmailVerification(
                worker_id=account.id if role == 'worker' else None,
                supervisor_id=account.id if role == 'supervisor' else None,
            )
            db.session.add(challenge)
        challenge.invitation_token_hash = digest
        challenge.code_hash = generate_password_hash(code)
        challenge.issued_at = now
        challenge.expires_at = now + CODE_LIFETIME
        challenge.last_sent_at = now
        challenge.send_count = challenge.send_count + 1 if same_invitation else 1
        challenge.failed_attempts = 0
        recipient, name, expiry = account.email, account.name, challenge.expires_at
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    # A timed-out send may already have been accepted. Leave the challenge in
    # place, do not automatically retry, and let the user request a new code.
    send_verification_code(recipient, name, code, expiry, settings)


def check_verification_code(role, token, email, code):
    """Delete the challenge in the caller's transaction before redeeming.

    redeem_invitation commits on success and rolls back on failure, so the
    challenge and account activation change together.
    """
    try:
        account, digest = _pending_invitation(role, token, email)
        challenge = _challenge(role, account.id)
        if (challenge is None or not hmac.compare_digest(challenge.invitation_token_hash, digest)
                or challenge.expires_at <= utcnow()
                or challenge.failed_attempts >= MAX_FAILED_ATTEMPTS):
            raise VerificationUnavailable(INVALID_CODE)
        valid = bool(re.fullmatch(r'\d{6}', code or '')) and check_password_hash(challenge.code_hash, code)
        if not valid:
            challenge.failed_attempts += 1
            db.session.commit()
            raise VerificationUnavailable(INVALID_CODE)
        db.session.delete(challenge)
    except Exception:
        # Failed attempts must remain committed for the rate limit; other
        # failures must not leave a write lock or partial deletion in session.
        db.session.rollback()
        raise
