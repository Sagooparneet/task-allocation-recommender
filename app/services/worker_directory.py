"""Read-only worker directory presentation; never changes model bindings."""
from collections import Counter
import json
from pathlib import Path

from flask import current_app
from app.extensions import db
from app.models import OnboardingAgent, WorkerSourceBinding
from app.services.worker_display_names import worker_display_name


def directory_names(include_sources=False):
    rows = db.session.query(OnboardingAgent.id, OnboardingAgent.name, OnboardingAgent.email, OnboardingAgent.profile_display_name).all()
    names = {row.id: row.profile_display_name or row.name for row in rows}
    source_names = {}
    def result():
        return (names, source_names) if include_sources else names
    storage = current_app.config.get('NETEASE_BINDING_STORAGE', 'file')
    try:
        if storage == 'database':
            bindings = {str(row.agent_id): row.source_worker_id for row in WorkerSourceBinding.query.all()}
        elif storage == 'file':
            path = Path(current_app.instance_path) / 'netease_agent_bindings.json'
            if not path.is_file():
                return result()
            document = json.loads(path.read_text(encoding='utf-8-sig'))
            if document.get('schema_version') != 1 or document.get('status') != 'ready':
                return result()
            bindings = document.get('worker_bindings')
        else:
            return result()
        if not isinstance(bindings, dict) or not all(isinstance(value, str) for value in bindings.values()):
            return result()
        occurrences = Counter(bindings.values())
        for row in rows:
            source_id = bindings.get(str(row.id))
            if source_id is not None and occurrences[source_id] == 1 and row.email == f'netease-{source_id}@demo.invalid':
                names[row.id] = row.profile_display_name or worker_display_name(source_id)
                source_names[source_id] = names[row.id]
    except (OSError, ValueError, TypeError, AttributeError):
        current_app.logger.warning('Worker directory display mapping unavailable; using stored names.')
    return result()
