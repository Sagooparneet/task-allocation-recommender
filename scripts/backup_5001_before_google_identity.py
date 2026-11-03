"""Back up port 5001 before adding Google identity storage."""
from contextlib import closing
from datetime import datetime
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3


FILES = ('task_allocation.db', 'netease_agent_bindings.json',
         'onboarding_capability_mapping.json', 'setup_complete.json')
EXPECTED_REVISION = '66b08e6f1a23'


def backup_instance(instance):
    instance = Path(instance).resolve()
    database = instance / FILES[0]
    for name in FILES:
        if not (instance / name).is_file():
            raise ValueError(f'Missing installation file: {name}. No backup started.')
    with closing(sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)) as source:
        source.execute('PRAGMA query_only=ON')
        revision = [row[0] for row in source.execute('SELECT version_num FROM alembic_version')]
        if revision != [EXPECTED_REVISION]:
            raise ValueError(f'Expected migration {EXPECTED_REVISION}; found {revision}. No backup started.')
        backup = instance / 'backups' / ('before_google_identity_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
        backup.mkdir(parents=True)
        with closing(sqlite3.connect(backup / FILES[0])) as destination:
            source.backup(destination)
            if destination.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise ValueError('Backup integrity check failed. Source database unchanged.')
            if destination.execute('PRAGMA foreign_key_check').fetchall():
                raise ValueError('Backup foreign-key check failed. Source database unchanged.')
            counts = {table: destination.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
                      for table in ('supervisors', 'administrators', 'onboarding_agents', 'tasks', 'task_assignments')}
    for name in FILES[1:]:
        shutil.copy2(instance / name, backup / name)
    hashes = {name: hashlib.sha256((backup / name).read_bytes()).hexdigest() for name in FILES}
    manifest = {'source_database': str(database), 'counts': counts,
                'migration_revisions': revision, 'sha256': hashes, 'status': 'verified'}
    (backup / 'backup_manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print('Verified backup:', backup)
    print('Integrity and foreign keys: ok')
    for table, count in counts.items():
        print(f'{table}: {count}')
    print('Migration revision:', revision[0])
    print('Configuration files copied: 3')
    print('Original database unchanged. No migrations were applied.')
    return backup


if __name__ == '__main__':
    backup_instance(Path(__file__).resolve().parents[1] / 'instance' / 'netease_setup_test')
