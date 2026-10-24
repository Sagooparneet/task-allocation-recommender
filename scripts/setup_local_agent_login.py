"""Enable one controlled login in the port-5001 installation only."""
import argparse
import json
import secrets
import sqlite3
import sys
from datetime import datetime
from getpass import getpass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-worker', required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    instance = PROJECT_ROOT / 'instance' / 'netease_setup_test'
    database = instance / 'task_allocation.db'
    mapping_file = instance / 'netease_agent_bindings.json'
    if not database.is_file() or not mapping_file.is_file():
        raise SystemExit('Port-5001 test installation not found. No changes made.')
    mapping = json.loads(mapping_file.read_text(encoding='utf-8-sig'))
    if mapping.get('schema_version') != 1 or mapping.get('status') != 'ready':
        raise SystemExit('Worker mapping is not ready. No changes made.')
    matches = [key for key, value in mapping['worker_bindings'].items()
               if str(value) == args.source_worker]
    if len(matches) != 1:
        raise SystemExit('Expected exactly one worker mapping. No changes made.')

    from sqlalchemy.engine import URL
    from app import create_app
    from app.extensions import db
    from app.models import OnboardingAgent, TaskAssignment, Supervisor, Administrator
    from app.services.worker_display_names import worker_display_name

    app = create_app({
        'SQLALCHEMY_DATABASE_URI': URL.create('sqlite', database=str(database)),
        'SECRET_KEY': secrets.token_hex(32),
        'NETEASE_BINDING_STORAGE': 'file',
    })
    app.instance_path = str(instance)
    with app.app_context():
        worker = db.session.get(OnboardingAgent, int(matches[0]))
        expected_email = f'netease-{args.source_worker}@demo.invalid'
        if worker is None or worker.email != expected_email:
            raise SystemExit('Worker identity mismatch. No changes made.')
        if (Supervisor.query.filter_by(email=expected_email).first()
                or Administrator.query.filter_by(email=expected_email).first()):
            raise SystemExit('Another role uses this email. No changes made.')
        print('Installation:', instance)
        print('Worker:', worker_display_name(args.source_worker))
        print('Login email:', worker.email)
        print('Assignments:', TaskAssignment.query.filter_by(agent_id=worker.id).count())
        if not args.apply:
            print('Read-only checks passed. No password or database records changed.')
            return
        password = getpass('Choose a local test password (12+ characters): ')
        confirmation = getpass('Confirm password: ')
        if len(password) < 12 or password != confirmation:
            raise SystemExit('Password must match and contain 12+ characters. No changes made.')
        backups = instance / 'backups'
        backups.mkdir(exist_ok=True)
        backup = backups / ('before_agent_login_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f') + '.db')
        with sqlite3.connect(database.as_uri() + '?mode=ro', uri=True) as source:
            with sqlite3.connect(str(backup)) as destination:
                source.backup(destination)
                if destination.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                    raise SystemExit('Backup integrity check failed. Password unchanged.')
        worker.set_password(password)
        db.session.commit()
        print('Backup:', backup)
        print('Local test login enabled. Tasks, workload and identity mappings unchanged.')
        print('Sign in at http://127.0.0.1:5001/auth/login')
        print('Neon and the original local database were not changed.')


if __name__ == '__main__':
    main()
