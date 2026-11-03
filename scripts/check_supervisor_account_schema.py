"""Rehearse supervisor account-status migration in a disposable SQLite database."""
from pathlib import Path
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

BASE = '56d04a2b7c80'
TARGET = '62a05b3c8d90'


def snapshot(tables):
    quote = db.engine.dialect.identifier_preparer.quote
    return {name: (tuple(c['name'] for c in inspect(db.engine).get_columns(name)),
                   tuple(sorted((tuple(row) for row in db.session.execute(
                       text('SELECT * FROM ' + quote(name)))), key=repr)))
            for name in tables}


def verify(folder):
    database = (Path(folder) / 'supervisor_schema_check.db').resolve()
    assert not database.exists()
    app = create_app({'TESTING': True, 'SECRET_KEY': secrets.token_hex(32),
        'SQLALCHEMY_DATABASE_URI': URL.create('sqlite', database=str(database)),
        'SQLALCHEMY_ENGINE_OPTIONS': {}})
    app.instance_path = str(folder)
    migrations = str(PROJECT_ROOT / 'migrations')
    with app.app_context():
        assert Path(db.engine.url.database).resolve() == database
        upgrade(directory=migrations, revision=BASE)
        for sql in (
            "INSERT INTO supervisors (id,name,email,password_hash) VALUES (1,'Existing supervisor','supervisor@test.invalid','unchanged-hash')",
            "INSERT INTO onboarding_agents (id,name,email,password_hash) VALUES (1,'Fixture worker','worker@test.invalid','unchanged-hash')",
            "INSERT INTO tasks (id,task_type,supervisor_id,status) VALUES (1,'Existing task',1,'Assigned')",
            "INSERT INTO task_assignments (id,task_id,agent_id,supervisor_id,status) VALUES (1,1,1,1,'Assigned')",
        ):
            db.session.execute(text(sql))
        db.session.commit()
        tables = sorted(set(inspect(db.engine).get_table_names()) - {'alembic_version'})
        before = snapshot(tables)
        db.session.remove()
        upgrade(directory=migrations, revision=TARGET)
        after = snapshot(tables)
        assert set(after) == set(before)
        assert all(after[name] == before[name] for name in tables if name != 'supervisors')
        assert after['supervisors'][0] == before['supervisors'][0] + ('account_disabled',)
        assert [row[:-1] for row in after['supervisors'][1]] == list(before['supervisors'][1])
        assert [row[-1] for row in after['supervisors'][1]] == [0]
        assert db.session.execute(text('SELECT version_num FROM alembic_version')).scalar_one() == TARGET
        print('Existing supervisor access, password, tasks and assignments preserved: PASS')
        db.session.remove()
        upgrade(directory=migrations, revision=TARGET)
        assert snapshot(tables) == after
        print('Repeated upgrade preserves records: PASS')
        db.session.execute(text('UPDATE supervisors SET account_disabled=1 WHERE id=1'))
        db.session.commit()
        db.session.remove()
        try:
            downgrade(directory=migrations, revision=BASE)
        except (RuntimeError, SystemExit):
            pass
        else:
            raise AssertionError('Downgrade removed a disabled account.')
        db.session.remove()
        assert db.session.execute(text('SELECT account_disabled FROM supervisors')).scalar_one() == 1
        print('Downgrade protects account restrictions: PASS')
        db.session.execute(text('UPDATE supervisors SET account_disabled=0 WHERE id=1'))
        db.session.commit()
        db.session.remove()
        downgrade(directory=migrations, revision=BASE)
        assert snapshot(tables) == before
        assert db.session.execute(text('PRAGMA integrity_check')).scalar_one() == 'ok'
        assert not db.session.execute(text('PRAGMA foreign_key_check')).all()
        print('Unused-column rollback and database integrity: PASS')
        db.session.remove()
        db.engine.dispose()


def main():
    parent = PROJECT_ROOT / 'instance'
    parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='supervisor_account_schema_', dir=parent) as folder:
        print('Using a new disposable SQLite database.')
        verify(folder)
    print('Temporary database removed. Port 5001 and Neon were not changed.')


if __name__ == '__main__':
    main()
