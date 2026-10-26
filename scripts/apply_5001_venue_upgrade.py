"""Apply the rehearsed venue migration to the existing local port-5001 database."""
import argparse
from contextlib import closing
from datetime import datetime
import hashlib
import json
import shutil
import socket
import sqlite3
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import MetaData
from flask_migrate import upgrade
from app.extensions import db
from check_5001_venue_upgrade import (
    BASE, TARGET, FILES, app_for, check_backup, upgrade_verified_database,
)


def require_server_stopped():
    with socket.socket() as sock:
        sock.settimeout(0.5)
        if sock.connect_ex(('127.0.0.1', 5001)) == 0:
            raise ValueError('Port 5001 is running. Stop it with Ctrl+C before upgrading.')


def hashes(instance):
    return {name: hashlib.sha256((instance / name).read_bytes()).hexdigest() for name in FILES}


def apply_to_instance(instance):
    """Internal routine; CLI always supplies the fixed port-5001 installation."""
    instance = Path(instance).resolve()
    database = instance / 'task_allocation.db'
    for name in FILES:
        if not (instance / name).is_file():
            raise ValueError(f'Missing installation file: {name}')
    for suffix in ('-wal', '-journal'):
        sidecar = Path(str(database) + suffix)
        if sidecar.exists() and sidecar.stat().st_size:
            raise ValueError('An active database journal exists. Keep the server stopped and investigate before upgrading.')
    with closing(sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)) as connection:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if 'alembic_version' in tables:
            revisions = [row[0] for row in connection.execute('SELECT version_num FROM alembic_version')]
            if revisions == [TARGET]:
                print('Venue migration already applied. No changes made.')
                return
    original_hashes = hashes(instance)
    backup = instance / 'backups' / ('before_venue_apply_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    backup.parent.mkdir(exist_ok=True)
    backup.mkdir()
    with closing(sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)) as source:
        with closing(sqlite3.connect(str(backup / database.name))) as destination:
            source.backup(destination)
            if destination.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise ValueError('Fresh backup integrity check failed.')
    for name in FILES[1:]:
        shutil.copy2(instance / name, backup / name)
    (backup / 'backup_manifest.json').write_text(json.dumps({
        'status': 'verified', 'source_database': str(database), 'sha256': hashes(backup),
    }, indent=2) + '\n', encoding='utf-8')
    print('Fresh verified backup:', backup, flush=True)

    check_backup(backup, temp_parent=instance.parent)
    if hashes(instance) != original_hashes:
        raise ValueError('Installation changed during rehearsal. Original database was not upgraded.')
    require_server_stopped()
    migrations = str(PROJECT_ROOT / 'migrations')
    with tempfile.TemporaryDirectory(prefix='venue_baseline_', dir=instance.parent) as folder:
        baseline_app = app_for(Path(folder), 'baseline.db')
        metadata = MetaData()
        with baseline_app.app_context():
            try:
                upgrade(directory=migrations, revision=BASE)
                metadata.reflect(bind=db.engine)
                metadata.remove(metadata.tables['alembic_version'])
            finally:
                db.session.remove()
                db.engine.dispose()
        print('Applying verified upgrade to:', database, flush=True)
        upgrade_verified_database(instance, metadata, migrations)
    with closing(sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)) as connection:
        if connection.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise ValueError('Post-upgrade integrity check failed. Keep the server stopped.')
        if connection.execute('PRAGMA foreign_key_check').fetchall():
            raise ValueError('Post-upgrade foreign-key check failed. Keep the server stopped.')
    print('PORT-5001 UPGRADE: PASS')
    print('Existing accounts, passwords, tasks, assignments and ML scores verified unchanged.')
    print('Five venues are ready. Neon was not accessed.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--server-stopped', action='store_true')
    args = parser.parse_args()
    if not args.apply or not args.server_stopped:
        parser.error('Stop port 5001, then use --apply --server-stopped.')
    require_server_stopped()
    instance = PROJECT_ROOT / 'instance' / 'netease_setup_test'
    lock = instance / 'venue_upgrade.lock'
    try:
        with lock.open('x', encoding='utf-8') as stream:
            stream.write('Venue upgrade in progress\n')
    except FileExistsError:
        parser.error('An upgrade lock already exists. Check the previous run before retrying.')
    try:
        apply_to_instance(instance)
    except Exception:
        print('Upgrade did not finish. Keep the server stopped and retain the printed backup path.', file=sys.stderr)
        raise
    finally:
        lock.unlink()


if __name__ == '__main__':
    main()
