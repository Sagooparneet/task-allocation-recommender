from html.parser import HTMLParser
import pytest
from app.extensions import db
from app.models import WorkVenue
from test_admin_venues import login, form


class Page(HTMLParser):
    def __init__(self, response):
        super().__init__()
        self.ids = {}
        self.links = []
        self.feed(response.get_data(as_text=True))

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'id' in attrs:
            assert attrs['id'] not in self.ids
            self.ids[attrs['id']] = attrs
        if tag == 'a':
            self.links.append(attrs.get('href'))


def assert_error(page, field):
    assert '#' + field in page.links
    assert page.ids[field]['aria-invalid'] == 'true'
    assert field + '-error' in page.ids[field]['aria-describedby'].split()
    assert field + '-error' in page.ids
    assert page.ids['form-error-summary']['tabindex'] == '-1'


def test_empty_login_has_two_linked_errors(client):
    response = client.post('/auth/login', data={})
    assert response.status_code == 200
    page = Page(response)
    assert_error(page, 'email')
    assert_error(page, 'password')
    assert 'value' not in page.ids['password']
    assert client.get('/supervisor/dashboard').status_code == 302


@pytest.mark.parametrize('email', ['supervisor@test.com', 'unknown@test.com'])
def test_wrong_credentials_are_generic_and_password_never_returned(client, email):
    password = 'Secret-that-must-not-be-returned'
    response = client.post('/auth/login', data={'email': email, 'password': password})
    assert b'Invalid email or password.' in response.data
    assert password.encode() not in response.data
    page = Page(response)
    assert page.ids['email']['value'] == email
    assert '#email' in page.links and '#password' in page.links
    assert page.ids['password']['aria-describedby'] == 'credentials-error'
    assert client.get('/supervisor/dashboard').status_code == 302


@pytest.mark.parametrize('email,path', [('supervisor@test.com','/supervisor/dashboard'),
    ('admin@test.com','/admin/dashboard'), ('netease-6376@demo.invalid','/agent/dashboard')])
def test_corrected_login_redirects_by_role(client, email, path):
    client.post('/auth/login', data={})
    response = client.post('/auth/login', data={'email': email, 'password': 'password123'})
    assert response.status_code == 302 and response.headers['Location'] == path


def test_location_errors_link_to_fields_and_keep_values(app, client):
    login(client)
    response = client.post('/admin/venues/new', data=form(client, city='', name='', address='', directions='Keep this', map_url='http://example.com'))
    assert response.status_code == 422
    page = Page(response)
    for field in ('city','name','address','map_url'):
        assert_error(page, field)
    assert b'Keep this' in response.data
    with app.app_context():
        assert WorkVenue.query.count() == 0


def test_invalid_edit_preserves_database_then_corrected_edit_saves(app, client):
    login(client)
    client.post('/admin/venues/new', data=form(client))
    with app.app_context():
        venue_id = WorkVenue.query.one().id
    path = f'/admin/venues/{venue_id}/edit'
    response = client.post(path, data=form(client, name='', address='New Road'))
    assert_error(Page(response), 'name')
    with app.app_context():
        db.session.expire_all()
        assert db.session.get(WorkVenue, venue_id).address == 'Example Road'
    assert client.post(path, data=form(client, address='New Road')).status_code == 302
    with app.app_context():
        db.session.expire_all()
        assert db.session.get(WorkVenue, venue_id).address == 'New Road'
