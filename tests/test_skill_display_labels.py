import datetime as _deadline_datetime

def _future_task_deadline():
    return (_deadline_datetime.datetime.now(_deadline_datetime.timezone(_deadline_datetime.timedelta(hours=3))) + _deadline_datetime.timedelta(days=7)).strftime("%Y-%m-%dT%H:%M")

from html.parser import HTMLParser

import pytest

from app.extensions import db
from app.models import Skill, Task, TaskSkill
from app.services.skill_display_labels import SKILL_LABELS
from app.services.netease_recommendation_service import NetEaseRecommendationService


def login(client):
    client.post("/auth/login", data={
        "email": "supervisor@test.com", "password": "password123"
    })


class SkillChoices(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "input" and attrs.get("name") == "required_skills":
            self.ids.append(attrs["value"])


@pytest.mark.parametrize("code,label", list(SKILL_LABELS.items()))
def test_readable_skill_keeps_original_database_identity(app, client, code, label):
    login(client)
    source_name = f"NetEase capability {code}"
    with app.app_context():
        skill = Skill.query.filter_by(name=source_name).first()
        if skill is None:
            skill = Skill(name=source_name)
            db.session.add(skill)
            db.session.commit()
        skill_id = skill.id
    page = client.get("/supervisor/task/create").get_data(as_text=True)
    parser = SkillChoices()
    parser.feed(page)
    assert str(skill_id) in parser.ids
    assert label in page
    assert source_name not in page
    result = client.post("/supervisor/task/create", data={"deadline": _future_task_deadline(),
        "task_type": "__other__", "custom_task_type": label,
        "location": "Nairobi", "priority": "Medium", "required_skills": str(skill_id)
    })
    assert result.status_code == 302
    with app.app_context():
        task = Task.query.one()
        link = TaskSkill.query.filter_by(task_id=task.id).one()
        assert link.skill_id == skill_id
        assert link.skill.name == source_name


def test_recommendation_page_uses_labels_without_changing_scores(app, client):
    login(client)
    with app.app_context():
        skill_id = Skill.query.filter_by(name="NetEase capability 56").one().id
    client.post("/supervisor/task/create", data={"deadline": _future_task_deadline(),
        "task_type": "KYC Verification", "location": "Nairobi",
        "priority": "Medium", "required_skills": str(skill_id)
    })
    with app.app_context():
        task_id = Task.query.one().id
        before = NetEaseRecommendationService().get_recommendations(task_id)
    page = client.get(f"/supervisor/task/{task_id}/recommendations").get_data(as_text=True)
    assert "KYC Verification" in page
    assert "capability 56" not in page
    assert "NetEase capabilities 56" not in page
    assert "not verified onboarding qualifications" not in page
    with app.app_context():
        after = NetEaseRecommendationService().get_recommendations(task_id)
        assert [(r['agent_id'], r['source_worker_id'], r['score']) for r in after] == [
            (r['agent_id'], r['source_worker_id'], r['score']) for r in before]
        assert after[0]['skills'] == before[0]['skills']
