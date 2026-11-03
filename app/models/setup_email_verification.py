"""A short-lived email challenge for one invited account."""

from app.extensions import db


class SetupEmailVerification(db.Model):
    __tablename__ = 'setup_email_verifications'

    id = db.Column(db.Integer, primary_key=True)
    worker_id = db.Column(db.Integer, db.ForeignKey('independent_worker_registrations.agent_id'), unique=True)
    supervisor_id = db.Column(db.Integer, db.ForeignKey('supervisors.id'), unique=True)
    invitation_token_hash = db.Column(db.String(64), nullable=False)
    code_hash = db.Column(db.String(255), nullable=False)
    issued_at = db.Column(db.DateTime, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    last_sent_at = db.Column(db.DateTime, nullable=False)
    send_count = db.Column(db.Integer, nullable=False, default=1)
    failed_attempts = db.Column(db.Integer, nullable=False, default=0)

    __table_args__ = (
        db.CheckConstraint(
            '(worker_id IS NOT NULL AND supervisor_id IS NULL) OR '
            '(worker_id IS NULL AND supervisor_id IS NOT NULL)',
            name='ck_setup_email_one_account',
        ),
        db.CheckConstraint('length(invitation_token_hash) = 64', name='ck_setup_email_invitation_hash'),
        db.CheckConstraint('expires_at > issued_at', name='ck_setup_email_expiry'),
        db.CheckConstraint('last_sent_at >= issued_at', name='ck_setup_email_last_sent'),
        db.CheckConstraint('send_count >= 1', name='ck_setup_email_send_count'),
        db.CheckConstraint('failed_attempts >= 0', name='ck_setup_email_failed_attempts'),
    )
