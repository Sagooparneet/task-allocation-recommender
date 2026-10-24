import pytest

from app.extensions import db
from app.models import OnboardingAgent, Skill, Supervisor, Task, TaskSkill
from app.services.worker_display_names import worker_display_name
from app.services.netease_dataset_profiles import load_dataset_profiles
from app.services.netease_recommendation_service import NetEaseRecommendationService
from ml.src.recommender import load_artifacts, recommend_agents


def test_aliases_preserve_source_history():
    profiles = load_dataset_profiles()
    names = [profile["display_name"] for profile in profiles.values()]
    assert len(names) == len(set(names)) == 1653
    assert profiles["57"]["display_name"] == "Felix Karanja"
    assert profiles["57"]["source_worker_id"] == "57"
    assert profiles["57"]["successful_responses"] == 1043
    assert profiles["57"]["training_responses"] == 1109
    for source_id in profiles:
        assert profiles[source_id]["display_name"] == load_artifacts()["profiles"][source_id]["agent_name"]
    with pytest.raises(ValueError):
        worker_display_name("not-a-source-worker")


def test_alias_on_dashboard_recommendations_and_assignment(app, client):
    client.post("/auth/login", data={
        "email": "supervisor@test.com", "password": "password123"
    })
    dashboard = client.get("/supervisor/dashboard").get_data(as_text=True)
    assert "Peter Kariuki" in dashboard
    assert "Demonstration name" not in dashboard
    assert "NetEase worker 23" not in dashboard

    with app.app_context():
        owner = Supervisor.query.first()
        worker = OnboardingAgent.query.filter_by(email="netease-6376@demo.invalid").one()
        original_name = worker.name
        agent_id = worker.id
        task = Task(task_type="Alias check", location="Nairobi", priority="Medium",
                    status="Pending", supervisor_id=owner.id)
        db.session.add(task)
        db.session.flush()
        db.session.add(TaskSkill(task_id=task.id,
                                skill_id=Skill.query.filter_by(name="NetEase capability 56").one().id))
        db.session.commit()
        task_id = task.id
        ranked = NetEaseRecommendationService().get_recommendations(task_id)
        baseline = recommend_agents({"mode": "application_demo", "capability_ids": ["56"],
                                     "candidate_worker_ids": ["6376"]})
        assert ranked[0]["source_worker_id"] == baseline[0]["source_worker_id"] == "6376"
        assert ranked[0]["score"] == baseline[0]["score"]
        assert ranked[0]["agent_id"] == agent_id
        assert ranked[0]["agent_name"] == "Mary Wafula"

    page = client.get(f"/supervisor/task/{task_id}/recommendations")
    assert b"Mary Wafula" in page.data
    with client.session_transaction() as session:
        token = session["assignment_csrf_token"]
    response = client.post(f"/supervisor/task/{task_id}/assign", data={
        "agent_id": str(agent_id), "assignment_csrf_token": token
    }, follow_redirects=True)
    assert b"assigned to Mary Wafula successfully" in response.data
    with app.app_context():
        assert db.session.get(OnboardingAgent, agent_id).name == original_name
