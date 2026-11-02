"""Check the independent-worker schema on a disposable SQLite database only."""
from pathlib import Path
import secrets
import sys
import tempfile

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from flask_migrate import upgrade, downgrade
from sqlalchemy import event, inspect, text
from sqlalchemy.engine import URL
from app import create_app
from app.extensions import db

BASE = '56b02e0f5a60'
TARGET = '56c03f1a6b70'
TABLE = 'independent_worker_registrations'


def snapshot(tables):
    inspector = inspect(db.engine)
    quote = db.engine.dialect.identifier_preparer.quote
    return {table: (
        [c['name'] for c in inspector.get_columns(table)],
        sorted([tuple(r) for r in db.session.execute(text('SELECT * FROM ' + quote(table)))], key=repr)
    ) for table in tables}


def verify(folder):
    database = (Path(folder) / 'independent_worker_check.db').resolve()
    if database.exists():
        raise RuntimeError('A new disposable database is required.')
    app = create_app({'TESTING': True, 'SECRET_KEY': secrets.token_hex(32),
        'SQLALCHEMY_DATABASE_URI': URL.create('sqlite', database=str(database)),
        'SQLALCHEMY_ENGINE_OPTIONS': {}})
    app.instance_path = str(folder)
    migrations = str(PROJECT_ROOT / 'migrations')
    with app.app_context():
        def foreign_keys(connection, _):
            connection.execute('PRAGMA foreign_keys=ON')
        event.listen(db.engine, 'connect', foreign_keys)
        try:
            assert Path(db.engine.url.database).resolve() == database
            upgrade(directory=migrations, revision=BASE)
            # All fixture people and activity are confined to this disposable database.
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
            db.session.commit()
            tables = sorted(set(inspect(db.engine).get_table_names()) - {'alembic_version'})
            before = snapshot(tables)
            db.session.remove()
            upgrade(directory=migrations, revision=TARGET)
            assert set(inspect(db.engine).get_table_names()) == set(tables) | {TABLE, 'alembic_version'}
            assert snapshot(tables) == before
            assert db.session.execute(text('SELECT COUNT(*) FROM ' + TABLE)).scalar_one() == 0
            assert db.session.execute(text('SELECT version_num FROM alembic_version')).scalar_one() == TARGET
            print('One empty registration table added; existing workers, mappings and assignments preserved: PASS')
            db.session.remove()
            upgrade(directory=migrations, revision=TARGET)
            assert snapshot(tables) == before
            print('Repeat upgrade preserves existing records: PASS')
            columns = inspect(db.engine).get_columns(TABLE)
            assert {c['name'] for c in columns} == {'agent_id','created_by_admin_id','created_at'}
            assert inspect(db.engine).get_pk_constraint(TABLE)['constrained_columns'] == ['agent_id']
            assert {fk['referred_table'] for fk in inspect(db.engine).get_foreign_keys(TABLE)} == {'onboarding_agents','administrators'}
            db.session.execute(text("INSERT INTO onboarding_agents (id,name,email,password_hash,availability,workload,account_disabled) VALUES (2,'Independent fixture','worker@test.invalid','disabled',0,0,1)"))
            db.session.execute(text('INSERT INTO independent_worker_registrations (agent_id,created_by_admin_id) VALUES (2,1)'))
            db.session.commit()
            assert db.session.execute(text('SELECT created_at FROM ' + TABLE)).scalar_one() is not None
            assert db.session.execute(text('SELECT COUNT(*) FROM worker_source_bindings WHERE agent_id=2')).scalar_one() == 0
            print('Independent registration stored without a dataset binding or model score: PASS')
            db.session.remove()
            print('Testing downgrade protection; the next migration error is expected.', flush=True)
            try:
                downgrade(directory=migrations, revision=BASE)
            except SystemExit as exc:
                assert exc.code == 1
            else:
                raise AssertionError('Downgrade did not preserve registration records.')
            db.session.remove()
            assert db.session.execute(text('SELECT COUNT(*) FROM ' + TABLE)).scalar_one() == 1
            assert db.session.execute(text('SELECT version_num FROM alembic_version')).scalar_one() == TARGET
            print('Downgrade protects independent-worker origin records: PASS')
            # Remove only the disposable fixture to exercise an unused-table rollback.
            db.session.execute(text('DELETE FROM independent_worker_registrations'))
            db.session.execute(text('DELETE FROM onboarding_agents WHERE id=2'))
            db.session.commit()
            db.session.remove()
            downgrade(directory=migrations, revision=BASE)
            assert snapshot(tables) == before
            assert TABLE not in inspect(db.engine).get_table_names()
            assert db.session.execute(text('PRAGMA integrity_check')).scalar_one() == 'ok'
            assert not db.session.execute(text('PRAGMA foreign_key_check')).all()
            print('Unused-table rollback and database integrity: PASS')
        finally:
            db.session.remove()
            db.engine.dispose()


def main():
    parent = PROJECT_ROOT / 'instance'
    parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='independent_worker_schema_', dir=parent) as folder:
        print('Using a new disposable SQLite database.')
        verify(folder)
    print('Temporary database removed. Port 5001 and Neon were not changed.')


if __name__ == '__main__':
    main()
