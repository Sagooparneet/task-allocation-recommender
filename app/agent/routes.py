from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user

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