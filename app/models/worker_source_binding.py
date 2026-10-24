from app.extensions import db


class WorkerSourceBinding(db.Model):
    __tablename__ = "worker_source_bindings"

    # One source identity per website worker.
    agent_id = db.Column(
        db.Integer,
        db.ForeignKey("onboarding_agents.id"),
        primary_key=True,
    )

    # Store original source IDs as strings.
    source_worker_id = db.Column(
        db.String(64),
        nullable=False,
        unique=True,
    )