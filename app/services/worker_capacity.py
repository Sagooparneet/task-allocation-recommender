"""Application capacity policy, separate from model scores and dataset evidence."""
from sqlalchemy import func
from app.extensions import db
from app.models import TaskAssignment

MAX_ACTIVE_TASKS = 3
ACTIVE_STATUSES = ('Assigned', 'In progress')


def active_task_counts():
    return dict(db.session.query(TaskAssignment.agent_id, func.count(TaskAssignment.id))
        .filter(TaskAssignment.status.in_(ACTIVE_STATUSES))
        .group_by(TaskAssignment.agent_id).all())


def active_task_count(agent_id):
    return TaskAssignment.query.filter(
        TaskAssignment.agent_id == agent_id,
        TaskAssignment.status.in_(ACTIVE_STATUSES)
    ).count()
