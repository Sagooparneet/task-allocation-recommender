"""Rehearse issue 54 against a temporary copy of a verified port-5001 backup."""
import argparse
from contextlib import closing
import hashlib
import json
from pathlib import Path
import secrets
import shutil
import sqlite3
import sys
import tempfile

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from flask_migrate import upgrade
from sqlalchemy.engine import URL
from app import create_app
from app.extensions import db

BASE = '49a01b7c2d30'
TARGET = '54b01c8d3e40'
FILES = ('task_allocation.db', 'netease_agent_bindings.json',
         'onboarding_capability_mapping.json', 'setup_complete.json')


def quote(name):
    return '"' + name.replace('"', '""') + '"'


def file_hashes(folder):
    return {name: hashlib.sha256((Path(folder) / name).read_bytes()).hexdigest() for name in FILES}


def snapshot(database, projection=None):
    """Capture all application rows, using original columns after migration."""
    with closing(sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)) as connection:
        connection.execute('PRAGMA query_only=ON')
        if connection.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
            raise ValueError('Database integrity check failed.')
        if connection.execute('PRAGMA foreign_key_check').fetchall():
            raise ValueError('Database foreign-key check failed.')
        revision = connection.execute('SELECT version_num FROM alembic_version').fetchall()
        tables = {row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' AND name != 'alembic_version'"
        )}
        columns = {table: [r[1] for r in connection.execute('PRAGMA table_info(' + quote(table) + ')')]
                   for table in tables}
        if projection is not None and set(projection) != tables:
            raise ValueError('Application table set changed unexpectedly.')
        data = {}
        for table in sorted(tables):
            names = projection[table] if projection is not None else columns[table]
            rows = connection.execute('SELECT ' + ','.join(map(quote, names)) + ' FROM ' + quote(table)).fetchall()
            data[table] = sorted(rows, key=repr)
        return revision, columns, data


def upgrade_database(database, instance):
    app = create_app({
        'TESTING': True, 'SECRET_KEY': secrets.token_hex(32),
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
    if {'started_at', 'completed_at'} & set(columns['task_assignments']):
        raise ValueError('Progress columns already exist unexpectedly.')
    upgrade_database(database, instance)
    new_revision, new_columns, new_rows = snapshot(database, columns)
    if new_revision != [(TARGET,)] or rows != new_rows:
        raise ValueError('Migration revision or original records did not match expectations.')
    expected_columns = dict(columns)
    expected_columns['task_assignments'] = columns['task_assignments'] + ['started_at', 'completed_at']
    if new_columns != expected_columns:
        raise ValueError('Unexpected column changes detected.')
    with closing(sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)) as connection:
        count = connection.execute('SELECT COUNT(*) FROM task_assignments WHERE started_at IS NOT NULL OR completed_at IS NOT NULL').fetchone()[0]
        if count:
            raise ValueError('Historical timestamps must remain empty.')
    print('Migration revision and exactly two new columns: PASS')
    print('All existing application records preserved: PASS')
    print('Historical timestamps remain empty: PASS')
    print('Database integrity and foreign keys: PASS')
    for table in ('supervisors', 'administrators', 'onboarding_agents', 'tasks', 'task_assignments'):
        print(f'{table}: {len(rows[table])}')


def check_backup(backup, source_database, temp_parent):
    backup = Path(backup).resolve()
    manifest = json.loads((backup / 'backup_manifest.json').read_text(encoding='utf-8'))
    if manifest.get('status') != 'verified' or Path(manifest['source_database']).resolve() != Path(source_database).resolve():
        raise ValueError('Backup manifest does not identify the intended installation.')
    before = file_hashes(backup)
    if before != manifest['sha256']:
        raise ValueError('Backup file hashes do not match its manifest.')
    with tempfile.TemporaryDirectory(prefix='progress_rehearsal_', dir=temp_parent) as folder:
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
