"""One-time password resets and privacy-preserving request throttling."""

from app.extensions import db


class PasswordResetToken(db.Model):
    __tablename__ = 'password_reset_tokens'

    id = db.Column(db.Integer, primary_key=True)
    worker_id = db.Column(db.Integer, db.ForeignKey('onboarding_agents.id'))
    supervisor_id = db.Column(db.Integer, db.ForeignKey('supervisors.id'))
    administrator_id = db.Column(db.Integer, db.ForeignKey('administrators.id'))
    token_hash = db.Column(db.String(64), nullable=False, unique=True)
    issued_at = db.Column(db.DateTime, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    used_at = db.Column(db.DateTime)

    __table_args__ = (
        db.CheckConstraint(
            '(worker_id IS NOT NULL AND supervisor_id IS NULL AND administrator_id IS NULL) OR '
            '(worker_id IS NULL AND supervisor_id IS NOT NULL AND administrator_id IS NULL) OR '
            '(worker_id IS NULL AND supervisor_id IS NULL AND administrator_id IS NOT NULL)',
            name='ck_password_reset_one_account',
        ),
        db.CheckConstraint('length(token_hash) = 64', name='ck_password_reset_hash_length'),
        db.CheckConstraint('expires_at > issued_at', name='ck_password_reset_expiry'),
    )


class PasswordResetRequest(db.Model):
    __tablename__ = 'password_reset_requests'

    id = db.Column(db.Integer, primary_key=True)
    email_digest = db.Column(db.String(64), nullable=False, index=True)
    ip_digest = db.Column(db.String(64), nullable=False, index=True)
    requested_at = db.Column(db.DateTime, nullable=False)

    __table_args__ = (
        db.CheckConstraint('length(email_digest) = 64', name='ck_password_reset_email_digest'),
        db.CheckConstraint('length(ip_digest) = 64', name='ck_password_reset_ip_digest'),
    )
