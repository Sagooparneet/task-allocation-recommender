"""Service matching for administrator-added workers, separate from ML rankings."""
from sqlalchemy import func, exists
from app.extensions import db
from app.models import OnboardingAgent, IndependentWorkerRegistration, WorkerSourceBinding, AgentSkill, TaskSkill
from app.services.independent_workers import PENDING_PASSWORD, require_unbound_identity, registration_services
from app.services.worker_capacity import active_task_counts, MAX_ACTIVE_TASKS


def matching_workers(task_id, worker_id=None):
    required = {row.skill_id for row in TaskSkill.query.filter_by(task_id=task_id).all()}
    allowed = {skill.id for skill in registration_services()}
    # Empty or unsupported requirements are not evidence of a service match.
    if not required or not required.issubset(allowed):
        return []
    qualified = db.session.query(AgentSkill.agent_id).filter(
        AgentSkill.skill_id.in_(required),
        AgentSkill.proficiency_level == 'Administrator confirmed',
    ).group_by(AgentSkill.agent_id).having(func.count(func.distinct(AgentSkill.skill_id)) == len(required))
    query = OnboardingAgent.query.join(IndependentWorkerRegistration,
        IndependentWorkerRegistration.agent_id == OnboardingAgent.id).filter(
        OnboardingAgent.id.in_(qualified),
        OnboardingAgent.availability.is_(True),
        OnboardingAgent.account_disabled.is_(False),
        OnboardingAgent.password_hash != PENDING_PASSWORD,
        OnboardingAgent.password_hash != '',
        ~exists().where(WorkerSourceBinding.agent_id == OnboardingAgent.id),
    )
    if worker_id is not None:
        query = query.filter(OnboardingAgent.id == worker_id)
    counts = active_task_counts()
    result = []
    for worker in query.populate_existing().all():
        if counts.get(worker.id, 0) >= MAX_ACTIVE_TASKS:
            continue
        try:
            require_unbound_identity(worker.id)
        except (ValueError, OSError, TypeError, AttributeError):
            continue
        result.append({'agent_id': worker.id, 'name': worker.profile_display_name or worker.name,
            'city': worker.location, 'active_tasks': counts.get(worker.id, 0)})
    return sorted(result, key=lambda item: (item['name'].casefold(), item['agent_id']))
