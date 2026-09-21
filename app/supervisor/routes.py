from flask import Blueprint, render_template, redirect, url_for, abort
from flask_login import login_required, current_user

from app.models import Task
from app.services.recommendation_service import MockRecommendationService


supervisor_bp = Blueprint(
    "supervisor",
    __name__,
    url_prefix="/supervisor"
)


@supervisor_bp.route("/dashboard")
@login_required
def dashboard():

    if current_user.role != "supervisor":
        return redirect(url_for("home"))

    tasks = (
        Task.query
        .order_by(Task.created_at.desc())
        .all()
    )

    return render_template(
        "supervisor/dashboard.html",
        tasks=tasks
    )


@supervisor_bp.route(
    "/task/<int:task_id>/recommendations"
)
@login_required
def recommendations(task_id):

    if current_user.role != "supervisor":
        return redirect(url_for("home"))

    task = Task.query.get_or_404(task_id)

    service = MockRecommendationService()

    recommended_agents = service.get_recommendations(
        task_id
    )

    return render_template(
        "supervisor/recommendations.html",
        task=task,
        recommendations=recommended_agents
    )