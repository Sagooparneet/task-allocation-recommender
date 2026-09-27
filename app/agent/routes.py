from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    flash
)

from flask_login import login_required, current_user

from app.extensions import db
from app.models import TaskAssignment


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

    assignments = (
        TaskAssignment.query
        .filter_by(agent_id=current_user.id)
        .order_by(TaskAssignment.assigned_at.desc())
        .all()
    )

    return render_template(
        "agent/dashboard.html",
        assignments=assignments
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

    db.session.commit()

    flash(
        f"{assignment.task.task_type} was marked as completed.",
        "success"
    )

    return redirect(
        url_for("agent.dashboard")
    )