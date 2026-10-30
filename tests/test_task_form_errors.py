from html.parser import HTMLParser

from app.models import Task, TaskSkill, TaskVenueDetails
from test_task_venues import login, payload


class FormPage(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = {}
        self.links = []

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if 'id' in attrs:
            assert attrs['id'] not in self.ids
            self.ids[attrs['id']] = (tag, attrs)
        if tag == 'a':
            self.links.append(attrs.get('href', ''))


def test_multiple_errors_have_linked_fields_and_save_nothing(app, client):
    login(client)
    data = payload(client)
    data.update(task_type='', deadline='', reporting_point='')
    data.pop('required_skills')
    response = client.post('/supervisor/task/create', data=data)
    assert response.status_code == 200
    assert b'Please fix 4 problems' in response.data
    page = FormPage()
    page.feed(response.get_data(as_text=True))
    assert page.ids['form-error-summary'][1]['tabindex'] == '-1'
    for field in ('task_type', 'deadline', 'reporting_point', 'required_skills'):
        assert '#' + field in page.links
        attrs = page.ids[field][1]
        assert attrs['aria-invalid'] == 'true'
        assert field + '-error' in attrs['aria-describedby'].split()
        assert field + '-error' in page.ids
    assert page.ids['required_skills'][0] == 'fieldset'
    assert 'task-title-help' in page.ids['task_type'][1]['aria-describedby'].split()
    assert 'aria-invalid' not in page.ids['location'][1]
    assert b'Keep my description' in response.data
    with app.app_context():
        assert Task.query.count() == TaskSkill.query.count() == TaskVenueDetails.query.count() == 0


def test_optional_field_limits_have_separate_errors_and_preserve_values(client):
    login(client)
    data = payload(client)
    data.update(location_instructions='x' * 2001, location_contact='y' * 251)
    response = client.post('/supervisor/task/create', data=data)
    assert b'Please fix 2 problems' in response.data
    page = FormPage()
    page.feed(response.get_data(as_text=True))
    for field in ('location_instructions', 'location_contact'):
        assert '#' + field in page.links
        assert page.ids[field][1]['aria-invalid'] == 'true'
    assert ('x' * 2001).encode() in response.data
    assert page.ids['location_contact'][1]['value'] == 'y' * 251


def test_corrected_submission_succeeds_without_stale_errors(app, client):
    login(client)
    data = payload(client)
    original_deadline = data['deadline']
    data['deadline'] = ''
    assert b'Please fix 1 problem' in client.post('/supervisor/task/create', data=data).data
    data['deadline'] = original_deadline
    assert client.post('/supervisor/task/create', data=data).status_code == 302
    with app.app_context():
        assert Task.query.count() == 1
    page = client.get('/supervisor/task/create').get_data(as_text=True)
    assert 'id="form-error-summary"' not in page
    assert 'aria-invalid="true"' not in page


def test_title_is_escaped_when_other_field_fails(client):
    login(client)
    data = payload(client)
    data.update(task_type='<script>alert(1)</script>', deadline='')
    page = client.post('/supervisor/task/create', data=data).get_data(as_text=True)
    assert '<script>alert(1)</script>' not in page
    parser = FormPage()
    parser.feed(page)
    assert parser.ids['task_type'][1]['value'] == data['task_type']
