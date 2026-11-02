"""Check invitation storage in a new disposable SQLite database only."""
from pathlib import Path
from datetime import datetime, timedelta, timezone
import hashlib
import secrets
import sys
import tempfile

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
from flask_migrate import upgrade, downgrade
from sqlalchemy import event, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.engine import URL
from app import create_app
from app.extensions import db

BASE = '56c03f1a6b70'
TARGET = '56d04a2b7c80'
TABLE = 'worker_setup_invitations'


def snapshot(tables):
    inspector = inspect(db.engine)
    quote = db.engine.dialect.identifier_preparer.quote
    return {table: ([c['name'] for c in inspector.get_columns(table)],
        sorted([tuple(row) for row in db.session.execute(text('SELECT * FROM ' + quote(table)))], key=repr))
        for table in tables}


def verify(folder):
    database = (Path(folder) / 'worker_setup_check.db').resolve()
    if database.exists():
        raise RuntimeError('A new disposable database is required.')
    app = create_app({'TESTING': True, 'SECRET_KEY': secrets.token_hex(32),
        'SQLALCHEMY_DATABASE_URI': URL.create('sqlite', database=str(database)),
        'SQLALCHEMY_ENGINE_OPTIONS': {}})
    app.instance_path = str(folder)
    migrations = str(PROJECT_ROOT / 'migrations')
    with app.app_context():
        def enable_fk(connection, _):
            connection.execute('PRAGMA foreign_keys=ON')
        event.listen(db.engine, 'connect', enable_fk)
        try:
            assert Path(db.engine.url.database).resolve() == database
            upgrade(directory=migrations, revision=BASE)
            fixtures = [
                "INSERT INTO administrators (id,name,email,password_hash) VALUES (1,'Fixture admin','admin@test.invalid','disabled')",
                "INSERT INTO supervisors (id,name,email,password_hash) VALUES (1,'Fixture supervisor','supervisor@test.invalid','disabled')",
                "INSERT INTO onboarding_agents (id,name,email,password_hash,availability,workload) VALUES (1,'Dataset fixture','netease-57@demo.invalid','disabled',1,1)",
                "INSERT INTO worker_source_bindings (agent_id,source_worker_id) VALUES (1,'57')",
                "INSERT INTO skills (id,name) VALUES (1,'NetEase capability 53')",
                "INSERT INTO agent_skills (agent_id,skill_id,proficiency_level) VALUES (1,1,'Observed participation')",
                "INSERT INTO tasks (id,task_type,supervisor_id,status) VALUES (1,'Fixture task',1,'In progress')",
                "INSERT INTO task_assignments (task_id,agent_id,supervisor_id,status,started_at) VALUES (1,1,1,'In progress','2026-10-30 07:00:00')",
            ]
            for sql in fixtures:
                db.session.execute(text(sql))
            for agent_id in (2,3):
                db.session.execute(text("INSERT INTO onboarding_agents (id,name,email,password_hash,account_disabled,availability,workload) VALUES (:id,'Independent fixture',:email,'!pending-independent-worker-setup',1,0,0)"),
                    {'id': agent_id, 'email': f'fixture{agent_id}@example.com'})
                db.session.execute(text('INSERT INTO independent_worker_registrations (agent_id,created_by_admin_id) VALUES (:id,1)'), {'id':agent_id})
            db.session.commit()
            tables = sorted(set(inspect(db.engine).get_table_names()) - {'alembic_version'})
            before = snapshot(tables)
            db.session.remove()
            upgrade(directory=migrations, revision=TARGET)
            assert set(inspect(db.engine).get_table_names()) == set(tables) | {TABLE, 'alembic_version'}
            assert snapshot(tables) == before
            assert db.session.execute(text('SELECT COUNT(*) FROM ' + TABLE)).scalar_one() == 0
            assert db.session.execute(text('SELECT version_num FROM alembic_version')).scalar_one() == TARGET
            print('One empty invitation table added; existing workers, passwords, registrations and bindings preserved: PASS')
            db.session.remove()
            upgrade(directory=migrations, revision=TARGET)
            assert snapshot(tables) == before
            print('Repeat upgrade preserves existing records: PASS')
            assert {c['name'] for c in inspect(db.engine).get_columns(TABLE)} == {
                'agent_id','token_hash','created_by_admin_id','issued_at','expires_at','consumed_at'}
            assert inspect(db.engine).get_pk_constraint(TABLE)['constrained_columns'] == ['agent_id']
            raw_token = secrets.token_urlsafe(32)
            digest = hashlib.sha256(raw_token.encode()).hexdigest()
            issued = datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)
            params = {'id':2, 'hash':digest, 'admin':1, 'issued':issued, 'expires':issued+timedelta(hours=24)}
            insert = text('INSERT INTO worker_setup_invitations (agent_id,token_hash,created_by_admin_id,issued_at,expires_at) VALUES (:id,:hash,:admin,:issued,:expires)')
            db.session.execute(insert, params)
            db.session.commit()
            row = db.session.execute(text('SELECT * FROM ' + TABLE)).one()
            assert digest in row and raw_token not in row and row[-1] is None
            print('Token hash, expiry and unused state can be stored without changing credentials: PASS')
            # One current invitation per worker, unique token hashes, valid expiry,
            # and foreign keys limited to explicitly registered independent workers.
            for bad in (
                {**params,'hash':'b'*64},
                {**params,'id':3},
                {**params,'id':1,'hash':'c'*64},
                {**params,'id':3,'hash':'short'},
                {**params,'id':3,'hash':'d'*64,'expires':issued},
                {**params,'id':3,'hash':'e'*64,'admin':9999},
            ):
                try:
                    db.session.execute(insert,bad)
                    db.session.commit()
                except IntegrityError:
                    db.session.rollback()
                else:
                    raise AssertionError('Invalid invitation was accepted.')
            assert snapshot(tables) == before
            print('Unique invitation, independent-worker identity, issuer and expiry constraints: PASS')
            db.session.execute(text('UPDATE worker_setup_invitations SET consumed_at=:used WHERE agent_id=2'), {'used':issued+timedelta(minutes=1)})
            db.session.commit()
            assert db.session.execute(text('SELECT consumed_at FROM ' + TABLE)).scalar_one() is not None
            db.session.remove()
            print('Testing downgrade protection; the next migration error is expected.',flush=True)
            try:
                downgrade(directory=migrations, revision=BASE)
            except SystemExit as exc:
                assert exc.code == 1
            else:
                raise AssertionError('Downgrade discarded invitation records.')
            db.session.remove()
            assert db.session.execute(text('SELECT COUNT(*) FROM ' + TABLE)).scalar_one() == 1
            assert db.session.execute(text('SELECT version_num FROM alembic_version')).scalar_one() == TARGET
            print('Used invitation records are preserved by downgrade protection: PASS')
            # Remove only disposable invitation data to check the unused-table rollback.
            db.session.execute(text('DELETE FROM worker_setup_invitations'))
            db.session.commit()
            db.session.remove()
            downgrade(directory=migrations, revision=BASE)
            assert snapshot(tables) == before
            assert TABLE not in inspect(db.engine).get_table_names()
            assert db.session.execute(text('PRAGMA integrity_check')).scalar_one() == 'ok'
            assert not db.session.execute(text('PRAGMA foreign_key_check')).all()
            print('Unused-table rollback, existing records and database integrity: PASS')
        finally:
            db.session.remove()
            db.engine.dispose()


def main():
    parent = PROJECT_ROOT / 'instance'
    parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='worker_setup_schema_', dir=parent) as folder:
        print('Using a new disposable SQLite database.')
        verify(folder)
    print('Temporary database removed. Port 5001 and Neon were not changed.')
    print('This checks storage only; invitation issuance and password setup are not installed yet.')


if __name__ == '__main__':
    main()
