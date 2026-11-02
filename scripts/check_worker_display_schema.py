"""Verify the display-name migration using a new disposable SQLite database only."""
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

BASE = '54b01c8d3e40'
TARGET = '56a01d9e4f50'


def snapshot(columns=None):
    inspector = inspect(db.engine)
    tables = sorted(set(inspector.get_table_names()) - {'alembic_version'})
    if columns is not None and set(tables) != set(columns):
        raise AssertionError('Application tables changed unexpectedly.')
    columns = columns or {table: [c['name'] for c in inspector.get_columns(table)] for table in tables}
    quote = db.engine.dialect.identifier_preparer.quote
    rows = {table: sorted([tuple(row) for row in db.session.execute(text(
        'SELECT ' + ','.join(quote(c) for c in columns[table]) + ' FROM ' + quote(table)
    ))], key=repr) for table in tables}
    return columns, rows


def verify(folder):
    database = (Path(folder) / 'worker_display_check.db').resolve()
    if database.exists():
        raise RuntimeError('A new disposable database path is required.')
    app = create_app({'TESTING': True, 'SECRET_KEY': secrets.token_hex(32),
        'SQLALCHEMY_DATABASE_URI': URL.create('sqlite', database=str(database)),
        'SQLALCHEMY_ENGINE_OPTIONS': {}})
    app.instance_path = str(folder)
    migrations = str(PROJECT_ROOT / 'migrations')
    with app.app_context():
        def enable_foreign_keys(connection, _):
            connection.execute('PRAGMA foreign_keys=ON')
        event.listen(db.engine, 'connect', enable_foreign_keys)
        try:
            assert Path(db.engine.url.database).resolve() == database
            upgrade(directory=migrations, revision=BASE)
            # Fictional fixtures exist only inside this temporary database.
            for sql in (
                "INSERT INTO supervisors (id,name,email,password_hash) VALUES (1,'Test supervisor','supervisor@test.invalid','disabled')",
                "INSERT INTO onboarding_agents (id,name,email,password_hash,availability,workload,performance_score) VALUES (1,'NetEase worker 57','netease-57@demo.invalid','disabled',1,1,0)",
                "INSERT INTO worker_source_bindings (agent_id,source_worker_id) VALUES (1,'57')",
                "INSERT INTO skills (id,name) VALUES (1,'NetEase capability 53')",
                "INSERT INTO agent_skills (id,agent_id,skill_id,proficiency_level) VALUES (1,1,1,'Observed participation')",
                "INSERT INTO tasks (id,task_type,supervisor_id,status) VALUES (1,'Fixture task',1,'In progress')",
                "INSERT INTO task_assignments (id,task_id,agent_id,supervisor_id,status,started_at) VALUES (1,1,1,1,'In progress','2026-10-30 07:00:00')",
            ):
                db.session.execute(text(sql))
            db.session.commit()
            columns, before = snapshot()
            db.session.remove()
            upgrade(directory=migrations, revision=TARGET)
            assert snapshot(columns)[1] == before
            assert db.session.execute(text('SELECT profile_display_name FROM onboarding_agents')).all() == [(None,)]
            expected = dict(columns)
            expected['onboarding_agents'] = columns['onboarding_agents'] + ['profile_display_name']
            assert snapshot()[0] == expected
            assert db.session.execute(text('SELECT version_num FROM alembic_version')).scalar_one() == TARGET
            print('One optional display-name column added: PASS')
            print('Original identity, email, bindings, services, workload and task history preserved: PASS')
            db.session.remove()
            upgrade(directory=migrations, revision=TARGET)
            assert snapshot(columns)[1] == before
            print('Repeat upgrade preserves existing records: PASS')
            db.session.execute(text("UPDATE onboarding_agents SET profile_display_name='Test display name' WHERE id=1"))
            db.session.commit()
            assert snapshot(columns)[1] == before
            db.session.remove()
            print('Testing protection against removing edited names; the next migration error is expected.', flush=True)
            try:
                downgrade(directory=migrations, revision=BASE)
            except SystemExit as exc:
                assert exc.code == 1
            else:
                raise AssertionError('Downgrade did not protect the edited name.')
            db.session.remove()
            assert db.session.execute(text('SELECT profile_display_name FROM onboarding_agents')).scalar_one() == 'Test display name'
            assert db.session.execute(text('SELECT version_num FROM alembic_version')).scalar_one() == TARGET
            print('Edited-name storage and downgrade protection: PASS')
            # Clear only this fictional test value to verify unused-column rollback.
            db.session.execute(text('UPDATE onboarding_agents SET profile_display_name=NULL'))
            db.session.commit()
            db.session.remove()
            downgrade(directory=migrations, revision=BASE)
            assert snapshot() == (columns, before)
            assert db.session.execute(text('PRAGMA integrity_check')).scalar_one() == 'ok'
            assert not db.session.execute(text('PRAGMA foreign_key_check')).all()
            print('Unused-column rollback, database integrity and foreign keys: PASS')
        finally:
            db.session.remove()
            db.engine.dispose()


def main():
    parent = PROJECT_ROOT / 'instance'
    parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='worker_display_schema_', dir=parent) as folder:
        print('Using a new disposable SQLite database.')
        verify(folder)
    print('Temporary database removed. Port 5001 and Neon were not changed.')


if __name__ == '__main__':
    main()
