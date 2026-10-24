from datetime import datetime, timedelta, timezone
from sqlalchemy import case
from sqlalchemy.orm import joinedload

from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    flash, request
)

from flask_login import login_required, current_user

from app.extensions import db
from app.models import TaskAssignment, OnboardingAgent, Task


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
    if selected_status not in ("Active", "Completed", "Overdue"):
        selected_status = ""
    query = owned.join(Task)
    if search:
        query = query.filter(Task.task_type.contains(search, autoescape=True))
    if selected_status == "Active":
        query = query.filter(TaskAssignment.status != "Completed")
    elif selected_status == "Completed":
        query = query.filter(TaskAssignment.status == "Completed")
    elif selected_status == "Overdue":
        query = query.filter(TaskAssignment.status != "Completed", Task.deadline < now)
    page = max(1, request.args.get("page", 1, type=int))
    assignment_page = query.options(joinedload(TaskAssignment.task)).order_by(
        case((TaskAssignment.status == "Completed", 1), else_=0),
        case((Task.deadline.is_(None), 1), else_=0),
        Task.deadline.asc(), TaskAssignment.id.desc(),
    ).paginate(page=page, per_page=10, error_out=False)
    return render_template(
        "agent/dashboard.html", assignment_page=assignment_page,
        total_tasks=total, active_tasks=active, completed_tasks=completed,
        overdue_tasks=overdue, due_today=due_today, now=now,
        search=search, selected_status=selected_status,
        completion_percent=round(100 * completed / total) if total else 0,
    )


@agent_bp.route(
    "/assignment/<int:assignment_id>/complete",
    methods=["POST"]
)
@login_required
def complete_assignment(assignment_id):

    if current_user.role != "agent":
        return redirect(url_for("home"))

    assignment = db.session.get(
        TaskAssignment,
        assignment_id
    )

    if not assignment:

        flash(
            "Assignment could not be found.",
            "danger"
        )

        return redirect(
            url_for("agent.dashboard")
        )

    # Prevent agents from changing another agent's task
    if assignment.agent_id != current_user.id:

        flash(
            "You are not allowed to update this assignment.",
            "danger"
        )

        return redirect(
            url_for("agent.dashboard")
        )

    # Prevent completed tasks from being completed again
    if assignment.status == "Completed":

        flash(
            "This task has already been completed.",
            "warning"
        )

        return redirect(
            url_for("agent.dashboard")
        )

    assignment.status = "Completed"
    assignment.task.status = "Completed"

    # Get the assigned agent
    agent = db.session.get(
        OnboardingAgent,
        assignment.agent_id
    )

    # Reduce workload without allowing it to go below zero
    if agent:
        agent.workload = max(
            0,
            (agent.workload or 0) - 1
        )

    db.session.commit()

    flash(
        f"{assignment.task.task_type} was marked as completed.",
        "success"
    )

    return redirect(
        url_for("agent.dashboard")
    )