from contextlib import closing
from pathlib import Path
import sqlite3

import pytest
from app.extensions import db
from app.models import Administrator
from scripts.setup_local_admin_login import create_admin, REVISION


def prepare(app):
    with app.app_context():
        Administrator.query.delete()
        db.session.commit()
        database = Path(db.engine.url.database)
    with closing(sqlite3.connect(database)) as connection:
        connection.execute('CREATE TABLE alembic_version (version_num TEXT)')
        connection.execute('INSERT INTO alembic_version VALUES (?)', (REVISION,))
        connection.commit()
    return database


def test_admin_login_backup_and_existing_data_preserved(app, client):
    database = prepare(app)
    backup = create_admin(database, 'Local Administrator', 'NEW@example.com', 'private-test-password')
    with closing(sqlite3.connect(database)) as actual, closing(sqlite3.connect(backup)) as before:
        assert before.execute('PRAGMA integrity_check').fetchone() == ('ok',)
        tables = [row[0] for row in before.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name != 'administrators'"
        )]
        for table in tables:
            assert actual.execute(f'SELECT * FROM "{table}"').fetchall() == before.execute(f'SELECT * FROM "{table}"').fetchall()
        assert before.execute('SELECT count(*) FROM administrators').fetchone() == (0,)
    response = client.post('/auth/login', data={'email': 'new@example.com', 'password': 'private-test-password'})
    assert response.status_code == 302
    assert '/admin/dashboard' in response.location
    assert client.get('/admin/dashboard').status_code == 200
    with pytest.raises(ValueError, match='already exists'):
        create_admin(database, 'Other', 'other@example.com', 'another-test-password')


@pytest.mark.parametrize('email', ['SUPERVISOR@test.com', 'netease-6376@demo.invalid'])
def test_cross_role_collision_is_rejected(app, email):
    database = prepare(app)
    with pytest.raises(ValueError, match='existing account'):
        create_admin(database, 'Admin', email, 'private-test-password')
    with app.app_context():
        assert Administrator.query.count() == 0


def test_wrong_schema_and_invalid_input_do_not_create_account(app):
    database = prepare(app)
    with pytest.raises(ValueError, match='12 characters'):
        create_admin(database, 'Admin', 'new@example.com', 'short')
    with closing(sqlite3.connect(database)) as connection:
        connection.execute("UPDATE alembic_version SET version_num='unexpected'")
        connection.commit()
    with pytest.raises(ValueError, match='migration'):
        create_admin(database, 'Admin', 'new@example.com', 'private-test-password')
    with app.app_context():
        assert Administrator.query.count() == 0
