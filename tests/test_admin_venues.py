import pytest
from app.extensions import db
from app.models import WorkVenue, TaskVenueDetails, Task, Supervisor


def login(client, email='admin@test.com'):
    client.post('/auth/login', data={'email': email, 'password': 'password123'})


def form(client, **changes):
    client.get('/admin/venues/new')
    with client.session_transaction() as session:
        token = session['venue_form_token']
    values = dict(csrf_token=token, city='Nairobi', name='Central Hall',
                  address='Example Road', directions='Use the main entrance.',
                  map_url='https://maps.google.com/?q=Nairobi', is_active='on')
    values.update(changes)
    return values


def test_create_list_filter_edit_and_preserve_snapshot(app, client):
    login(client)
    assert client.get('/admin/dashboard').status_code == 200
    response = client.post('/admin/venues/new', data=form(client))
    assert response.status_code == 302
    with app.app_context():
        venue = WorkVenue.query.one()
        venue_id = venue.id
        task = Task(task_type='KYC', location='Nairobi', priority='Medium',
                    status='Pending', supervisor_id=Supervisor.query.first().id)
        db.session.add(task)
        db.session.flush()
        db.session.add(TaskVenueDetails(task_id=task.id, venue_id=venue.id,
                       city=venue.city, venue_name=venue.name, address=venue.address,
                       reporting_point='Reception'))
        db.session.commit()
    assert b'Central Hall' in client.get('/admin/venues').data
    assert b'Central Hall' not in client.get('/admin/venues?city=Mombasa').data
    edited = form(client, name='Updated Hall', address='New Street', is_active='')
    assert client.post(f'/admin/venues/{venue_id}/edit', data=edited).status_code == 302
    with app.app_context():
        assert not db.session.get(WorkVenue, venue_id).is_active
        snapshot = TaskVenueDetails.query.one()
        assert (snapshot.venue_name, snapshot.address) == ('Central Hall', 'Example Road')
    assert b'Updated Hall' not in client.get('/admin/venues?status=active').data
    assert b'Updated Hall' in client.get('/admin/venues?status=inactive').data
    assert client.post(f'/admin/venues/{venue_id}/edit', data=form(client)).status_code == 302


@pytest.mark.parametrize('email', ['supervisor@test.com', 'netease-6376@demo.invalid'])
def test_other_roles_cannot_manage_venues(app, client, email):
    login(client, email)
    for path in ('/admin/venues', '/admin/venues/new', '/admin/venues/1/edit'):
        assert client.get(path).status_code == 403
        if path != '/admin/venues':
            assert client.post(path, data={}).status_code == 403
    with app.app_context():
        assert WorkVenue.query.count() == 0


def test_login_and_csrf_required(app, client):
    assert client.get('/admin/venues').status_code == 302
    login(client)
    assert client.post('/admin/venues/new', data={}).status_code == 400
    assert client.post('/admin/venues/new', data=form(client, csrf_token='wrong')).status_code == 400
    assert client.get('/admin/venues/999/edit').status_code == 404
    with app.app_context():
        assert WorkVenue.query.count() == 0


@pytest.mark.parametrize('changes', [dict(city='Invalid'), dict(name=' '), dict(address=''),
    dict(map_url='javascript:alert(1)'), dict(map_url='https://user:pass@example.com'),
    dict(map_url='https://['), dict(directions='x' * 2001), dict(name='x' * 161)])
def test_invalid_values_keep_form_and_database_unchanged(app, client, changes):
    login(client)
    response = client.post('/admin/venues/new', data=form(client, **changes))
    assert response.status_code == 422
    assert b'Please check' in response.data
    with app.app_context():
        assert WorkVenue.query.count() == 0


def test_duplicate_and_same_name_different_city(app, client):
    login(client)
    assert client.post('/admin/venues/new', data=form(client)).status_code == 302
    assert client.post('/admin/venues/new', data=form(client, name='central hall')).status_code == 422
    assert client.post('/admin/venues/new', data=form(client, city='Kisumu')).status_code == 302
    with app.app_context():
        assert WorkVenue.query.count() == 2


def test_user_text_is_escaped(client):
    login(client)
    client.post('/admin/venues/new', data=form(client, name='<script>alert(1)</script>'))
    html = client.get('/admin/venues').data
    assert b'<script>alert(1)</script>' not in html
    assert b'&lt;script&gt;' in html
