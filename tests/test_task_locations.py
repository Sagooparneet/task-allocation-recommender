from conftest import task_venue_fields
import datetime as _deadline_datetime

def _future_task_deadline():
    return (_deadline_datetime.datetime.now(_deadline_datetime.timezone(_deadline_datetime.timedelta(hours=3))) + _deadline_datetime.timedelta(days=7)).strftime("%Y-%m-%dT%H:%M")

from html.parser import HTMLParser

import pytest

from app.models import Skill, Task


LOCATIONS = ["Nairobi", "Mombasa", "Kisumu", "Nakuru", "Eldoret"]


def sign_in(client):
    client.post("/auth/login", data={
        "email": "supervisor@test.com", "password": "password123"
    })


@pytest.mark.parametrize("location", LOCATIONS + ["Online", "Remote", "Unlisted town"])
def test_location_is_validated_before_saving(app, client, location):
    sign_in(client)
    with app.app_context():
        skill_id = Skill.query.first().id
    response = client.post("/supervisor/task/create", data={**task_venue_fields(client, location=location), "deadline": _future_task_deadline(),
        "task_type": "KYC Verification", "description": "Location test",
        "location": location, "priority": "Medium", "required_skills": str(skill_id),
    })
    with app.app_context():
        tasks = Task.query.all()
        if location in LOCATIONS:
            assert response.status_code == 302
            assert len(tasks) == 1 and tasks[0].location == location
        else:
            assert not tasks
            assert b"Please select a location from the list." in response.data
            assert b"Location test" in response.data


def test_dropdown_choices_and_preserved_location(client):
    sign_in(client)

    class LocationSelect(HTMLParser):
        def __init__(self):
            super().__init__()
            self.inside = False
            self.values = []
            self.selected = []

        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if tag == "select" and attrs.get("name") == "location":
                self.inside = True
                assert "required" in attrs
            if tag == "option" and self.inside:
                self.values.append(attrs.get("value"))
                if "selected" in attrs:
                    self.selected.append(attrs.get("value"))

        def handle_endtag(self, tag):
            if tag == "select":
                self.inside = False

    parser = LocationSelect()
    parser.feed(client.get("/supervisor/task/create").get_data(as_text=True))
    assert parser.values == [""] + LOCATIONS
    # Missing required skills returns the form while retaining the chosen location.
    response = client.post("/supervisor/task/create", data={**task_venue_fields(client, location='Nairobi'), "deadline": _future_task_deadline(),
        "task_type": "KYC Verification", "location": "Mombasa"
    })
    parser = LocationSelect()
    parser.feed(response.get_data(as_text=True))
    assert parser.selected == ["Mombasa"]
