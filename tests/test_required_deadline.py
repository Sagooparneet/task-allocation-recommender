from html.parser import HTMLParser
import pytest
from app.models import Skill, Task


@pytest.mark.parametrize("value", [None, "", "   "])
def test_deadline_cannot_be_omitted(app, client, value):
    client.post("/auth/login", data={"email": "supervisor@test.com", "password": "password123"})
    with app.app_context():
        skill_id = Skill.query.first().id
    data = {"task_type": "KYC Verification", "location": "Nairobi",
            "required_skills": str(skill_id), "description": "Keep my entries"}
    if value is not None:
        data["deadline"] = value
    response = client.post("/supervisor/task/create", data=data)
    assert b"Please choose a deadline." in response.data
    assert b"Keep my entries" in response.data
    with app.app_context():
        assert Task.query.count() == 0


def test_required_browser_field_and_clean_copy(client):
    client.post("/auth/login", data={"email": "supervisor@test.com", "password": "password123"})

    class Fields(HTMLParser):
        required_deadline = False

        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if tag == "input" and attrs.get("name") == "deadline":
                self.required_deadline = "required" in attrs

    form = client.get("/supervisor/task/create").get_data(as_text=True)
    parser = Fields()
    parser.feed(form)
    assert parser.required_deadline
    assert "Optional" not in form
    assert "About these skill labels" not in form
    assert "research dataset" not in form
    dashboard = client.get("/supervisor/dashboard").get_data(as_text=True)
    assert "demonstration aliases" not in dashboard
    assert "Source reference" not in dashboard
