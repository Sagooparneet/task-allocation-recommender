from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.models import (WorkVenue, TaskVenueDetails, Task, TaskSkill, Skill,
                        Supervisor, TaskAssignment, OnboardingAgent)
from app.services.recommendation_service import HybridRecommendationService
from conftest import task_venue_fields


def login(client, email='supervisor@test.com'):
    client.post('/auth/login', data={'email': email, 'password': 'password123'})


def payload(client):
    fields = task_venue_fields(client)
    with client.application.app_context():
        skill_id = Skill.query.filter_by(name='KYC Verification').one().id
    return dict(fields, task_type='KYC Verification', location='Nairobi',
                required_skills=str(skill_id), description='Keep my description',
                deadline=(datetime.now(timezone(timedelta(hours=3))) + timedelta(days=7)).strftime('%Y-%m-%dT%H:%M'),
                location_instructions='Ask for the event coordinator', location_contact='Supervisor desk')


def test_snapshot_uses_database_address_and_survives_edits(app, client):
    login(client)
    data = payload(client)
    data['address'] = 'Forged browser address'
    assert client.post('/supervisor/task/create', data=data).status_code == 302
    with app.app_context():
        task = Task.query.one()
        task_id = task.id
        snapshot = TaskVenueDetails.query.one()
        assert (snapshot.address, snapshot.reporting_point) == ('Test address', 'Test reception')
        assert snapshot.instructions == 'Ask for the event coordinator'
        before = HybridRecommendationService().get_recommendations(task_id, limit=5)
        venue = db.session.get(WorkVenue, int(data['venue_id']))
        venue.address = 'Changed address'
        venue.name = 'Changed name'
        venue.is_active = False
        db.session.commit()
        after = HybridRecommendationService().get_recommendations(task_id, limit=5)
        assert [(x['agent_id'], x['match_percentage']) for x in before] == [(x['agent_id'], x['match_percentage']) for x in after]
        assert db.session.get(TaskVenueDetails, task_id).address == 'Test address'
        worker = OnboardingAgent.query.filter_by(email='netease-6376@demo.invalid').one()
        db.session.add(TaskAssignment(task_id=task_id, agent_id=worker.id,
                       supervisor_id=task.supervisor_id, status='Assigned'))
        db.session.commit()
    for path in ('/supervisor/dashboard', f'/supervisor/task/{task_id}/recommendations'):
        page = client.get(path)
        assert page.status_code == 200
        assert b'Test address' in page.data and b'Test reception' in page.data
        assert b'Changed address' not in page.data
    client.get('/auth/logout')
    login(client, 'netease-6376@demo.invalid')
    assert b'Test address' in client.get('/agent/dashboard').data
    client.get('/auth/logout')
    login(client, 'netease-13495@demo.invalid')
    assert b'Test address' not in client.get('/agent/dashboard').data


@pytest.mark.parametrize('change', [dict(venue_id=''), dict(venue_id='999999'),
    dict(venue_id='bad'), dict(location='Mombasa'), dict(reporting_point=' '),
    dict(reporting_point='x'*201), dict(location_instructions='x'*2001),
    dict(location_contact='x'*251)])
def test_invalid_location_details_save_nothing_and_keep_entries(app, client, change):
    login(client)
    data = payload(client)
    data.update(change)
    response = client.post('/supervisor/task/create', data=data)
    assert response.status_code == 200
    assert b'Keep my description' in response.data
    with app.app_context():
        assert Task.query.count() == TaskSkill.query.count() == TaskVenueDetails.query.count() == 0


def test_deactivated_after_form_open_is_rejected(app, client):
    login(client)
    data = payload(client)
    with app.app_context():
        db.session.get(WorkVenue, int(data['venue_id'])).is_active = False
        db.session.commit()
    response = client.post('/supervisor/task/create', data=data)
    assert b'Please choose an active work location' in response.data
    assert b'Test service point' not in client.get('/supervisor/task/create').data


def test_empty_state_and_multiple_venues_per_city(app, client):
    login(client)
    assert b'No active work locations' in client.get('/supervisor/task/create').data
    data = payload(client)
    with app.app_context():
        second = WorkVenue(city='Nairobi', name='Second point', address='Second address')
        db.session.add(second)
        db.session.commit()
        data['venue_id'] = str(second.id)
    assert b'Second point' in client.get('/supervisor/task/create').data
    assert client.post('/supervisor/task/create', data=data).status_code == 302
    with app.app_context():
        assert TaskVenueDetails.query.one().address == 'Second address'


def test_csrf_and_other_roles_cannot_create_task(app, client):
    login(client)
    data = payload(client)
    data.pop('task_create_csrf_token')
    assert client.post('/supervisor/task/create', data=data).status_code == 400
    for email in ('admin@test.com', 'netease-6376@demo.invalid'):
        client.get('/auth/logout')
        login(client, email)
        assert client.post('/supervisor/task/create', data=data).status_code == 302
    with app.app_context():
        assert Task.query.count() == 0


def test_snapshot_and_task_rollback_together(app, client, monkeypatch):
    login(client)
    data = payload(client)
    original = db.session.add
    def fail_snapshot(record):
        if isinstance(record, TaskVenueDetails):
            raise SQLAlchemyError('Simulated snapshot failure')
        return original(record)
    monkeypatch.setattr(db.session, 'add', fail_snapshot)
    assert b'The task could not be saved' in client.post('/supervisor/task/create', data=data).data
    with app.app_context():
        assert Task.query.count() == TaskSkill.query.count() == TaskVenueDetails.query.count() == 0


def test_legacy_task_stays_city_only_and_other_supervisor_cannot_read(app, client):
    login(client)
    with app.app_context():
        owner = Supervisor.query.one()
        legacy = Task(task_type='Old task', location='Nakuru', supervisor_id=owner.id)
        db.session.add(legacy)
        db.session.commit()
        task_id = legacy.id
    assert b'Nakuru' in client.get('/supervisor/dashboard').data
    assert b'Where to go' not in client.get(f'/supervisor/task/{task_id}/recommendations').data
    with app.app_context():
        assert TaskVenueDetails.query.count() == 0
        other = Supervisor(name='Other', email='other@test.com')
        other.set_password('password123')
        db.session.add(other)
        db.session.commit()
    client.get('/auth/logout')
    login(client, 'other@test.com')
    assert client.get(f'/supervisor/task/{task_id}/recommendations').status_code == 403


def test_deactivated_venue_is_rechecked_even_when_cached(app, client):
    login(client)
    data = payload(client)
    # Hold the record in the request session while a separate session updates it.
    cached_venue = db.session.get(WorkVenue, int(data['venue_id']))
    assert cached_venue.is_active is True
    with app.app_context():
        venue = db.session.get(WorkVenue, cached_venue.id)
        venue.is_active = False
        db.session.commit()
    assert cached_venue.is_active is True
    response = client.post('/supervisor/task/create', data=data)
    assert response.status_code == 200
    assert b'Please choose an active work location' in response.data
    assert Task.query.count() == TaskSkill.query.count() == TaskVenueDetails.query.count() == 0
