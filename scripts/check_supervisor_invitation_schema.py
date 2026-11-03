"""Rehearse supervisor invitation storage in a disposable database only."""
from pathlib import Path
from datetime import datetime, timedelta, timezone
import hashlib
import secrets
import sys
import tempfile
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
from flask_migrate import upgrade, downgrade
from sqlalchemy import inspect, text
from sqlalchemy.engine import URL
from app import create_app
from app.extensions import db

BASE = '62a05b3c8d90'
TARGET = '62b06c4d9e01'
TABLE = 'supervisor_setup_invitations'


def snapshot(tables):
    quote = db.engine.dialect.identifier_preparer.quote
    return {name: (tuple(c['name'] for c in inspect(db.engine).get_columns(name)),
        tuple(sorted((tuple(row) for row in db.session.execute(text('SELECT * FROM ' + quote(name)))), key=repr)))
        for name in tables}


def verify(folder):
    database = (Path(folder) / 'invitation_check.db').resolve()
    assert not database.exists()
    app = create_app({'TESTING': True, 'SECRET_KEY': secrets.token_hex(32),
        'SQLALCHEMY_DATABASE_URI': URL.create('sqlite', database=str(database)),
        'SQLALCHEMY_ENGINE_OPTIONS': {}})
    app.instance_path = str(folder)
    with app.app_context():
        migrations = str(PROJECT_ROOT / 'migrations')
        assert Path(db.engine.url.database).resolve() == database
        upgrade(directory=migrations, revision=BASE)
        for sql in (
            "INSERT INTO administrators (id,name,email,password_hash) VALUES (1,'Admin','admin@test.invalid','unchanged')",
            "INSERT INTO supervisors (id,name,email,password_hash,account_disabled) VALUES (1,'Existing','old@test.invalid','unchanged',0)",
            "INSERT INTO supervisors (id,name,email,password_hash,account_disabled) VALUES (2,'Pending','new@test.invalid','!pending-supervisor-setup',1)",
            "INSERT INTO tasks (id,task_type,supervisor_id,status) VALUES (1,'Existing task',1,'Completed')",
        ):
            db.session.execute(text(sql))
        db.session.commit()
        tables = sorted(set(inspect(db.engine).get_table_names()) - {'alembic_version'})
        before = snapshot(tables)
        db.session.remove()
        upgrade(directory=migrations, revision=TARGET)
        assert snapshot(tables) == before
        assert set(inspect(db.engine).get_table_names()) == set(tables) | {'alembic_version',TABLE}
        assert db.session.execute(text('SELECT version_num FROM alembic_version')).scalar_one() == TARGET
        print('Existing accounts, credentials and tasks preserved: PASS')
        db.session.remove()
        upgrade(directory=migrations, revision=TARGET)
        assert snapshot(tables) == before
        print('Repeated upgrade preserves records: PASS')
        token = secrets.token_urlsafe(32)
        digest = hashlib.sha256(token.encode('ascii')).hexdigest()
        now = datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)
        db.session.execute(text('INSERT INTO supervisor_setup_invitations (supervisor_id,token_hash,created_by_admin_id,issued_at,expires_at) VALUES (2,:digest,1,:now,:expiry)'),
            {'digest':digest,'now':now,'expiry':now+timedelta(hours=24)})
        db.session.commit()
        row = db.session.execute(text('SELECT * FROM supervisor_setup_invitations')).one()
        assert digest in row and token not in row and row[-1] is None
        assert {f['referred_table'] for f in inspect(db.engine).get_foreign_keys(TABLE)} == {'supervisors','administrators'}
        print('Hashed, expiring invitation storage and foreign keys: PASS')
        db.session.remove()
        try:
            downgrade(directory=migrations, revision=BASE)
        except (RuntimeError, SystemExit):
            pass
        else:
            raise AssertionError('Downgrade discarded an invitation.')
        db.session.remove()
        assert db.session.execute(text('SELECT COUNT(*) FROM supervisor_setup_invitations')).scalar_one() == 1
        print('Downgrade protects invitation records: PASS')
        db.session.execute(text('DELETE FROM supervisor_setup_invitations'))
        db.session.commit()
        db.session.remove()
        downgrade(directory=migrations, revision=BASE)
        assert snapshot(tables) == before
        assert db.session.execute(text('PRAGMA integrity_check')).scalar_one() == 'ok'
        assert not db.session.execute(text('PRAGMA foreign_key_check')).all()
        db.session.remove()
        db.engine.dispose()
        print('Unused-table rollback and integrity: PASS')


def main():
    parent = PROJECT_ROOT / 'instance'
    parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='supervisor_invitation_schema_', dir=parent) as folder:
        print('Using a new disposable SQLite database.')
        verify(folder)
    print('Temporary database removed. Port 5001 and Neon were not changed.')


if __name__ == '__main__':
    main()
