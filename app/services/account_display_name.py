"""Resolve account presentation through the installation's explicit bindings."""
import json
from pathlib import Path

from flask import current_app
from app.extensions import db
from app.models import WorkerSourceBinding
from app.services.worker_display_names import worker_display_name


def account_display_name(user):
    if user.role != 'agent':
        return user.name
    storage = current_app.config.get('NETEASE_BINDING_STORAGE', 'file')
    try:
        if storage == 'database':
            binding = db.session.get(WorkerSourceBinding, user.id)
            source_id = binding.source_worker_id if binding else None
        elif storage == 'file':
            path = Path(current_app.instance_path) / 'netease_agent_bindings.json'
            if not path.is_file():
                return user.name
            mapping = json.loads(path.read_text(encoding='utf-8-sig'))
            if mapping.get('schema_version') != 1 or mapping.get('status') != 'ready':
                return user.name
            bindings = mapping.get('worker_bindings')
            if not isinstance(bindings, dict):
                return user.name
            source_id = bindings.get(str(user.id))
            if source_id is not None and list(bindings.values()).count(source_id) != 1:
                return user.name
        else:
            return user.name
        if source_id is None or user.email != f'netease-{source_id}@demo.invalid':
            return user.name
        return worker_display_name(source_id)
    except (OSError, ValueError, TypeError, AttributeError):
        current_app.logger.warning('Account display mapping unavailable; using stored account name.')
        return user.name
