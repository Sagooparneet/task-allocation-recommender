"""Production entry point; importing this module does not initialise a database."""
import os
from pathlib import Path

from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError


def create_production_app():
    required = ('INTELLITASK_SECRET_KEY', 'INTELLITASK_DATABASE_URL')
    missing = [name for name in required if not os.environ.get(name, '').strip()]
    if missing:
        raise RuntimeError('Missing production settings: ' + ', '.join(missing))

    secret = os.environ['INTELLITASK_SECRET_KEY']
    if len(secret) < 32 or secret == 'dev-secret-key-change-later':
        raise RuntimeError('Use a private randomly generated secret of at least 32 characters.')

    try:
        url = make_url(os.environ['INTELLITASK_DATABASE_URL'])
    except ArgumentError:
        raise RuntimeError('Invalid production database URL. Details hidden.') from None

    backend = url.get_backend_name()
    settings = {
        'SECRET_KEY': secret,
        'DEBUG': False,
        'TESTING': False,
        'SESSION_COOKIE_NAME': 'intellitask_session',
        'SESSION_COOKIE_HTTPONLY': True,
        'SESSION_COOKIE_SECURE': True,
        'SESSION_COOKIE_SAMESITE': 'Lax',
    }
    instance = None

    if backend in ('postgresql', 'postgres'):
        url = url.set(drivername='postgresql+psycopg')
        if not url.host or not url.database:
            raise RuntimeError('PostgreSQL requires a host and database name.')
        settings.update({
            'SQLALCHEMY_DATABASE_URI': url,
            'NETEASE_BINDING_STORAGE': 'database',
            'SQLALCHEMY_ENGINE_OPTIONS': {
                'connect_args': {
                    'sslmode': 'require',
                    'connect_timeout': 20,
                    'prepare_threshold': None,
                },
                'pool_pre_ping': True,
                'pool_size': 2,
                'max_overflow': 2,
                'hide_parameters': True,
            },
        })
    elif backend == 'sqlite':
        # Retain the isolated production-style tests used before Neon setup.
        value = os.environ.get('INTELLITASK_INSTANCE_PATH', '').strip()
        if not value:
            raise RuntimeError('SQLite testing requires INTELLITASK_INSTANCE_PATH.')
        instance = Path(value).expanduser()
        if not instance.is_absolute() or not instance.is_dir():
            raise RuntimeError('SQLite test instance must be an existing absolute directory.')
        instance = instance.resolve()
        database = Path(url.database or '')
        if not database.is_absolute() or not database.is_file():
            raise RuntimeError('SQLite testing requires an existing absolute database file.')
        if database.resolve().parent != instance:
            raise RuntimeError('SQLite database must belong to the selected test instance.')
        for filename in ('netease_agent_bindings.json', 'onboarding_capability_mapping.json'):
            if not (instance / filename).is_file():
                raise RuntimeError(f'Missing SQLite test configuration: {filename}')
        settings.update({
            'SQLALCHEMY_DATABASE_URI': url,
            'NETEASE_BINDING_STORAGE': 'file',
        })
    else:
        raise RuntimeError('Unsupported database type for this entry point.')

    from app import create_app
    application = create_app(settings)
    if instance is not None:
        application.instance_path = str(instance)
    return application


app = create_production_app()
