from app.services.worker_display_names import worker_display_name
import secrets

from flask import abort, current_app, session
from sqlalchemy import update, exists, func
from sqlalchemy.exc import SQLAlchemyError

from app.services.netease_recommendation_service import NetEaseRecommendationService
from datetime import datetime, timedelta, timezone
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
    TaskSkill, WorkVenue, TaskVenueDetails
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

    now = datetime.now(timezone(timedelta(hours=3))).replace(tzinfo=None)
    owned = Task.query.filter_by(supervisor_id=current_user.id)
    counts = dict(db.session.query(Task.status, func.count(Task.id))
                  .filter(Task.supervisor_id == current_user.id).group_by(Task.status).all())
    total = sum(counts.values())
    pending = counts.get("Pending", 0)
    assigned = counts.get("Assigned", 0)
    in_progress = counts.get("In progress", 0)
    completed = counts.get("Completed", 0)
    other = total - pending - assigned - in_progress - completed
    overdue = owned.filter(Task.status != "Completed", Task.deadline < now).count()
    end_of_day = now.replace(hour=23, minute=59, second=59, microsecond=999999)
    due_today = owned.filter(Task.status != "Completed", Task.deadline >= now,
                            Task.deadline <= end_of_day).count()
    priorities = dict(db.session.query(Task.priority, func.count(Task.id))
                      .filter(Task.supervisor_id == current_user.id).group_by(Task.priority).all())

    search = request.args.get("q", "").strip()[:100]
    selected_status = request.args.get("status", "")
    valid_statuses = ("Pending", "Assigned", "In progress", "Completed", "Overdue")
    if selected_status not in valid_statuses:
        selected_status = ""
    filtered = owned
    if search:
        filtered = filtered.filter(Task.task_type.contains(search, autoescape=True))
    if selected_status == "Overdue":
        filtered = filtered.filter(Task.status != "Completed", Task.deadline < now)
    elif selected_status:
        filtered = filtered.filter(Task.status == selected_status)
    page_number = max(1, request.args.get("page", 1, type=int) or 1)
    page = filtered.order_by(Task.created_at.desc(), Task.id.desc()).paginate(
        page=page_number, per_page=10, error_out=False)
    profiles = load_dataset_profiles()
    from app.services.worker_directory import directory_names
    _, profile_names = directory_names(include_sources=True)
    workers = [{**profiles[key], 'display_name': profile_names.get(key, profiles[key]['display_name'])}
               for key in sorted(profiles, key=int)[:5]]
    progress_details = {}
    # Fetch only assignments for this supervisor's visible tasks, not the
    # full task history. Unknown historical timestamps remain undisplayed.
    assignments = TaskAssignment.query.join(Task).filter(
        Task.supervisor_id == current_user.id,
        Task.id.in_([task.id for task in page.items]),
    ).order_by(TaskAssignment.id).all()
    for assignment in assignments:
        progress_details.setdefault(assignment.task_id, []).append({
            'started': (assignment.started_at + timedelta(hours=3)).strftime('%d %b %Y, %H:%M')
                       if assignment.started_at is not None else None,
            'completed': (assignment.completed_at + timedelta(hours=3)).strftime('%d %b %Y, %H:%M')
                         if assignment.completed_at is not None else None,
        })
    return render_template(
        "supervisor/dashboard.html", total_tasks=total, pending_tasks=pending,
        assigned_tasks=assigned, in_progress_tasks=in_progress,
        completed_tasks=completed, other_tasks=other,
        progress_details=progress_details,
        overdue_tasks=overdue, due_today=due_today,
        available_agents=OnboardingAgent.query.filter_by(availability=True, account_disabled=False).count(),
        completion_percent=round(100 * completed / total) if total else 0,
        completed_end=100 * completed / total if total else 0,
        in_progress_end=100 * (completed + in_progress) / total if total else 0,
        assigned_end=100 * (completed + in_progress + assigned) / total if total else 0,
        pending_end=100 * (completed + in_progress + assigned + pending) / total if total else 0,
        priorities=priorities, agents=workers, task_page=page,
        search=search, selected_status=selected_status, now=now,
        venue_details={item.task_id: item for item in TaskVenueDetails.query.filter(
            TaskVenueDetails.task_id.in_([task.id for task in page.items])).all()},
    )


