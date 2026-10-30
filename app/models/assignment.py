from datetime import datetime

from app.extensions import db


class TaskAssignment(db.Model):
    __tablename__ = "task_assignments"

    id = db.Column(db.Integer, primary_key=True)

    task_id = db.Column(
        db.Integer,
        db.ForeignKey("tasks.id"),
        nullable=False
    )

    agent_id = db.Column(
        db.Integer,
        db.ForeignKey("onboarding_agents.id"),
        nullable=False
    )

    supervisor_id = db.Column(
        db.Integer,
        db.ForeignKey("supervisors.id"),
        nullable=False
    )

    assigned_at = db.Column(
        db.DateTime,
        default=datetime.now
    )

    # UTC timestamps, stored without timezone offsets. Historical times remain
    # unknown (NULL); only an explicit progress action should populate them.
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)

    status = db.Column(
        db.String(30),
        default="Assigned"
    )

    task = db.relationship(
        "Task",
        backref="assignments"
    )

    agent = db.relationship(
        "OnboardingAgent",
        backref="assignments"
    )

    supervisor = db.relationship(
        "Supervisor",
        backref="assignments"
    )

    def __repr__(self):
        return f"<TaskAssignment {self.id}>"
