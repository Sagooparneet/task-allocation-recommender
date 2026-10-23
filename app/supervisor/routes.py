import secrets

from flask import abort, current_app, session
from sqlalchemy import update, exists, func
from sqlalchemy.exc import SQLAlchemyError

from app.services.netease_recommendation_service import NetEaseRecommendationService
from datetime import datetime
from app.services.netease_dataset_profiles import load_dataset_profiles

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
    TaskAssignment,
    Skill,
    TaskSkill
)

from app.services.recommendation_service import HybridRecommendationService


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

    total_tasks = len(tasks)

    pending_tasks = sum(
        1 for task in tasks
        if task.status == "Pending"
    )

    completed_tasks = sum(
        1 for task in tasks
        if task.status == "Completed"
    )

    available_agents = (
        OnboardingAgent.query
        .filter_by(availability=True)
        .count()
    )

    recent_tasks = tasks[:5]

    dataset_profiles = load_dataset_profiles()

    # Preview the first five workers by original numeric worker ID.
    # This is a dataset overview, not a recommendation ranking.
    agents = [
        dataset_profiles[worker_id]
        for worker_id in sorted(dataset_profiles, key=int)[:5]
    ]

    return render_template(
        "supervisor/dashboard.html",
        tasks=tasks,
        total_tasks=total_tasks,
        pending_tasks=pending_tasks,
        completed_tasks=completed_tasks,
        available_agents=available_agents,
        recent_tasks=recent_tasks,
        agents=agents
    )


@supervisor_bp.route(
    "/task/create",
    methods=["GET", "POST"]
)
@login_required
def create_task():

    if current_user.role != "supervisor":
        return redirect(url_for("home"))

    # -------------------------
    # FORM OPTIONS
    # -------------------------

    skills = Skill.query.order_by(
        Skill.name
    ).all()

    task_types = [
        "KYC Verification",
        "SIM Registration",
        "M-PESA Onboarding",
        "Account Activation"
    ]

    locations = [
        row[0]
        for row in (
            db.session.query(
                OnboardingAgent.location
            )
            .filter(
                OnboardingAgent.location.isnot(None),
                OnboardingAgent.location != ""
            )
            .distinct()
            .order_by(
                OnboardingAgent.location
            )
            .all()
        )
    ]


    # -------------------------
    # FORM SUBMISSION
    # -------------------------

    if request.method == "POST":

        selected_task_type = request.form.get(
            "task_type",
            ""
        ).strip()

        custom_task_type = request.form.get(
            "custom_task_type",
            ""
        ).strip()

        if selected_task_type == "__other__":
            task_type = custom_task_type
        else:
            task_type = selected_task_type


        description = request.form.get(
            "description",
            ""
        ).strip()


        location = request.form.get(
            "location",
            ""
        ).strip()


        priority = request.form.get(
            "priority",
            "Medium"
        )


        deadline_value = request.form.get(
            "deadline"
        )


        selected_skill_ids = request.form.getlist(
            "required_skills"
        )


        # -------------------------
        # VALIDATION
        # -------------------------

        if (
            selected_task_type == "__other__"
            and not custom_task_type
        ):

            flash(
                "Please enter the new task type.",
                "danger"
            )

            return render_template(
                "supervisor/create_task.html",
                skills=skills,
                locations=locations,
                task_types=task_types
            )


        if not task_type or not location:

            flash(
                "Task type and location are required.",
                "danger"
            )

            return render_template(
                "supervisor/create_task.html",
                skills=skills,
                locations=locations,
                task_types=task_types
            )


        if not selected_skill_ids:

            flash(
                "Please select at least one required skill.",
                "danger"
            )

            return render_template(
                "supervisor/create_task.html",
                skills=skills,
                locations=locations,
                task_types=task_types
            )


        # -------------------------
        # DEADLINE
        # -------------------------

        deadline = None

        if deadline_value:

            try:

                deadline = datetime.strptime(
                    deadline_value,
                    "%Y-%m-%dT%H:%M"
                )

            except ValueError:

                flash(
                    "Please enter a valid deadline.",
                    "danger"
                )

                return render_template(
                    "supervisor/create_task.html",
                    skills=skills,
                    locations=locations,
                    task_types=task_types
                )


        # -------------------------
        # CREATE TASK
        # -------------------------

        task = Task(
            task_type=task_type,
            description=description,
            location=location,
            priority=priority,
            deadline=deadline,
            status="Pending",
            supervisor_id=current_user.id
        )

        db.session.add(task)

        # Generates task ID before TaskSkill records are created
        db.session.flush()


        # -------------------------
        # ADD REQUIRED SKILLS
        # -------------------------

        for skill_id in selected_skill_ids:

            task_skill = TaskSkill(
                task_id=task.id,
                skill_id=int(skill_id)
            )

            db.session.add(task_skill)


        db.session.commit()


        flash(
            f"{task.task_type} was created successfully.",
            "success"
        )

        return redirect(
            url_for("supervisor.dashboard")
        )


    # -------------------------
    # INITIAL PAGE LOAD
    # -------------------------

    return render_template(
        "supervisor/create_task.html",
        skills=skills,
        locations=locations,
        task_types=task_types
    )


