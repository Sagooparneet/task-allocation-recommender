from datetime import datetime, timedelta, timezone
import secrets
from sqlalchemy import case, update
from sqlalchemy.orm import joinedload

from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    flash, request, session, abort
)

from flask_login import login_required, current_user

from app.extensions import db
from app.models import TaskAssignment, OnboardingAgent, Task, TaskVenueDetails


agent_bp = Blueprint(
    "agent",
    __name__,
    url_prefix="/agent"
)


@agent_bp.route("/dashboard")
@login_required
def dashboard():

    if current_user.role != "agent":
        return redirect(url_for("home"))

    now = datetime.now(timezone(timedelta(hours=3))).replace(tzinfo=None)
    end_today = now.replace(hour=23, minute=59, second=59, microsecond=999999)
    owned = TaskAssignment.query.filter_by(agent_id=current_user.id)
    total = owned.count()
    completed = owned.filter_by(status="Completed").count()
    active = total - completed
    active_query = owned.join(Task).filter(TaskAssignment.status != "Completed")
    overdue = active_query.filter(Task.deadline < now).count()
    due_today = active_query.filter(Task.deadline >= now, Task.deadline <= end_today).count()
    search = request.args.get("q", "").strip()[:100]
    selected_status = request.args.get("status", "")
    if selected_status not in ("Active", "Assigned", "In progress", "Completed", "Overdue"):
        selected_status = ""
    query = owned.join(Task)
    if search:
        query = query.filter(Task.task_type.contains(search, autoescape=True))
    if selected_status == "Active":
        query = query.filter(TaskAssignment.status != "Completed")
    elif selected_status in ("Assigned", "In progress", "Completed"):
        query = query.filter(TaskAssignment.status == selected_status)
    elif selected_status == "Overdue":
        query = query.filter(TaskAssignment.status != "Completed", Task.deadline < now)
    page = max(1, request.args.get("page", 1, type=int))
    assignment_page = query.options(joinedload(TaskAssignment.task)).order_by(
        case((TaskAssignment.status == "Completed", 1), else_=0),
        case((Task.deadline.is_(None), 1), else_=0),
        Task.deadline.asc(), TaskAssignment.id.desc(),
    ).paginate(page=page, per_page=10, error_out=False)
    session.setdefault('task_progress_csrf_token', secrets.token_urlsafe(32))
    return render_template(
        "agent/dashboard.html", assignment_page=assignment_page,
        total_tasks=total, active_tasks=active, completed_tasks=completed,
        overdue_tasks=overdue, due_today=due_today, now=now,
        search=search, selected_status=selected_status,
        progress_token=session['task_progress_csrf_token'],
        started_times={a.id: (a.started_at + timedelta(hours=3)).strftime('%d %b %Y, %H:%M')
                       for a in assignment_page.items if a.started_at is not None},
        completed_times={a.id: (a.completed_at + timedelta(hours=3)).strftime('%d %b %Y, %H:%M')
                         for a in assignment_page.items if a.completed_at is not None},
        venue_details={item.task_id: item for item in TaskVenueDetails.query.filter(
            TaskVenueDetails.task_id.in_([a.task_id for a in assignment_page.items])).all()},
        completion_percent=round(100 * completed / total) if total else 0,
    )


@agent_bp.route('/assignment/<int:assignment_id>/start', methods=['POST'])
@login_required
def start_assignment(assignment_id):
    if current_user.role != 'agent':
        abort(403)
    expected = session.get('task_progress_csrf_token')
    supplied = request.form.get('task_progress_csrf_token', '')
    if not expected or not secrets.compare_digest(expected, supplied):
        abort(400)
    assignment = db.session.get(TaskAssignment, assignment_id, populate_existing=True)
    if assignment is None or assignment.agent_id != current_user.id:
        abort(404)
    task_id = assignment.task_id
    started = datetime.now(timezone.utc).replace(tzinfo=None)
    # Compare-and-set both statuses in one transaction. Repeated or stale
    # requests cannot replace the first start time or reopen completed work.
    task_changed = db.session.execute(update(Task).where(
        Task.id == task_id, Task.status == 'Assigned'
    ).values(status='In progress').execution_options(synchronize_session=False)).rowcount
    assignment_changed = 0
    if task_changed == 1:
        assignment_changed = db.session.execute(update(TaskAssignment).where(
            TaskAssignment.id == assignment_id,
            TaskAssignment.agent_id == current_user.id,
            TaskAssignment.status == 'Assigned',
            TaskAssignment.started_at.is_(None),
            TaskAssignment.completed_at.is_(None),
        ).values(status='In progress', started_at=started)
          .execution_options(synchronize_session=False)).rowcount
    if task_changed != 1 or assignment_changed != 1:
        db.session.rollback()
        flash('This task could not be started. Check its current status.', 'warning')
    else:
        db.session.commit()
        flash('Task started. Your supervisor can see that it is in progress.', 'success')
    return redirect(url_for('agent.dashboard'))


@agent_bp.route('/assignment/<int:assignment_id>/complete', methods=['POST'])
@login_required
def complete_assignment(assignment_id):
    if current_user.role != 'agent':
        abort(403)
    expected = session.get('task_progress_csrf_token')
    supplied = request.form.get('task_progress_csrf_token', '')
    if not expected or not secrets.compare_digest(expected, supplied):
        abort(400)
    assignment = db.session.get(TaskAssignment, assignment_id, populate_existing=True)
    if assignment is None or assignment.agent_id != current_user.id:
        abort(404)
    task_id = assignment.task_id
    completed = datetime.now(timezone.utc).replace(tzinfo=None)
    # The task row is claimed first, matching the start action's lock order.
    # All three updates commit together; a repeated request claims no row.
    task_changed = db.session.execute(update(Task).where(
        Task.id == task_id, Task.status == 'In progress'
    ).values(status='Completed').execution_options(synchronize_session=False)).rowcount
    assignment_changed = 0
    if task_changed == 1:
        assignment_changed = db.session.execute(update(TaskAssignment).where(
            TaskAssignment.id == assignment_id,
            TaskAssignment.agent_id == current_user.id,
            TaskAssignment.status == 'In progress',
            TaskAssignment.started_at.is_not(None),
            TaskAssignment.started_at <= completed,
            TaskAssignment.completed_at.is_(None),
        ).values(status='Completed', completed_at=completed)
          .execution_options(synchronize_session=False)).rowcount
    if task_changed != 1 or assignment_changed != 1:
        db.session.rollback()
        flash('This task could not be completed. It must be in progress and not already completed.', 'warning')
        return redirect(url_for('agent.dashboard'))
    worker_changed = db.session.execute(update(OnboardingAgent).where(
        OnboardingAgent.id == current_user.id
    ).values(workload=case((OnboardingAgent.workload > 0, OnboardingAgent.workload - 1), else_=0))
      .execution_options(synchronize_session=False)).rowcount
    if worker_changed != 1:
        db.session.rollback()
        abort(409)
    db.session.commit()
    flash('Task completed. Your completion time has been recorded.', 'success')
    return redirect(url_for('agent.dashboard'))