@supervisor_bp.route(
    "/task/create",
    methods=["GET", "POST"]
)
@login_required
def create_task():

    if current_user.role != "supervisor":
        return redirect(url_for("home"))

    today_eat = datetime.now(timezone(timedelta(hours=3))).date()
    locations = ["Nairobi", "Mombasa", "Kisumu", "Nakuru", "Eldoret"]
    skills = Skill.query.order_by(Skill.name).all()
    venues = WorkVenue.query.filter_by(is_active=True).order_by(WorkVenue.city, WorkVenue.name).all()
    if "task_create_csrf_token" not in session:
        session["task_create_csrf_token"] = secrets.token_urlsafe(32)

    def show_form(errors=None):
        return render_template("supervisor/create_task.html", skills=skills,
            locations=locations, venues=venues, form_errors=errors or {},
            deadline_min=today_eat.isoformat() + "T00:00",
            task_create_csrf_token=session["task_create_csrf_token"])

    if request.method == "GET":
        return show_form()
    expected = session["task_create_csrf_token"]
    supplied = request.form.get("task_create_csrf_token", "")
    if not secrets.compare_digest(expected.encode(), supplied.encode()):
        abort(400, description="This form expired. Reload Create Task and try again.")
    # Keep the stored field and older custom-title submissions compatible.
    selected_type = request.form.get("task_type", "").strip()
    custom_type = request.form.get("custom_task_type", "").strip()
    task_type = custom_type if selected_type == "__other__" else selected_type
    location = request.form.get("location", "").strip()
    errors = {}
    if not task_type:
        errors['task_type'] = "Please enter a task title."
    elif len(task_type) > 100:
        errors['task_type'] = "Keep the task title within 100 characters."
    if location not in locations:
        errors['location'] = "Please select a location from the list."
    selected_skills = request.form.getlist("required_skills")
    skill_ids = set()
    if not selected_skills:
        errors['required_skills'] = "Please select at least one service."
    else:
        try:
            skill_ids = {int(value) for value in selected_skills}
        except ValueError:
            errors['required_skills'] = "Please select valid services from the list."
        if not skill_ids.issubset({skill.id for skill in skills}):
            errors['required_skills'] = "Please select valid services from the list."
    deadline_value = request.form.get("deadline", "").strip()
    deadline = None
    if not deadline_value:
        errors['deadline'] = "Please choose a deadline."
    else:
        try:
            deadline = datetime.strptime(deadline_value, "%Y-%m-%dT%H:%M")
        except ValueError:
            errors['deadline'] = "Please enter a valid deadline."
        if deadline is not None and deadline.date() < today_eat:
            errors['deadline'] = "Please choose today or a later date for the deadline (Kenya time)."
    priority = request.form.get("priority", "Medium")
    if priority not in ("Low", "Medium", "High"):
        errors['priority'] = "Please choose a priority from the list."
    venue_id = request.form.get("venue_id", type=int)
    # Refresh the record to reject venues deactivated since the form opened.
    venue = db.session.get(WorkVenue, venue_id, populate_existing=True) if venue_id else None
    if venue is None or not venue.is_active or venue.city != location:
        errors['venue_id'] = "Please choose an active work location in the selected city."
    reporting_point = request.form.get("reporting_point", "").strip()
    instructions = request.form.get("location_instructions", "").strip()
    contact_details = request.form.get("location_contact", "").strip()
    if not reporting_point or len(reporting_point) > 200:
        errors['reporting_point'] = "Enter where the agent should report, using 1 to 200 characters."
    if len(instructions) > 2000:
        errors['location_instructions'] = "Keep arrival instructions within 2,000 characters."
    if len(contact_details) > 250:
        errors['location_contact'] = "Keep contact details within 250 characters."
    if errors:
        return show_form(errors)
    try:
        task = Task(task_type=task_type, description=request.form.get("description", "").strip(),
            location=location, priority=priority, deadline=deadline, status="Pending",
            supervisor_id=current_user.id)
        db.session.add(task)
        db.session.flush()
        for skill_id in sorted(skill_ids):
            db.session.add(TaskSkill(task_id=task.id, skill_id=skill_id))
        db.session.add(TaskVenueDetails(task_id=task.id, venue_id=venue.id,
            city=venue.city, venue_name=venue.name, address=venue.address,
            directions=venue.directions, map_url=venue.map_url,
            reporting_point=reporting_point, instructions=instructions,
            contact_details=contact_details))
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Task creation transaction failed")
        return show_form({"__all__": "The task could not be saved. Please try again."})
    flash(f"{task.task_type} was created successfully.", "success")
    return redirect(url_for("supervisor.dashboard"))


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
        recommendation_error = "Recommendations could not be loaded. Please contact your administrator."
    except OSError:
        recommended_agents = []
        recommendation_error = "Recommendations are temporarily unavailable. Please contact your administrator."

    if "assignment_csrf_token" not in session:
        session["assignment_csrf_token"] = secrets.token_urlsafe(32)

    already_assigned = TaskAssignment.query.filter_by(task_id=task.id).first() is not None
    return render_template(
        "supervisor/recommendations.html",
        task=task,
        venue_details=db.session.get(TaskVenueDetails, task.id),
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
        flash("Eligibility could not be checked. Please contact your administrator.", "warning")
        return redirect(url_for("supervisor.recommendations", task_id=task.id))

    selected = next((agent for agent in candidates.values() if agent.id == agent_id), None)
    if selected is None:
        flash("This agent is no longer available or does not meet all mapped task requirements.", "warning")
        return redirect(url_for("supervisor.recommendations", task_id=task.id))

    selected_source_id = next(
        source_id for source_id, agent in candidates.items() if agent.id == selected.id
    )
    selected_name = worker_display_name(selected_source_id)
    selected_task_type = task.task_type
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
                OnboardingAgent.availability.is_(True),
                OnboardingAgent.account_disabled.is_(False)
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
