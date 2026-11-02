from app.extensions import db


class WorkerSetupInvitation(db.Model):
    __tablename__ = 'worker_setup_invitations'
    agent_id = db.Column(db.Integer, db.ForeignKey('independent_worker_registrations.agent_id'), primary_key=True)
    token_hash = db.Column(db.String(64), nullable=False, unique=True)
    created_by_admin_id = db.Column(db.Integer, db.ForeignKey('administrators.id'), nullable=False)
    issued_at = db.Column(db.DateTime, nullable=False, server_default=db.func.current_timestamp())
    expires_at = db.Column(db.DateTime, nullable=False)
    consumed_at = db.Column(db.DateTime, nullable=True)
    __table_args__ = (
        db.CheckConstraint('length(token_hash) = 64', name='ck_worker_setup_hash_length'),
        db.CheckConstraint('expires_at > issued_at', name='ck_worker_setup_expiry'),
    )
