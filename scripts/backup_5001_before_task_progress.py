"""Back up the existing port-5001 installation without changing it."""
from contextlib import closing
from datetime import datetime
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3


def backup_instance(instance):
    instance = Path(instance).resolve()
    database = instance / 'task_allocation.db'
    configs = ('netease_agent_bindings.json', 'onboarding_capability_mapping.json', 'setup_complete.json')
    for name in ('task_allocation.db', *configs):
        if not (instance / name).is_file():
            raise SystemExit(f'Missing installation file: {name}. No backup started.')
    backup = instance / 'backups' / ('before_task_progress_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    backup.parent.mkdir(exist_ok=True)
    backup.mkdir()
    with closing(sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)) as source:
        source.execute('PRAGMA query_only=ON')
        with closing(sqlite3.connect(str(backup / database.name))) as destination:
            source.backup(destination)
            if destination.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise SystemExit('Backup integrity check failed. Source database unchanged.')
            tables = {row[0] for row in destination.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            counts = {}
            for table in ('supervisors', 'administrators', 'onboarding_agents', 'tasks', 'task_assignments'):
                counts[table] = destination.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            revision = [row[0] for row in destination.execute('SELECT version_num FROM alembic_version')] if 'alembic_version' in tables else []
    for name in configs:
        shutil.copy2(instance / name, backup / name)
    hashes = {name: hashlib.sha256((backup / name).read_bytes()).hexdigest()
              for name in ('task_allocation.db', *configs)}
    manifest = {'source_database': str(database), 'counts': counts,
                'migration_revisions': revision, 'sha256': hashes, 'status': 'verified'}
    (backup / 'backup_manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print('Verified backup:', backup)
    print('Integrity: ok')
    for table, count in counts.items():
        print(f'{table}: {count}')
    print('Migration revisions:', ', '.join(revision) or 'not recorded')
    print('Configuration files copied: 3')
    print('Original database unchanged. No migrations were applied.')
    return backup


def main():
    project = Path(__file__).resolve().parents[1]
    backup_instance(project / 'instance' / 'netease_setup_test')


if __name__ == '__main__':
    main()
