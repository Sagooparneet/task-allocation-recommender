from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser

import pytest
from app.extensions import db
from app.models import Skill, Task, TaskSkill, TaskVenueDetails, Supervisor
from app.services.recommendation_service import HybridRecommendationService
from conftest import task_venue_fields


def sign_in(client):
    client.post('/auth/login', data={'email': 'supervisor@test.com', 'password': 'password123'})


def fields(client):
    data = task_venue_fields(client)
    with client.application.app_context():
        ids = [s.id for s in Skill.query.filter(Skill.name.in_(
            ['KYC Verification', 'NetEase capability 56'])).all()]
    return dict(data, task_type='Register new customers at KICC', location='Nairobi',
                required_skills=[str(x) for x in ids],
                deadline=(datetime.now(timezone(timedelta(hours=3))) + timedelta(days=7)).strftime('%Y-%m-%dT%H:%M'))


def test_form_has_title_and_same_service_ids(app, client):
    sign_in(client)
    class Fields(HTMLParser):
        title = None
        dropdown = False
        services = []
        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if attrs.get('name') == 'task_type':
                if tag == 'input': self.title = attrs
                if tag == 'select': self.dropdown = True
            if tag == 'input' and attrs.get('name') == 'required_skills':
                self.services.append(int(attrs['value']))
    page = client.get('/supervisor/task/create').get_data(as_text=True)
    parser = Fields()
    parser.feed(page)
    assert parser.title['type'] == 'text'
    assert parser.title['maxlength'] == '100' and 'required' in parser.title
    assert not parser.dropdown
    assert 'Services needed' in page and 'Other / New Task Type' not in page
    with app.app_context():
        assert set(parser.services) == {s.id for s in Skill.query.all()}


def test_different_titles_keep_same_requirements_and_ranking(app, client):
    sign_in(client)
    data = fields(client)
    for title in ['KYC Verification', 'Register new customers at KICC']:
        data['task_type'] = title
        assert client.post('/supervisor/task/create', data=data).status_code == 302
    with app.app_context():
        tasks = Task.query.order_by(Task.id).all()
        assert [t.task_type for t in tasks] == ['KYC Verification', 'Register new customers at KICC']
        results = []
        for task in tasks:
            assert {s.skill_id for s in TaskSkill.query.filter_by(task_id=task.id)} == {int(x) for x in data['required_skills']}
            rows = HybridRecommendationService().get_recommendations(task.id)
            assert rows
            results.append([(r['agent_id'], r['source_worker_id'], r['score'], r['components']) for r in rows])
        assert results[0] == results[1]


@pytest.mark.parametrize('title', ['', '   ', 'x' * 101])
def test_invalid_title_preserves_form_without_saving(app, client, title):
    sign_in(client)
    data = fields(client)
    data.update(task_type=title, description='Keep my instructions')
    response = client.post('/supervisor/task/create', data=data)
    assert response.status_code == 200
    assert b'Keep my instructions' in response.data
    with app.app_context():
        assert Task.query.count() == TaskSkill.query.count() == TaskVenueDetails.query.count() == 0


def test_title_does_not_replace_required_services(app, client):
    sign_in(client)
    data = fields(client)
    data['task_type'] = 'KYC Verification'
    data.pop('required_skills')
    response = client.post('/supervisor/task/create', data=data)
    assert b'Please select at least one service.' in response.data
    with app.app_context():
        assert Task.query.count() == 0


def test_existing_task_and_older_form_submission_stay_compatible(app, client):
    sign_in(client)
    with app.app_context():
        old = Task(task_type='Existing SIM Registration', location='Mombasa',
                   supervisor_id=Supervisor.query.one().id)
        db.session.add(old)
        db.session.commit()
        old_id = old.id
    assert b'Existing SIM Registration' in client.get('/supervisor/dashboard').data
    data = fields(client)
    data.update(task_type='__other__', custom_task_type='Earlier open form title')
    assert client.post('/supervisor/task/create', data=data).status_code == 302
    with app.app_context():
        old = db.session.get(Task, old_id)
        assert (old.task_type, old.location) == ('Existing SIM Registration', 'Mombasa')
        assert db.session.get(TaskVenueDetails, old_id) is None
        assert Task.query.filter_by(task_type='Earlier open form title').count() == 1
