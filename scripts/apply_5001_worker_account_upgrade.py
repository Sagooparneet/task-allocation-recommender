"""Apply the rehearsed account-deactivation migration only to the local port-5001 installation."""
import argparse
from pathlib import Path
import socket
import sys

from backup_5001_before_worker_account import backup_instance
from check_5001_worker_account_upgrade import (
    BASE, TARGET, FILES, snapshot, file_hashes, check_backup, verify_upgrade,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def require_server_stopped():
    with socket.socket() as sock:
        sock.settimeout(0.5)
        if sock.connect_ex(('127.0.0.1', 5001)) == 0:
            raise ValueError('Stop the port-5001 server with Ctrl+C before upgrading.')


def apply_to_instance(instance):
    """Internal routine; the command line always uses the fixed local installation."""
    instance = Path(instance).resolve()
    require_server_stopped()
    for name in FILES:
        if not (instance / name).is_file():
            raise ValueError(f'Missing installation file: {name}')
    database = instance / 'task_allocation.db'
    for suffix in ('-wal', '-journal'):
        sidecar = Path(str(database) + suffix)
        if sidecar.exists() and sidecar.stat().st_size:
            raise ValueError('A database journal exists. Keep the server stopped and investigate before upgrading.')
    revision, columns, _ = snapshot(database)
    if revision == [(TARGET,)]:
        if not {'account_disabled'} <= set(columns['onboarding_agents']):
            raise ValueError('Migration revision and worker columns disagree.')
        print('Worker account-deactivation migration already applied. No changes made.')
        return
    if revision != [(BASE,)]:
        raise ValueError(f'Expected migration {BASE}; found {revision}. No upgrade applied.')
    original = file_hashes(instance)
    backup = backup_instance(instance)
    print('Keep this backup until the worker account-deactivation feature is fully tested:', backup, flush=True)
    check_backup(backup, database, instance.parent)
    require_server_stopped()
    if file_hashes(instance) != original:
        raise ValueError('Installation changed during rehearsal. No upgrade applied to the original database.')
    print('Applying worker account-deactivation migration to:', database, flush=True)
    verify_upgrade(database, instance)
    current = file_hashes(instance)
    if any(current[name] != original[name] for name in FILES[1:]):
        raise ValueError('Configuration files changed unexpectedly. Keep the server stopped.')
    print('PORT-5001 WORKER-ACCOUNT UPGRADE: PASS')
    print('Existing records and configuration preserved. Neon was not accessed.')
    print('Only the database field is ready; account access enforcement and controls will be added next.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--server-stopped', action='store_true')
    args = parser.parse_args()
    if not args.apply or not args.server_stopped:
        parser.error('Stop port 5001, then use --apply --server-stopped.')
    instance = PROJECT_ROOT / 'instance' / 'netease_setup_test'
    if not instance.is_dir():
        parser.error('The port-5001 installation folder does not exist.')
    require_server_stopped()
    lock = instance / 'worker_account_upgrade.lock'
    try:
        with lock.open('x', encoding='utf-8') as stream:
            stream.write('Worker account-deactivation upgrade in progress\n')
    except FileExistsError:
        parser.error('An upgrade lock exists. Check the previous run before retrying.')
    try:
        apply_to_instance(instance)
    except BaseException:
        print('Upgrade did not finish. Keep the server stopped and retain the backup. Do not downgrade or restore automatically.', file=sys.stderr)
        raise
    finally:
        lock.unlink()


if __name__ == '__main__':
    main()
