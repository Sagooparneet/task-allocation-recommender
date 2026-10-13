from datetime import datetime

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

    agents = (
        OnboardingAgent.query
        .order_by(
            OnboardingAgent.workload.asc(),
            OnboardingAgent.performance_score.desc()
        )
        .limit(5)
        .all()
    )

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
@supervisor_bp.route(
    "/task/<int:task_id>/recommendations"
)
@login_required
def recommendations(task_id):

    if current_user.role != "supervisor":
        return redirect(url_for("home"))

    task = Task.query.get_or_404(task_id)

    service = HybridRecommendationService()

    recommended_agents = service.get_recommendations(
        task_id,
        limit=5
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