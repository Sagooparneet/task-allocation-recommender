"""Check issue 54 migration only in a brand-new disposable SQLite database."""
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

BASE = '49a01b7c2d30'
TARGET = '54b01c8d3e40'


def verify(folder):
    database = Path(folder) / 'progress_check.db'
    if database.exists():
        raise RuntimeError('A fresh database path is required.')
    app = create_app({
        'TESTING': True, 'SECRET_KEY': secrets.token_hex(32),
        'SQLALCHEMY_DATABASE_URI': URL.create('sqlite', database=str(database)),
        'SQLALCHEMY_ENGINE_OPTIONS': {},
    })
    app.instance_path = str(folder)
    migrations = str(PROJECT_ROOT / 'migrations')
    with app.app_context():
        def foreign_keys(connection, _):
            connection.execute('PRAGMA foreign_keys=ON')
        event.listen(db.engine, 'connect', foreign_keys)
        try:
            if Path(db.engine.url.database).resolve() != database.resolve():
                raise RuntimeError('Disposable database selection failed.')
            upgrade(directory=migrations, revision=BASE)
            db.session.execute(text("INSERT INTO supervisors (id,name,email,password_hash) VALUES (1,'Test','test@demo.invalid','disabled')"))
            db.session.execute(text("INSERT INTO onboarding_agents (id,name,email,password_hash,workload) VALUES (1,'Test worker','worker@demo.invalid','disabled',1)"))
            for task_id, status in ((1, 'Assigned'), (2, 'Completed')):
                params = {'id': task_id, 'status': status}
                db.session.execute(text("INSERT INTO tasks (id,task_type,supervisor_id,status) VALUES (:id,'Legacy task',1,:status)"), params)
                db.session.execute(text("INSERT INTO task_assignments (id,task_id,agent_id,supervisor_id,status,assigned_at) VALUES (:id,:id,1,1,:status,'2026-01-01 09:00:00')"), params)
            db.session.commit()
            columns = [c['name'] for c in inspect(db.engine).get_columns('task_assignments')]
            projection = ', '.join(columns)
            before = db.session.execute(text(f'SELECT {projection} FROM task_assignments ORDER BY id')).all()
            tasks = db.session.execute(text('SELECT * FROM tasks ORDER BY id')).all()
            db.session.remove()
            upgrade(directory=migrations, revision=TARGET)
            assert db.session.execute(text('SELECT version_num FROM alembic_version')).scalar_one() == TARGET
            assert db.session.execute(text(f'SELECT {projection} FROM task_assignments ORDER BY id')).all() == before
            assert db.session.execute(text('SELECT * FROM tasks ORDER BY id')).all() == tasks
            assert db.session.execute(text('SELECT started_at, completed_at FROM task_assignments ORDER BY id')).all() == [(None, None), (None, None)]
            assert db.session.execute(text('SELECT workload FROM onboarding_agents WHERE id=1')).scalar_one() == 1
            print('Legacy assignments, task statuses and workload preserved: PASS')
            print('Unknown historical start/completion times remain empty: PASS')
            db.session.remove()
            upgrade(directory=migrations, revision=TARGET)
            assert db.session.execute(text('SELECT COUNT(*) FROM task_assignments')).scalar_one() == 2
            print('Repeated upgrade leaves records intact: PASS')
            db.session.execute(text("UPDATE task_assignments SET started_at='2026-01-02 08:00:00', completed_at='2026-01-02 09:00:00' WHERE id=1"))
            db.session.commit()
            assert all(db.session.execute(text('SELECT started_at, completed_at FROM task_assignments WHERE id=1')).one())
            db.session.remove()
            print('Testing refusal to remove recorded timestamps; the next migration error is expected.', flush=True)
            try:
                downgrade(directory=migrations, revision=BASE)
            except SystemExit as exc:
                # Flask-Migrate converts migration RuntimeError into exit code 1.
                assert exc.code == 1
            else:
                raise AssertionError('Downgrade should protect recorded timestamps.')
            db.session.remove()
            assert db.session.execute(text('SELECT version_num FROM alembic_version')).scalar_one() == TARGET
            assert all(db.session.execute(text('SELECT started_at, completed_at FROM task_assignments WHERE id=1')).one())
            print('Timestamp storage and downgrade data-loss guard: PASS')
            # Only these disposable test timestamps are cleared to test rollback.
            db.session.execute(text('UPDATE task_assignments SET started_at=NULL, completed_at=NULL'))
            db.session.commit()
            db.session.remove()
            downgrade(directory=migrations, revision=BASE)
            assert db.session.execute(text(f'SELECT {projection} FROM task_assignments ORDER BY id')).all() == before
            assert db.session.execute(text('SELECT * FROM tasks ORDER BY id')).all() == tasks
            assert 'started_at' not in {c['name'] for c in inspect(db.engine).get_columns('task_assignments')}
            print('Rollback of unused columns preserves legacy records: PASS')
        finally:
            db.session.remove()
            db.engine.dispose()


def main():
    parent = PROJECT_ROOT / 'instance'
    parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='progress_schema_check_', dir=parent) as folder:
        print('Using a new disposable SQLite database.')
        verify(folder)
    print('Temporary database removed. Port 5001 and Neon were not changed.')


if __name__ == '__main__':
    main()
