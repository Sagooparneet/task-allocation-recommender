import argparse
import getpass
import json
from pathlib import Path
import secrets

from sqlalchemy.engine import URL
from sqlalchemy import null
from werkzeug.security import generate_password_hash

from app import create_app
from app.extensions import db
from app.models import Supervisor, OnboardingAgent, Skill, AgentSkill
from app.services.netease_dataset_profiles import load_dataset_profiles
from ml.src.recommender import load_artifacts


def validate_target(value):
    target = Path(value).expanduser().resolve()
    if target.exists():
        raise ValueError(
            f'Refusing existing folder: {target}. Choose a new folder; '
            'this script never resets or migrates an installation.'
        )
    if not target.parent.is_dir():
        raise ValueError('The parent folder must already exist.')
    return target


def validate_sources():
    profiles = load_dataset_profiles()
    artifacts = load_artifacts()
    if not profiles or set(profiles) != set(artifacts['profiles']):
        raise ValueError('Dataset workers and model workers do not match.')
    known = set(artifacts['model']['capabilities'])
    for worker, profile in profiles.items():
        caps = set(profile['capabilities'])
        if not caps.issubset(known):
            raise ValueError(f'Unknown capability for worker {worker}.')
        if {'NetEase capability ' + c for c in caps} != set(artifacts['profiles'][worker]['skills']):
            raise ValueError(f'Dataset/model capability mismatch for worker {worker}.')
    return profiles, sorted(known, key=int)


def write_json(path, value):
    # Exclusive creation: never overwrite a file.
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def initialize(target, name, email, password):
    target = validate_target(target)
    name, email = name.strip(), email.strip().lower()
    if not name or len(name) > 100:
        raise ValueError('Supervisor name must contain 1 to 100 characters.')
    if len(email) > 120 or email.count('@') != 1 or any(c.isspace() for c in email):
        raise ValueError('Enter a valid supervisor email address.')
    local, domain = email.split('@')
    if not local or not domain or domain.endswith('.invalid'):
        raise ValueError('Use your supervisor email, not a reserved demo address.')
    if len(password) < 12:
        raise ValueError('Choose a password of at least 12 characters.')
    profiles, capabilities = validate_sources()

    # mkdir without exist_ok protects against another process claiming the target.
    target.mkdir()
    db_path = target / 'task_allocation.db'
    app = create_app({
        'SQLALCHEMY_DATABASE_URI': URL.create('sqlite', database=str(db_path)),
        'SECRET_KEY': secrets.token_hex(32),
    })
    app.instance_path = str(target)
    bindings, unknown = {}, []
    try:
        with app.app_context():
            db.create_all()
            supervisor = Supervisor(name=name, email=email)
            supervisor.set_password(password)
            db.session.add(supervisor)
            skills = {c: Skill(name=f'NetEase capability {c}') for c in capabilities}
            db.session.add_all(skills.values())
            db.session.flush()
            # No worker login is enabled. The random password is never retained.
            disabled_hash = generate_password_hash(secrets.token_urlsafe(64))
            for worker in sorted(profiles, key=int):
                profile = profiles[worker]
                agent = OnboardingAgent(
                    name=f'NetEase worker {worker}',
                    email=f'netease-{worker}@demo.invalid',
                    password_hash=disabled_hash,
                    specialization=None,
                    location=None,
                    availability=True,
                    workload=0,
                    performance_score=(profile['training_success_rate']
                                       if profile['training_success_rate'] is not None else null()),
                )
                db.session.add(agent)
                db.session.flush()
                bindings[str(agent.id)] = worker
                if profile['training_success_rate'] is None:
                    unknown.append(agent.id)
                for capability in profile['capabilities']:
                    db.session.add(AgentSkill(
                        agent_id=agent.id,
                        skill_id=skills[capability].id,
                        proficiency_level='Observed participation',
                    ))
            db.session.commit()
            db.session.remove()
            db.engine.dispose()

        write_json(target / 'onboarding_capability_mapping.json', {
            'schema_version': 1,
            'purpose': 'Direct source capability codes; no onboarding interpretation',
            'skill_to_capabilities': {
                f'NetEase capability {c}': [c] for c in capabilities
            },
        })
        write_json(target / 'netease_agent_bindings.json', {
            'schema_version': 1,
            'status': 'ready',
            'worker_bindings': bindings,
            'legacy_agent_ids': [],
            'unknown_performance_agent_ids': unknown,
            'notes': [
                'Worker IDs and training histories originate in NetEaseCrowd.',
                'Names are worker-ID labels; no personal names or locations are invented.',
                'Emails are local account placeholders, not source contact details.',
                'Available=True and workload=0 are initial website state, not dataset facts.',
                'Worker logins are disabled; no tasks or assignments are fabricated.',
            ],
        })
        # Written last: absence means setup did not finish successfully.
        write_json(target / 'setup_complete.json', {
            'schema_version': 1,
            'workers': len(bindings),
            'tasks': 0,
            'assignments': 0,
            'supervisors': 1,
            'database': db_path.name,
        })
    except Exception:
        # Preserve diagnostic files; never delete an existing database on failure.
        with app.app_context():
            db.session.rollback()
            db.session.remove()
            db.engine.dispose()
        raise
    return {'instance_directory': str(target), 'workers': len(bindings),
            'supervisors': 1, 'tasks': 0, 'assignments': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--instance-dir', required=True, help='A new folder that does not exist yet')
    parser.add_argument('--check-only', action='store_true', help='Validate without creating any files')
    args = parser.parse_args()
    try:
        target = validate_target(args.instance_dir)
        profiles, capabilities = validate_sources()
        print(f'New installation folder: {target}')
        print(f'Dataset workers: {len(profiles)}')
        print('Source capability codes: ' + ', '.join(capabilities))
        if args.check_only:
            print('Checks passed. No files or database records were changed.')
            return
        name = input('Supervisor name: ')
        email = input('Supervisor email: ')
        password = getpass.getpass('Choose a supervisor password (12+ characters): ')
        if password != getpass.getpass('Confirm password: '):
            raise ValueError('Passwords do not match.')
        print(json.dumps(initialize(target, name, email, password), indent=2))
        print('Separate installation created. Your running website has NOT been switched.')
        print('Do not copy its binding file into your existing instance folder.')
    except (ValueError, OSError) as exc:
        parser.exit(1, f'Setup stopped: {exc}\n')


if __name__ == '__main__':
    main()
