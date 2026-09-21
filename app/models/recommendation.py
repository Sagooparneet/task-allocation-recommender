from datetime import datetime

from app.extensions import db


class Recommendation(db.Model):
    __tablename__ = "recommendations"

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

    score = db.Column(db.Float, nullable=False)

    explanation = db.Column(db.Text)

    created_at = db.Column(
        db.DateTime,
        default=datetime.now
    )

    task = db.relationship(
        "Task",
        backref="recommendations"
    )

    agent = db.relationship(
        "OnboardingAgent",
        backref="recommendations"
    )

    def __repr__(self):
        return (
            f"<Recommendation Task={self.task_id} "
            f"Agent={self.agent_id}>"
        )