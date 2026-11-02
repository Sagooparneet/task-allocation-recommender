"""Independent registration rules; never create or borrow dataset bindings."""
import json
import re
from pathlib import Path
from flask import current_app
from sqlalchemy import func
from app.extensions import db
from app.models import Administrator, Supervisor, OnboardingAgent, WorkerSourceBinding, IndependentWorkerRegistration, Skill
from app.services.skill_display_labels import SKILL_LABELS

PENDING_PASSWORD = '!pending-independent-worker-setup'


def pending_account_setup(worker):
    return (worker.password_hash == PENDING_PASSWORD
            and db.session.get(IndependentWorkerRegistration, worker.id) is not None)


def registration_services():
    allowed = set(SKILL_LABELS.values()) | {'NetEase capability ' + code for code in SKILL_LABELS}
    return Skill.query.filter(Skill.name.in_(allowed)).order_by(Skill.id).all()


def valid_email(value):
    if not value.isascii() or len(value) > 120 or value.count('@') != 1:
        return False
    local, domain = value.split('@')
    if not local or len(local) > 64 or local.startswith('.') or local.endswith('.') or '..' in local:
        return False
    if not re.fullmatch(r"[a-z0-9.!#$%&'*+/=?^_`{|}~-]+", local):
        return False
    labels = domain.split('.')
    return len(labels) >= 2 and all(re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', label) for label in labels)


def email_in_use(email):
    return any(db.session.query(model.id).filter(func.lower(model.email) == email).first()
               for model in (OnboardingAgent, Supervisor, Administrator))


def require_unbound_identity(agent_id):
    if db.session.get(WorkerSourceBinding, agent_id) is not None:
        raise ValueError('Unexpected source identity binding.')
    mode = current_app.config.get('NETEASE_BINDING_STORAGE', 'file')
    if mode == 'database':
        return
    if mode != 'file':
        raise ValueError('Unknown binding configuration.')
    path = Path(current_app.instance_path) / 'netease_agent_bindings.json'
    mapping = json.loads(path.read_text(encoding='utf-8-sig'))
    if mapping.get('schema_version') != 1 or mapping.get('status') != 'ready' or not isinstance(mapping.get('worker_bindings'), dict):
        raise ValueError('Invalid binding configuration.')
    if str(agent_id) in mapping['worker_bindings']:
        raise ValueError('New identity would overlap an existing source binding.')
