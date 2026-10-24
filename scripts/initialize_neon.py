"""Populate an empty migrated Neon database. Never migrate a local database."""
from getpass import getpass
from pathlib import Path
import secrets
import sys

from sqlalchemy import func, null, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.security import generate_password_hash

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))

from app import create_app
from app.extensions import db
from app.models import Supervisor, OnboardingAgent, Skill, AgentSkill, WorkerSourceBinding
from app.services.netease_dataset_profiles import load_dataset_profiles
from ml.src.recommender import load_artifacts


def populate_empty_database(name, email, password):
    """Caller provides an app context; all inserts commit or roll back together."""
    name, email = name.strip(), email.strip().lower()
    if not name or len(name) > 100:
        raise ValueError('Enter a supervisor name of 1 to 100 characters.')
    if (email.count('@') != 1 or len(email) > 120
            or any(c.isspace() for c in email)):
        raise ValueError('Enter a valid supervisor email address.')
    local, domain = email.split('@')
    if not local or not domain or domain.endswith('.invalid'):
        raise ValueError('Use a supervisor email, not a reserved demo address.')
    if len(password) < 12:
        raise ValueError('The password must contain at least 12 characters.')

    profiles = load_dataset_profiles()
    artifacts = load_artifacts()
    capabilities = set(artifacts['model']['capabilities'])
    if len(profiles) != 1653 or set(profiles) != set(artifacts['profiles']):
        raise ValueError('Dataset worker IDs do not match the verified model.')
    for worker, profile in profiles.items():
        codes = set(profile['capabilities'])
        if not codes.issubset(capabilities):
            raise ValueError('Unexpected capability code in dataset.')
        expected = {'NetEase capability ' + c for c in codes}
        if expected != set(artifacts['profiles'][worker]['skills']):
            raise ValueError('Dataset capability history differs from model profiles.')

    supervisor = Supervisor(name=name, email=email)
    supervisor.set_password(password)
    disabled_hash = generate_password_hash(secrets.token_urlsafe(64))
    with db.session.begin():
        if db.engine.dialect.name == 'postgresql':
            db.session.execute(text("SET LOCAL lock_timeout = '5s'"))
            db.session.execute(text("SET LOCAL statement_timeout = '120s'"))
            # Serialize setup attempts. Names come from application metadata.
            quote = db.engine.dialect.identifier_preparer.quote
            names = ', '.join(quote(t.name) for t in db.metadata.sorted_tables)
            db.session.execute(text(f'LOCK TABLE {names} IN EXCLUSIVE MODE'))
            revision = db.session.execute(
                text('SELECT version_num FROM alembic_version')
            ).scalar_one()
            if revision != '4baace48147a':
                raise ValueError('Unexpected schema version. Review migrations first.')

        for table in db.metadata.sorted_tables:
            count = db.session.execute(select(func.count()).select_from(table)).scalar_one()
            if count:
                raise ValueError(
                    'Database already contains application records. '
                    'Setup refused; existing records were not changed.'
                )

        skills = {c: Skill(name=f'NetEase capability {c}')
                  for c in sorted(capabilities, key=int)}
        db.session.add(supervisor)
        db.session.add_all(skills.values())
        workers = {}
        for source_id in sorted(profiles, key=int):
            rate = profiles[source_id]['training_success_rate']
            workers[source_id] = OnboardingAgent(
                name=f'NetEase worker {source_id}',
                email=f'netease-{source_id}@demo.invalid',
                password_hash=disabled_hash,
                specialization=None,
                location=None,
                availability=True,
                workload=0,
                performance_score=rate if rate is not None else null(),
            )
        db.session.add_all(workers.values())
        db.session.flush()
        links = []
        for source_id, worker in workers.items():
            links.append(WorkerSourceBinding(agent_id=worker.id, source_worker_id=source_id))
            for capability in profiles[source_id]['capabilities']:
                links.append(AgentSkill(
                    agent_id=worker.id, skill_id=skills[capability].id,
                    proficiency_level='Observed participation',
                ))
        db.session.add_all(links)
        db.session.flush()
        if WorkerSourceBinding.query.count() != 1653:
            raise ValueError('Worker binding count failed verification.')
    return len(workers)


def main():
    connection_string = getpass('Paste your Neon connection string: ').strip()
    try:
        url = make_url(connection_string)
        if url.drivername not in ('postgresql', 'postgres'):
            raise ValueError()
        if not url.host or not url.host.endswith('.neon.tech'):
            raise ValueError()
        url = url.set(drivername='postgresql+psycopg')
    except (ValueError, SQLAlchemyError):
        raise SystemExit('Invalid Neon PostgreSQL connection URL.') from None

    print('This creates 1 supervisor, 1653 dataset workers, and their database mappings.')
    print('It refuses nonempty application tables and creates no tasks or assignments.')
    name = input('Hosted supervisor name: ')
    email = input('Hosted supervisor email: ')
    password = getpass('Choose a password (12+ characters): ')
    if password != getpass('Confirm password: '):
        raise SystemExit('Passwords do not match. Nothing was changed.')

    app = create_app({
        'SQLALCHEMY_DATABASE_URI': url,
        'SQLALCHEMY_ENGINE_OPTIONS': {
            'connect_args': {'sslmode': 'require', 'connect_timeout': 20,
                             'prepare_threshold': None},
            'pool_pre_ping': True,
            'hide_parameters': True,
        },
    })
    with app.app_context():
        try:
            count = populate_empty_database(name, email, password)
            print('Neon initialisation: PASS')
            print('Supervisors: 1')
            print(f'Workers: {count}')
            print(f'Database worker mappings: {count}')
            print('Tasks: 0')
            print('Assignments: 0')
            print('Worker logins remain disabled. No local databases were changed.')
        except ValueError as error:
            raise SystemExit(str(error)) from None
        except SQLAlchemyError as error:
            raise SystemExit(
                f'Database operation failed: {type(error).__name__}. '
                'Do not delete records or rerun setup until the outcome is checked. '
                'Connection details have been hidden.'
            ) from None
        finally:
            db.session.remove()
            db.engine.dispose()


if __name__ == '__main__':
    main()
