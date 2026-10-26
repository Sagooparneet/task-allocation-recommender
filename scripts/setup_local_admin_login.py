"""Create the first administrator in the existing port-5001 installation."""
import argparse
from contextlib import closing
from datetime import datetime
from getpass import getpass
from pathlib import Path
import re
import sqlite3

from werkzeug.security import generate_password_hash

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REVISION = '49a01b7c2d30'


def check_database(connection):
    revision = connection.execute('SELECT version_num FROM alembic_version').fetchall()
    if revision != [(REVISION,)]:
        raise ValueError('Expected the verified venue migration. No changes made.')
    if connection.execute('SELECT count(*) FROM administrators').fetchone()[0]:
        raise ValueError('An administrator already exists. Use that login; no account was reset.')


def create_admin(database, name, email, password):
    database = Path(database).resolve()
    if not database.is_file():
        raise ValueError('Existing database not found. No changes made.')
    name, email = name.strip(), email.strip().lower()
    if not name or len(name) > 100:
        raise ValueError('Name must contain 1 to 100 characters.')
    if len(email) > 120 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email):
        raise ValueError('Enter a valid email address, up to 120 characters.')
    if len(password) < 12:
        raise ValueError('Password must contain at least 12 characters.')
    password_hash = generate_password_hash(password)
    with closing(sqlite3.connect(database.as_uri() + '?mode=rw', uri=True)) as connection:
        try:
            # Serialize account checks and insertion against other writers.
            connection.execute('BEGIN IMMEDIATE')
            check_database(connection)
            for table in ('supervisors', 'onboarding_agents', 'administrators'):
                if connection.execute(
                    f'SELECT 1 FROM {table} WHERE lower(trim(email)) = ?', (email,)
                ).fetchone():
                    raise ValueError('That email belongs to an existing account. Choose another email.')
            backup_dir = database.parent / 'backups'
            backup_dir.mkdir(exist_ok=True)
            backup = backup_dir / ('before_admin_login_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f') + '.db')
            # A separate reader captures committed data while the write lock is held.
            with closing(sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)) as source:
                with closing(sqlite3.connect(backup)) as destination:
                    source.backup(destination)
                    if destination.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                        raise ValueError('Backup verification failed. Account was not created.')
            connection.execute(
                'INSERT INTO administrators (name, email, password_hash) VALUES (?, ?, ?)',
                (name, email, password_hash),
            )
            connection.commit()
            return backup
        except Exception:
            connection.rollback()
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    database = PROJECT_ROOT / 'instance' / 'netease_setup_test' / 'task_allocation.db'
    if not database.is_file():
        raise SystemExit('Port-5001 database not found. No changes made.')
    try:
        with closing(sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)) as connection:
            check_database(connection)
        print('Installation:', database.parent)
        if not args.apply:
            print('Ready to create the first administrator. No changes made.')
            return
        name = input('Administrator name: ')
        email = input('Administrator email (different from your supervisor/worker): ')
        password = getpass('Choose a password (12+ characters): ')
        if password != getpass('Confirm password: '):
            raise ValueError('Passwords do not match. No changes made.')
        backup = create_admin(database, name, email, password)
        print('Verified backup:', backup)
        print('Administrator created. Existing accounts and tasks were not changed.')
        print('Sign out, then sign in at http://127.0.0.1:5001/auth/login')
        print('Neon was not accessed.')
    except (ValueError, sqlite3.Error) as exc:
        raise SystemExit(str(exc)) from None


if __name__ == '__main__':
    main()
