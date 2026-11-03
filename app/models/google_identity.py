"""Stable Google subject linked to exactly one approved IntelliTask account."""

from app.extensions import db


class GoogleIdentity(db.Model):
    __tablename__ = 'google_identities'

    subject = db.Column(db.String(255), primary_key=True)
    worker_id = db.Column(db.Integer, db.ForeignKey('onboarding_agents.id'), unique=True)
    supervisor_id = db.Column(db.Integer, db.ForeignKey('supervisors.id'), unique=True)
    administrator_id = db.Column(db.Integer, db.ForeignKey('administrators.id'), unique=True)
    linked_at = db.Column(db.DateTime, nullable=False)
    last_login_at = db.Column(db.DateTime, nullable=False)

    __table_args__ = (
        db.CheckConstraint('length(subject) > 0', name='ck_google_subject_present'),
        db.CheckConstraint(
            '(worker_id IS NOT NULL AND supervisor_id IS NULL AND administrator_id IS NULL) OR '
            '(worker_id IS NULL AND supervisor_id IS NOT NULL AND administrator_id IS NULL) OR '
            '(worker_id IS NULL AND supervisor_id IS NULL AND administrator_id IS NOT NULL)',
            name='ck_google_identity_one_account',
        ),
    )
