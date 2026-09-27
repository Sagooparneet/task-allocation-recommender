from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    request,
    flash
)

from flask_login import login_required, current_user

from app.extensions import db
from app.models import (
    Task,
    OnboardingAgent,
    TaskAssignment
)

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


@supervisor_bp.route(
    "/task/<int:task_id>/assign",
    methods=["POST"]
)
@login_required
def assign_task(task_id):

    if current_user.role != "supervisor":
        return redirect(url_for("home"))

    task = Task.query.get_or_404(task_id)

    # Prevent the same task from being assigned twice
    existing_assignment = TaskAssignment.query.filter_by(
        task_id=task.id
    ).first()

    if existing_assignment:

        flash(
            "This task has already been assigned.",
            "warning"
        )

        return redirect(
            url_for(
                "supervisor.recommendations",
                task_id=task.id
            )
        )

    agent_id = request.form.get(
        "agent_id",
        type=int
    )

    if not agent_id:

        flash(
            "Please select an agent.",
            "danger"
        )

        return redirect(
            url_for(
                "supervisor.recommendations",
                task_id=task.id
            )
        )

    agent = db.session.get(
        OnboardingAgent,
        agent_id
    )

    if not agent:

        flash(
            "The selected agent could not be found.",
            "danger"
        )

        return redirect(
            url_for(
                "supervisor.recommendations",
                task_id=task.id
            )
        )

    if not agent.availability:

        flash(
            "The selected agent is currently unavailable.",
            "warning"
        )

        return redirect(
            url_for(
                "supervisor.recommendations",
                task_id=task.id
            )
        )

    assignment = TaskAssignment(
        task_id=task.id,
        agent_id=agent.id,
        supervisor_id=current_user.id,
        status="Assigned"
    )

    task.status = "Assigned"

    db.session.add(assignment)
    db.session.commit()

    flash(
        f"{task.task_type} was assigned to "
        f"{agent.name} successfully.",
        "success"
    )

    return redirect(
        url_for("supervisor.dashboard")
    )