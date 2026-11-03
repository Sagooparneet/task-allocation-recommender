"""Rehearse password-reset migration on a temporary copy of a verified backup."""

import argparse
import json
from pathlib import Path
import secrets
import shutil
import sys
import tempfile

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from flask_migrate import upgrade
from sqlalchemy.engine import URL

from app import create_app
from app.extensions import db
from scripts.check_5001_supervisor_account_upgrade import snapshot, file_hashes, FILES

BASE = '66a07d5e0f12'
TARGET = '66b08e6f1a23'
NEW_COLUMNS = {
    'password_reset_tokens': [
        'id', 'worker_id', 'supervisor_id', 'administrator_id',
        'token_hash', 'issued_at', 'expires_at', 'used_at',
    ],
    'password_reset_requests': [
        'id', 'email_digest', 'ip_digest', 'requested_at',
    ],
}


def upgrade_database(database, instance):
    app = create_app({
        'TESTING': True,
        'SECRET_KEY': secrets.token_hex(32),
        'SQLALCHEMY_DATABASE_URI': URL.create('sqlite', database=str(database)),
        'SQLALCHEMY_ENGINE_OPTIONS': {},
    })
    app.instance_path = str(instance)
    with app.app_context():
        try:
            if Path(db.engine.url.database).resolve() != database.resolve():
                raise ValueError('Database selection does not match the intended copy.')
            upgrade(directory=str(PROJECT_ROOT / 'migrations'), revision=TARGET)
        finally:
            db.session.remove()
            db.engine.dispose()


def verify_upgrade(database, instance):
    revision, columns, rows = snapshot(database)
    if revision != [(BASE,)]:
        raise ValueError(f'Expected migration {BASE}; found {revision}.')
    upgrade_database(database, instance)
    new_revision, new_columns, new_rows = snapshot(database)
    expected = dict(columns)
    expected.update(NEW_COLUMNS)
    if new_revision != [(TARGET,)] or new_columns != expected:
        raise ValueError('Unexpected password-reset schema or migration revision. Keep the backup.')
    if any(new_rows[name] != rows[name] for name in rows):
        raise ValueError('Existing database records changed. Keep the backup.')
    if any(new_rows[table] for table in NEW_COLUMNS):
        raise ValueError('A password-reset table was unexpectedly populated. Keep the backup.')
    print('Migration revision and two empty reset tables: PASS')
    print('Existing accounts, credentials, tasks and assignments preserved: PASS')
    print('Database integrity and foreign keys: PASS')
    for table in ('supervisors', 'administrators', 'onboarding_agents', 'tasks', 'task_assignments'):
        print(f'{table}: {len(rows[table])}')


def check_backup(backup, source_database, temp_parent):
    backup = Path(backup).resolve()
    manifest = json.loads((backup / 'backup_manifest.json').read_text(encoding='utf-8'))
    if (manifest.get('status') != 'verified'
            or Path(manifest['source_database']).resolve() != Path(source_database).resolve()):
        raise ValueError('Backup manifest does not identify the intended installation.')
    before = file_hashes(backup)
    if before != manifest['sha256'] or manifest.get('migration_revisions') != [BASE]:
        raise ValueError('Backup hashes or migration revision do not match its manifest.')
    with tempfile.TemporaryDirectory(prefix='password_reset_rehearsal_', dir=temp_parent) as folder:
        copy = Path(folder) / 'task_allocation.db'
        shutil.copy2(backup / 'task_allocation.db', copy)
        verify_upgrade(copy, Path(folder))
    if file_hashes(backup) != before:
        raise ValueError('Backup files changed unexpectedly.')
    print('Backup files unchanged; temporary copy removed: PASS')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backup', required=True, type=Path)
    args = parser.parse_args()
    instance = (PROJECT_ROOT / 'instance' / 'netease_setup_test').resolve()
    backup = args.backup.resolve()
    if not backup.is_relative_to(instance / 'backups'):
        parser.error('Choose a verified backup inside the port-5001 installation backup folder.')
    check_backup(backup, instance / 'task_allocation.db', instance.parent)
    print('Rehearsal finished. The port-5001 database and Neon were not changed.')


if __name__ == '__main__':
    main()
