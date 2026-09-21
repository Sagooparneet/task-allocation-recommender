from datetime import datetime

from app.extensions import db


class Task(db.Model):
    __tablename__ = "tasks"

    id = db.Column(db.Integer, primary_key=True)

    task_type = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)

    location = db.Column(db.String(100))
    priority = db.Column(db.String(20), default="Medium")
    deadline = db.Column(db.DateTime)

    status = db.Column(db.String(30), default="Pending")

    created_at = db.Column(
        db.DateTime,
        default=datetime.now
    )

    supervisor_id = db.Column(
        db.Integer,
        db.ForeignKey("supervisors.id"),
        nullable=False
    )

    supervisor = db.relationship(
        "Supervisor",
        backref="tasks"
    )

    def __repr__(self):
        return f"<Task {self.task_type}>"