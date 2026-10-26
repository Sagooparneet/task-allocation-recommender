"""Rehearse venue upgrade on a disposable copy of a verified local backup."""
import argparse
import hashlib
import json
import secrets
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import MetaData, inspect, text
from sqlalchemy.engine import URL
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from flask_migrate import upgrade, stamp
from app import create_app
from app.extensions import db
from app.models import Task, WorkVenue, TaskVenueDetails
from app.services.initial_work_venues import add_initial_venues
from app.services.netease_recommendation_service import NetEaseRecommendationService

BASE = '4baace48147a'
TARGET = '49a01b7c2d30'
FILES = ('task_allocation.db', 'netease_agent_bindings.json',
         'onboarding_capability_mapping.json', 'setup_complete.json')


def app_for(folder, filename='task_allocation.db'):
    app = create_app({'TESTING': True, 'SECRET_KEY': secrets.token_hex(32),
        'SQLALCHEMY_DATABASE_URI': URL.create('sqlite', database=str(folder / filename)),
        'SQLALCHEMY_ENGINE_OPTIONS': {}, 'NETEASE_BINDING_STORAGE': 'file'})
    app.instance_path = str(folder)
    return app


def fingerprints(table_names):
    results = {}
    for name in table_names:
        quoted = db.engine.dialect.identifier_preparer.quote(name)
        rows = db.session.execute(text(f'SELECT * FROM {quoted}')).all()
        results[name] = hashlib.sha256(repr(sorted(repr(tuple(row)) for row in rows)).encode()).hexdigest()
    return results


def recommendations():
    service = NetEaseRecommendationService()
    return {task.id: [(row['agent_id'], row['source_worker_id'], row['score'])
                      for row in service.get_recommendations(task.id)]
            for task in Task.query.order_by(Task.id).all()}


def upgrade_verified_database(folder, baseline_metadata, migrations):
    app = app_for(folder)
    with app.app_context():
        try:
            tables = set(inspect(db.engine).get_table_names())
            old_tables = sorted(tables - {'alembic_version'})
            with db.engine.connect() as connection:
                differences = compare_metadata(MigrationContext.configure(connection,
                    opts={'compare_type': True, 'compare_server_default': True}), baseline_metadata)
            if (len(differences) == 1 and differences[0][0] == 'add_table'
                    and differences[0][1].name == 'worker_source_bindings'
                    and 'alembic_version' not in tables):
                # The pre-deployment local seed used JSON worker mappings.
                # Only this exact known missing table may be reconciled here.
                baseline_metadata.tables['worker_source_bindings'].create(bind=db.engine)
                print('Older local schema: added missing worker-binding table in selected database.')
                with db.engine.connect() as connection:
                    differences = compare_metadata(MigrationContext.configure(connection,
                        opts={'compare_type': True, 'compare_server_default': True}), baseline_metadata)
            if differences:
                raise ValueError(f'Existing schema does not match the baseline: {differences}')
            print('Existing schema matches initial migration: PASS')
            if 'alembic_version' in tables:
                revisions = db.session.execute(text('SELECT version_num FROM alembic_version')).scalars().all()
                if revisions != [BASE]:
                    raise ValueError('Unexpected migration revision. Rehearsal stopped.')
            before = fingerprints(old_tables)
            ranking_before = recommendations()
            db.session.remove()
            # Register the baseline only after its complete schema was verified.
            if 'alembic_version' not in tables:
                stamp(directory=migrations, revision=BASE)
            upgrade(directory=migrations, revision=TARGET)
            if add_initial_venues(db.session) != 5:
                raise ValueError('Expected five new venues.')
            db.session.commit()
            if fingerprints(old_tables) != before:
                raise ValueError('Existing records changed during upgrade.')
            if recommendations() != ranking_before:
                raise ValueError('Recommendation identities or scores changed.')
            if TaskVenueDetails.query.count() != 0:
                raise ValueError('Legacy tasks were assigned venue details unexpectedly.')
            if add_initial_venues(db.session) != 0:
                raise ValueError('Repeated venue setup added duplicates.')
            db.session.commit()
            print('Existing accounts, tasks, assignments and other records unchanged: PASS')
            print(f'ML recommendation identities and scores unchanged for {len(ranking_before)} tasks: PASS')
            print('Legacy tasks remain city-only: PASS')
            print('Five venues and repeat-safe setup: PASS')
            print('Venues:', WorkVenue.query.count())
            print('Migration revision:', db.session.execute(text('SELECT version_num FROM alembic_version')).scalar_one())
        finally:
            db.session.remove()
            db.engine.dispose()


def check_backup(backup, temp_parent=None):
    backup = Path(backup).resolve()
    manifest = json.loads((backup / 'backup_manifest.json').read_text(encoding='utf-8'))
    if manifest.get('status') != 'verified':
        raise ValueError('Backup manifest is not marked verified.')
    for name in FILES:
        digest = hashlib.sha256((backup / name).read_bytes()).hexdigest()
        if digest != manifest['sha256'].get(name):
            raise ValueError(f'Backup file failed integrity verification: {name}')
    print('Backup file verification: PASS')
    migrations = str(PROJECT_ROOT / 'migrations')
    temp_parent = Path(temp_parent or PROJECT_ROOT / 'instance').resolve()
    with tempfile.TemporaryDirectory(prefix='venue_rehearsal_', dir=temp_parent) as temp:
        folder = Path(temp)
        baseline_app = app_for(folder, 'baseline.db')
        baseline_metadata = MetaData()
        with baseline_app.app_context():
            try:
                upgrade(directory=migrations, revision=BASE)
                baseline_metadata.reflect(bind=db.engine)
                baseline_metadata.remove(baseline_metadata.tables['alembic_version'])
            finally:
                db.session.remove()
                db.engine.dispose()
        for name in FILES:
            shutil.copy2(backup / name, folder / name)
        upgrade_verified_database(folder, baseline_metadata, migrations)
    print('Temporary copy removed. Original database, backup and Neon were not changed.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backup-name', required=True, help='Folder name printed by the backup script')
    args = parser.parse_args()
    parent = (PROJECT_ROOT / 'instance/netease_setup_test/backups').resolve()
    backup = (parent / args.backup_name).resolve()
    if backup.parent != parent or not backup.is_dir():
        parser.error('Choose an existing backup folder directly within the port-5001 backups directory.')
    check_backup(backup)


if __name__ == '__main__':
    main()
