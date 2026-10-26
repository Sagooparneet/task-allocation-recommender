"""Exercise venue migrations only in a disposable SQLite database."""
import secrets
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import event, inspect, text
from sqlalchemy.engine import URL
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from flask_migrate import upgrade, downgrade
from app import create_app
from app.extensions import db
from app.models import WorkVenue, TaskVenueDetails, Task
from app.services.initial_work_venues import add_initial_venues

BASE_REVISION = '4baace48147a'
VENUE_REVISION = '49a01b7c2d30'


def verify_in_temporary_directory(folder):
    database = Path(folder) / 'venue_check.db'
    if database.exists():
        raise RuntimeError('The check requires a brand-new database path.')
    app = create_app({
        'TESTING': True,
        'SECRET_KEY': secrets.token_hex(32),
        'SQLALCHEMY_DATABASE_URI': URL.create('sqlite', database=str(database)),
        'SQLALCHEMY_ENGINE_OPTIONS': {},
    })
    app.instance_path = str(folder)
    migrations = str(PROJECT_ROOT / 'migrations')
    with app.app_context():
        def enable_foreign_keys(connection, _):
            connection.execute('PRAGMA foreign_keys=ON')
        event.listen(db.engine, 'connect', enable_foreign_keys)
        try:
            if Path(db.engine.url.database).resolve() != database.resolve():
                raise RuntimeError('Isolated database selection failed.')
            upgrade(directory=migrations, revision=BASE_REVISION)
            db.session.execute(text("INSERT INTO supervisors (id,name,email,password_hash) VALUES (1,'Schema test','schema-test@demo.invalid','disabled')"))
            db.session.execute(text("INSERT INTO tasks (id,task_type,location,priority,status,supervisor_id) VALUES (1,'Legacy city-only task','Nairobi','Medium','Pending',1)"))
            db.session.commit()
            before = tuple(db.session.execute(text('SELECT * FROM tasks WHERE id=1')).one())
            db.session.remove()
            upgrade(directory=migrations, revision=VENUE_REVISION)
            after = tuple(db.session.execute(text('SELECT * FROM tasks WHERE id=1')).one())
            assert after == before, 'Legacy task changed'
            assert TaskVenueDetails.query.count() == 0
            assert add_initial_venues(db.session) == 5
            db.session.commit()
            assert add_initial_venues(db.session) == 0
            db.session.commit()
            assert WorkVenue.query.count() == 5
            print('Migration and unchanged legacy task: PASS')
            print('Five initial venues and repeat-safe setup: PASS')

            venue = WorkVenue.query.filter_by(seed_key='kicc-nairobi').one()
            original_address = venue.address
            snapshot = TaskVenueDetails(task_id=1, venue_id=venue.id, city=venue.city,
                venue_name=venue.name, address=venue.address, reporting_point='Schema test reporting point')
            db.session.add(snapshot)
            db.session.commit()
            venue.address = 'Changed address for isolated schema test'
            venue.is_active = False
            db.session.commit()
            assert add_initial_venues(db.session) == 0
            db.session.commit()
            db.session.expire_all()
            assert db.session.get(TaskVenueDetails, 1).address == original_address
            assert not WorkVenue.query.filter_by(seed_key='kicc-nairobi').one().is_active
            db.session.add(WorkVenue(city='Nairobi', name='Isolated second venue', address='Test address'))
            db.session.commit()
            assert WorkVenue.query.filter_by(city='Nairobi').count() == 2
            print('Historical location preserved after venue edits: PASS')
            print('Multiple venues per city: PASS')
            with db.engine.connect() as connection:
                changes = compare_metadata(MigrationContext.configure(connection), db.metadata)
                assert not changes, f'Model/migration mismatch: {changes}'
            print('Migration matches application models: PASS')

            db.session.remove()
            downgrade(directory=migrations, revision=BASE_REVISION)
            assert 'work_venues' not in inspect(db.engine).get_table_names()
            assert tuple(db.session.execute(text('SELECT * FROM tasks WHERE id=1')).one()) == before
            print('Rollback preserves legacy tables and task: PASS')
        finally:
            db.session.remove()
            db.engine.dispose()


def main():
    # No connection string or existing database argument is accepted.
    parent = PROJECT_ROOT / 'instance'
    parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='venue_schema_check_', dir=parent) as folder:
        print('Using a new disposable SQLite database.')
        verify_in_temporary_directory(folder)
    print('Temporary database removed. Existing local databases and Neon were not changed.')


if __name__ == '__main__':
    main()
