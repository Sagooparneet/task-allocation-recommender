from conftest import task_venue_fields
from datetime import datetime, timedelta, timezone

import pytest

from app.models import Skill, Task


@pytest.mark.parametrize("days,created", [(-1, False), (0, True), (7, True)])
def test_deadline_date_validation(app, client, days, created):
    # Direct POST proves server-side enforcement even when browser checks are bypassed.
    client.post("/auth/login", data={
        "email": "supervisor@test.com", "password": "password123"
    })
    with app.app_context():
        skill_id = Skill.query.first().id
    day = datetime.now(timezone(timedelta(hours=3))).date() + timedelta(days=days)
    response = client.post("/supervisor/task/create", data={**task_venue_fields(client, location='Nairobi'),
        "task_type": "__other__", "custom_task_type": "Deadline check",
        "description": "Keep these details", "location": "Nairobi",
        "priority": "High", "deadline": day.isoformat() + "T12:00",
        "required_skills": str(skill_id),
    })
    with app.app_context():
        assert Task.query.count() == int(created)
    if not created:
        assert response.status_code == 200
        assert b"Please choose today or a later date" in response.data
        assert b"Keep these details" in response.data
        assert b'value="Deadline check"' in response.data
    else:
        assert response.status_code == 302


def test_form_has_kenya_date_minimum(app, client):
    client.post("/auth/login", data={
        "email": "supervisor@test.com", "password": "password123"
    })
    response = client.get("/supervisor/task/create")
    today = datetime.now(timezone(timedelta(hours=3))).date().isoformat()
    assert f'min="{today}T00:00"'.encode() in response.data
