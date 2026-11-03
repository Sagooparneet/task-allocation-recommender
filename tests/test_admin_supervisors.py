from app.extensions import db
from app.models import Supervisor, Task


def login(client, email='admin@test.com'):
    return client.post('/auth/login', data={'email': email, 'password': 'password123'})


def test_admin_directory_shows_task_totals_and_navigation(app, client):
    record = Supervisor.query.filter_by(email='supervisor@test.com').one()
    db.session.add(Task(task_type='Existing job', supervisor_id=record.id))
    db.session.commit()
    login(client)
    response = client.get('/admin/supervisors')
    assert response.status_code == 200
    assert b'Test Supervisor' in response.data
    assert b'supervisor@test.com' in response.data
    assert b'Active' in response.data
    assert b'>1</td>' in response.data
    assert b'href="/admin/supervisors" aria-current="page"' in response.data


def test_search_and_status_filter(app, client):
    other = Supervisor(name='Another Person', email='another@example.com', account_disabled=True)
    other.set_password('password123')
    db.session.add(other)
    db.session.commit()
    login(client)
    response = client.get('/admin/supervisors', query_string={'q':'another','status':'inactive'})
    assert b'Another Person' in response.data
    assert b'Test Supervisor' not in response.data
    assert b'Inactive' in response.data
    response = client.get('/admin/supervisors', query_string={'q':'missing'})
    assert b'No supervisors found' in response.data


def test_non_admin_cannot_see_directory_or_navigation(app, client):
    login(client, 'supervisor@test.com')
    assert client.get('/admin/supervisors').status_code == 403
    assert b'href="/admin/supervisors"' not in client.get('/supervisor/dashboard').data
    client.get('/auth/logout')
    assert client.get('/admin/supervisors').status_code == 302
