"""Rehearse Google identity storage in a disposable SQLite database."""

from datetime import datetime, timezone
from pathlib import Path
import secrets
import sys
import tempfile

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from flask_migrate import downgrade, upgrade
from sqlalchemy import inspect, text
from sqlalchemy.engine import URL

from app import create_app
from app.extensions import db
from app.models import GoogleIdentity

BASE = '66b08e6f1a23'
TARGET = '66c09f702b34'
TABLE = 'google_identities'


def snapshot(tables):
    quote = db.engine.dialect.identifier_preparer.quote
    return {
        name: (
            tuple(column['name'] for column in inspect(db.engine).get_columns(name)),
            tuple(sorted(
                (tuple(row) for row in db.session.execute(text(f'SELECT * FROM {quote(name)}'))),
                key=repr,
            )),
        )
        for name in tables
    }


def verify(folder):
    database = (Path(folder) / 'google_identity_check.db').resolve()
    assert not database.exists()
    app = create_app({
        'TESTING': True,
        'SECRET_KEY': secrets.token_hex(32),
        'SQLALCHEMY_DATABASE_URI': URL.create('sqlite', database=str(database)),
        'SQLALCHEMY_ENGINE_OPTIONS': {},
    })
    app.instance_path = str(folder)
    migrations = str(PROJECT_ROOT / 'migrations')

    with app.app_context():
        assert Path(db.engine.url.database).resolve() == database
        upgrade(directory=migrations, revision=BASE)
        for sql in (
            "INSERT INTO administrators (id,name,email,password_hash) VALUES (1,'Admin','admin@test.invalid','original')",
            "INSERT INTO supervisors (id,name,email,password_hash,account_disabled) VALUES (1,'Supervisor','supervisor@test.invalid','original',0)",
            "INSERT INTO onboarding_agents (id,name,email,password_hash,availability,account_disabled,workload) VALUES (1,'Worker','worker@test.invalid','original',1,0,0)",
            "INSERT INTO independent_worker_registrations (agent_id,created_by_admin_id) VALUES (1,1)",
            "INSERT INTO tasks (id,task_type,supervisor_id,status) VALUES (1,'Existing task',1,'Pending')",
        ):
            db.session.execute(text(sql))
        db.session.commit()
        old_tables = sorted(set(inspect(db.engine).get_table_names()) - {'alembic_version'})
        before = snapshot(old_tables)
        db.session.remove()

        upgrade(directory=migrations, revision=TARGET)
        assert snapshot(old_tables) == before
        assert set(inspect(db.engine).get_table_names()) == set(old_tables) | {'alembic_version', TABLE}
        assert db.session.execute(text('SELECT version_num FROM alembic_version')).scalar_one() == TARGET
        assert set(GoogleIdentity.__table__.columns.keys()) == {
            column['name'] for column in inspect(db.engine).get_columns(TABLE)
        }
        assert not db.session.execute(text(f'SELECT * FROM {TABLE}')).all()
        print('Existing accounts, passwords, tasks and assignments preserved: PASS')
        print('No Google sign-in links created automatically: PASS')
        db.session.remove()
        upgrade(directory=migrations, revision=TARGET)
        assert snapshot(old_tables) == before
        print('Repeated upgrade preserves records: PASS')

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        db.session.add(GoogleIdentity(
            subject='sample-google-subject-123', supervisor_id=1,
            linked_at=now, last_login_at=now,
        ))
        db.session.commit()
        assert db.session.execute(text(f'SELECT COUNT(*) FROM {TABLE}')).scalar_one() == 1
        assert {fk['referred_table'] for fk in inspect(db.engine).get_foreign_keys(TABLE)} == {
            'administrators', 'onboarding_agents', 'supervisors'
        }
        print('A Google identity can be linked to one existing account: PASS')

        db.session.remove()
        try:
            downgrade(directory=migrations, revision=BASE)
        except (RuntimeError, SystemExit):
            pass
        else:
            raise AssertionError('Downgrade discarded a linked identity.')
        db.session.remove()
        assert db.session.execute(text(f'SELECT COUNT(*) FROM {TABLE}')).scalar_one() == 1
        print('Downgrade protects linked identities: PASS')
        db.session.execute(text(f'DELETE FROM {TABLE}'))
        db.session.commit()
        db.session.remove()
        downgrade(directory=migrations, revision=BASE)
        assert snapshot(old_tables) == before
        assert db.session.execute(text('PRAGMA integrity_check')).scalar_one() == 'ok'
        assert not db.session.execute(text('PRAGMA foreign_key_check')).all()
        db.session.remove()
        db.engine.dispose()
        print('Unused-table rollback and database integrity: PASS')


def main():
    parent = PROJECT_ROOT / 'instance'
    parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='google_identity_schema_', dir=parent) as folder:
        print('Using a new disposable SQLite database.')
        verify(folder)
    print('Temporary database removed. Port 5001 and Neon were not changed.')
    print('This checks storage only; Google sign-in will be added next.')


if __name__ == '__main__':
    main()
