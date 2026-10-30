from datetime import datetime

from app.extensions import db
from app.models import Task, TaskAssignment, Supervisor, OnboardingAgent


def make_assignment(status):
    supervisor = Supervisor.query.first()
    agent = OnboardingAgent.query.first()
    task = Task(task_type='Progress model test', supervisor_id=supervisor.id, status=status)
    db.session.add(task)
    db.session.flush()
    assignment = TaskAssignment(task_id=task.id, agent_id=agent.id,
                                supervisor_id=supervisor.id, status=status)
    db.session.add(assignment)
    db.session.commit()
    return assignment.id, agent.id, agent.workload


def test_completed_record_does_not_invent_historical_times(app):
    assignment_id, agent_id, workload = make_assignment('Completed')
    db.session.remove()
    assignment = db.session.get(TaskAssignment, assignment_id)
    assert assignment.started_at is None
    assert assignment.completed_at is None
    assert assignment.status == assignment.task.status == 'Completed'
    assert db.session.get(OnboardingAgent, agent_id).workload == workload


def test_progress_times_round_trip_without_changing_status_or_workload(app):
    assignment_id, agent_id, workload = make_assignment('Assigned')
    assignment = db.session.get(TaskAssignment, assignment_id)
    assigned_at = assignment.assigned_at
    started = datetime(2026, 10, 30, 7, 0, 0)
    completed = datetime(2026, 10, 30, 8, 15, 0)
    assignment.started_at = started
    assignment.completed_at = completed
    db.session.commit()
    db.session.remove()
    saved = db.session.get(TaskAssignment, assignment_id)
    assert (saved.started_at, saved.completed_at) == (started, completed)
    assert saved.assigned_at == assigned_at
    assert saved.status == saved.task.status == 'Assigned'
    assert db.session.get(OnboardingAgent, agent_id).workload == workload