@supervisor_bp.route("/task/<int:task_id>/recommendations")
@login_required
def recommendations(task_id):
    if current_user.role != "supervisor":
        return redirect(url_for("home"))

    task = Task.query.get_or_404(task_id)
    if task.supervisor_id != current_user.id:
        abort(403)

    recommendation_error = None
    try:
        recommended_agents = HybridRecommendationService().get_recommendations(task_id, limit=5)
    except ValueError as exc:
        recommended_agents = []
        recommendation_error = str(exc)
    except OSError:
        recommended_agents = []
        recommendation_error = "The model or demonstration mapping files could not be loaded."

    if "assignment_csrf_token" not in session:
        session["assignment_csrf_token"] = secrets.token_urlsafe(32)

    already_assigned = TaskAssignment.query.filter_by(task_id=task.id).first() is not None
    return render_template(
        "supervisor/recommendations.html",
        task=task,
        recommendations=recommended_agents,
        recommendation_error=recommendation_error,
        assignment_csrf_token=session["assignment_csrf_token"],
        assignments_enabled=(task.status == "Pending" and not already_assigned and recommendation_error is None)
    )


@supervisor_bp.route("/task/<int:task_id>/assign", methods=["POST"])
@login_required
def assign_task(task_id):
    if current_user.role != "supervisor":
        return redirect(url_for("home"))

    task = Task.query.get_or_404(task_id)
    if task.supervisor_id != current_user.id:
        abort(403)

    expected = session.get("assignment_csrf_token", "")
    supplied = request.form.get("assignment_csrf_token", "")
    if not expected or not secrets.compare_digest(supplied, expected):
        flash("The assignment form expired or is invalid. Refresh recommendations and try again.", "warning")
        return redirect(url_for("supervisor.recommendations", task_id=task.id))

    if task.status != "Pending" or TaskAssignment.query.filter_by(task_id=task.id).first():
        flash("This task is no longer pending or already has an assignment.", "warning")
        return redirect(url_for("supervisor.recommendations", task_id=task.id))

    agent_id = request.form.get("agent_id", type=int)
    try:
        _, _, candidates = NetEaseRecommendationService().get_eligible_candidates(task.id)
    except (ValueError, OSError):
        flash("Eligibility could not be checked. Review the task's capability mapping before assigning.", "warning")
        return redirect(url_for("supervisor.recommendations", task_id=task.id))

    selected = next((agent for agent in candidates.values() if agent.id == agent_id), None)
    if selected is None:
        flash("This agent is no longer available or does not meet all mapped task requirements.", "warning")
        return redirect(url_for("supervisor.recommendations", task_id=task.id))

    selected_name, selected_task_type = selected.name, task.task_type
    supervisor_id = current_user.id
    try:
        # Conditional update prevents duplicate assignment through competing requests.
        claim = db.session.execute(
            update(Task).where(
                Task.id == task_id,
                Task.supervisor_id == supervisor_id,
                Task.status == "Pending",
                ~exists().where(TaskAssignment.task_id == task_id)
            ).values(status="Assigned").execution_options(synchronize_session=False)
        )
        if claim.rowcount != 1:
            db.session.rollback()
            flash("Another request changed or assigned this task. Please refresh.", "warning")
            return redirect(url_for("supervisor.recommendations", task_id=task_id))

        agent_update = db.session.execute(
            update(OnboardingAgent).where(
                OnboardingAgent.id == agent_id,
                OnboardingAgent.availability.is_(True)
            ).values(workload=func.coalesce(OnboardingAgent.workload, 0) + 1)
            .execution_options(synchronize_session=False)
        )
        if agent_update.rowcount != 1:
            db.session.rollback()
            flash("The agent's availability changed. Please refresh recommendations.", "warning")
            return redirect(url_for("supervisor.recommendations", task_id=task_id))

        db.session.add(TaskAssignment(
            task_id=task_id,
            agent_id=agent_id,
            supervisor_id=supervisor_id,
            status="Assigned"
        ))
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Task assignment transaction failed")
        flash("The assignment could not be saved. Refresh and try again.", "danger")
        return redirect(url_for("supervisor.recommendations", task_id=task_id))

    flash(f"{selected_task_type} was assigned to {selected_name} successfully.", "success")
    return redirect(url_for("supervisor.dashboard"))
