"""Rehearse the email-verification migration in a disposable SQLite database."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
import hashlib
import secrets
import sys
import tempfile

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from flask_migrate import downgrade, upgrade
from sqlalchemy import inspect, text
from sqlalchemy.engine import URL
from werkzeug.security import generate_password_hash, check_password_hash

from app import create_app
from app.extensions import db
from app.models import SetupEmailVerification

BASE = '62b06c4d9e01'
TARGET = '66a07d5e0f12'
TABLE = 'setup_email_verifications'


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
    database = (Path(folder) / 'email_verification_check.db').resolve()
    assert not database.exists()
    app = create_app({
        'TESTING': True,
        'SECRET_KEY': secrets.token_hex(32),
        'SQLALCHEMY_DATABASE_URI': URL.create('sqlite', database=str(database)),
        'SQLALCHEMY_ENGINE_OPTIONS': {},
    })
    app.instance_path = str(folder)

    with app.app_context():
        migrations = str(PROJECT_ROOT / 'migrations')
        assert Path(db.engine.url.database).resolve() == database
        upgrade(directory=migrations, revision=BASE)
        for sql in (
            "INSERT INTO administrators (id,name,email,password_hash) VALUES (1,'Admin','admin@test.invalid','unchanged')",
            "INSERT INTO supervisors (id,name,email,password_hash,account_disabled) VALUES (1,'Existing','old@test.invalid','unchanged',0)",
            "INSERT INTO supervisors (id,name,email,password_hash,account_disabled) VALUES (2,'Pending','new@test.invalid','!pending-supervisor-setup',1)",
            "INSERT INTO onboarding_agents (id,name,email,password_hash,availability,account_disabled,workload) VALUES (1,'Worker','worker@test.invalid','!pending-independent-worker-setup',0,0,0)",
            "INSERT INTO independent_worker_registrations (agent_id,created_by_admin_id) VALUES (1,1)",
            "INSERT INTO tasks (id,task_type,supervisor_id,status) VALUES (1,'Existing task',1,'Completed')",
        ):
            db.session.execute(text(sql))
        db.session.commit()
        tables = sorted(set(inspect(db.engine).get_table_names()) - {'alembic_version'})
        before = snapshot(tables)
        db.session.remove()

        upgrade(directory=migrations, revision=TARGET)
        assert snapshot(tables) == before
        assert set(inspect(db.engine).get_table_names()) == set(tables) | {'alembic_version', TABLE}
        assert db.session.execute(text('SELECT version_num FROM alembic_version')).scalar_one() == TARGET
        assert set(SetupEmailVerification.__table__.columns.keys()) == {
            column['name'] for column in inspect(db.engine).get_columns(TABLE)
        }
        print('Existing accounts, passwords, tasks and assignments preserved: PASS')
        db.session.remove()
        upgrade(directory=migrations, revision=TARGET)
        assert snapshot(tables) == before
        print('Repeated upgrade preserves records: PASS')

        now = datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)
        invitation_hash = hashlib.sha256(secrets.token_bytes(32)).hexdigest()
        code = f'{secrets.randbelow(1_000_000):06d}'
        code_hash = generate_password_hash(code)
        db.session.add(SetupEmailVerification(
            worker_id=1,
            invitation_token_hash=invitation_hash,
            code_hash=code_hash,
            issued_at=now,
            expires_at=now + timedelta(minutes=10),
            last_sent_at=now,
        ))
        db.session.add(SetupEmailVerification(
            supervisor_id=2,
            invitation_token_hash=hashlib.sha256(secrets.token_bytes(32)).hexdigest(),
            code_hash=generate_password_hash('987654'),
            issued_at=now,
            expires_at=now + timedelta(minutes=10),
            last_sent_at=now,
        ))
        db.session.commit()
        rows = db.session.execute(text(f'SELECT * FROM {TABLE} ORDER BY id')).all()
        assert len(rows) == 2
        assert code not in repr(rows)
        assert check_password_hash(db.session.get(SetupEmailVerification, 1).code_hash, code)
        assert {fk['referred_table'] for fk in inspect(db.engine).get_foreign_keys(TABLE)} == {
            'independent_worker_registrations', 'supervisors'
        }
        print('Separate worker and supervisor challenges store hashed codes: PASS')

        db.session.remove()
        try:
            downgrade(directory=migrations, revision=BASE)
        except (RuntimeError, SystemExit):
            pass
        else:
            raise AssertionError('Downgrade discarded active verification challenges.')
        db.session.remove()
        assert db.session.execute(text(f'SELECT COUNT(*) FROM {TABLE}')).scalar_one() == 2
        print('Downgrade protects verification challenges: PASS')
        db.session.execute(text(f'DELETE FROM {TABLE}'))
        db.session.commit()
        db.session.remove()
        downgrade(directory=migrations, revision=BASE)
        assert snapshot(tables) == before
        assert db.session.execute(text('PRAGMA integrity_check')).scalar_one() == 'ok'
        assert not db.session.execute(text('PRAGMA foreign_key_check')).all()
        db.session.remove()
        db.engine.dispose()
        print('Unused-table rollback and database integrity: PASS')


def main():
    parent = PROJECT_ROOT / 'instance'
    parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='setup_email_schema_', dir=parent) as folder:
        print('Using a new disposable SQLite database.')
        verify(folder)
    print('Temporary database removed. Port 5001 and Neon were not changed.')


if __name__ == '__main__':
    main()
