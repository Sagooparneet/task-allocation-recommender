from app.extensions import db


class IndependentWorkerRegistration(db.Model):
    __tablename__ = 'independent_worker_registrations'
    agent_id = db.Column(db.Integer, db.ForeignKey('onboarding_agents.id'), primary_key=True)
    created_by_admin_id = db.Column(db.Integer, db.ForeignKey('administrators.id'), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, server_default=db.func.current_timestamp())
