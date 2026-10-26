from conftest import task_venue_fields
import datetime as _deadline_datetime

def _future_task_deadline():
    return (_deadline_datetime.datetime.now(_deadline_datetime.timezone(_deadline_datetime.timedelta(hours=3))) + _deadline_datetime.timedelta(days=7)).strftime("%Y-%m-%dT%H:%M")

from datetime import datetime, timedelta, timezone

from app.extensions import db

from app.models import (
    Supervisor,
    OnboardingAgent,
    Task,
    Skill,
    TaskSkill,
    TaskAssignment
)

from app.services.recommendation_service import HybridRecommendationService


def login_supervisor(client):

    return client.post(
        "/auth/login",
        data={
            "email": "supervisor@test.com",
            "password": "password123"
        },
        follow_redirects=True
    )


def login_agent(client, email="netease-6376@demo.invalid"):

    return client.post(
        "/auth/login",
        data={
            "email": email,
            "password": "password123"
        },
        follow_redirects=True
    )


def create_test_task(app):

    with app.app_context():

        supervisor = Supervisor.query.filter_by(
            email="supervisor@test.com"
        ).first()

        skill = Skill.query.filter_by(
            name="KYC Verification"
        ).first()

        task = Task(
            task_type="Customer KYC Verification",
            description="Verify customer identity documents",
            location="Nairobi",
            priority="High",
            status="Pending",
            supervisor_id=supervisor.id
        )

        db.session.add(task)
        db.session.flush()

        db.session.add(
            TaskSkill(
                task_id=task.id,
                skill_id=skill.id
            )
        )

        db.session.commit()

        return task.id


def test_valid_task_creation(app, client):

    login_supervisor(client)

    with app.app_context():

        skill = Skill.query.filter_by(
            name="KYC Verification"
        ).first()

        skill_id = skill.id

    response = client.post(
        "/supervisor/task/create",
        data={**task_venue_fields(client, location='Nairobi'),
            "task_type": "KYC Registration",
            "description": "Register and verify customer",
            "location": "Nairobi",
            "priority": "High",
            "deadline": (datetime.now(timezone(timedelta(hours=3))) + timedelta(days=7)).strftime("%Y-%m-%dT%H:%M"),
            "required_skills": str(skill_id)
        },
        follow_redirects=True
    )

    assert response.status_code == 200

    with app.app_context():

        task = Task.query.filter_by(
            task_type="KYC Registration"
        ).first()

        assert task is not None
        assert task.status == "Pending"

        task_skill = TaskSkill.query.filter_by(
            task_id=task.id
        ).first()

        assert task_skill is not None


def test_missing_required_task_fields(app, client):

    login_supervisor(client)

    with app.app_context():

        skill = Skill.query.first()
        skill_id = skill.id

    response = client.post(
        "/supervisor/task/create",
        data={**task_venue_fields(client, location='Nairobi'), "deadline": _future_task_deadline(),
            "task_type": "",
            "location": "Nairobi",
            "required_skills": str(skill_id)
        },
        follow_redirects=True
    )

    assert b"Task title and location are required" in response.data


def test_task_requires_skill(client):

    login_supervisor(client)

    response = client.post(
        "/supervisor/task/create",
        data={**task_venue_fields(client, location='Nairobi'), "deadline": _future_task_deadline(),
            "task_type": "KYC Verification",
            "location": "Nairobi",
            "priority": "Medium"
        },
        follow_redirects=True
    )

    assert b"Please select at least one service" in response.data


def test_invalid_deadline(app, client):

    login_supervisor(client)

    with app.app_context():

        skill = Skill.query.first()
        skill_id = skill.id

    response = client.post(
        "/supervisor/task/create",
        data={**task_venue_fields(client, location='Nairobi'),
            "task_type": "KYC Verification",
            "location": "Nairobi",
            "deadline": "invalid-date",
            "required_skills": str(skill_id)
        },
        follow_redirects=True
    )

    assert b"Please enter a valid deadline" in response.data


def test_unavailable_agents_excluded_from_recommendations(app):

    task_id = create_test_task(app)

    with app.app_context():

        unavailable_agent = OnboardingAgent.query.filter_by(
            email="netease-13495@demo.invalid"
        ).first()

        service = HybridRecommendationService()

        recommendations = service.get_recommendations(
            task_id,
            limit=5
        )

        recommended_ids = [
            recommendation["agent_id"]
            for recommendation in recommendations
        ]

        assert unavailable_agent.id not in recommended_ids

        for recommendation in recommendations:
            assert recommendation["availability"] is True


def test_successful_task_assignment(app, client):

    task_id = create_test_task(app)

    login_supervisor(client)

    with app.app_context():

        agent = OnboardingAgent.query.filter_by(
            email="netease-6376@demo.invalid"
        ).first()

        agent_id = agent.id
        initial_workload = agent.workload or 0

    response = client.post(
        f"/supervisor/task/{task_id}/assign",
        data={
            "agent_id": agent_id,
            "assignment_csrf_token": assignment_token(client, task_id)
        },
        follow_redirects=True
    )

    assert response.status_code == 200

    with app.app_context():

        task = db.session.get(
            Task,
            task_id
        )

        assignment = TaskAssignment.query.filter_by(
            task_id=task_id
        ).first()

        agent = db.session.get(
            OnboardingAgent,
            agent_id
        )

        assert assignment is not None
        assert assignment.status == "Assigned"
        assert task.status == "Assigned"

        # Workload should increase after assignment
        assert agent.workload == initial_workload + 1


def test_duplicate_assignment_prevented(app, client):

    task_id = create_test_task(app)

    login_supervisor(client)

    with app.app_context():

        agent = OnboardingAgent.query.filter_by(
            email="netease-6376@demo.invalid"
        ).first()

        agent_id = agent.id

    client.post(
        f"/supervisor/task/{task_id}/assign",
        data={
            "agent_id": agent_id,
            "assignment_csrf_token": assignment_token(client, task_id)
        },
        follow_redirects=True
    )

    response = client.post(
        f"/supervisor/task/{task_id}/assign",
        data={
            "agent_id": agent_id,
            "assignment_csrf_token": assignment_token(client, task_id)
        },
        follow_redirects=True
    )

    assert b"This task is no longer pending or already has an assignment" in response.data

    with app.app_context():

        assignment_count = TaskAssignment.query.filter_by(
            task_id=task_id
        ).count()

        assert assignment_count == 1


def test_unavailable_agent_cannot_be_assigned(app, client):

    task_id = create_test_task(app)

    login_supervisor(client)

    with app.app_context():

        agent = OnboardingAgent.query.filter_by(
            email="netease-13495@demo.invalid"
        ).first()

        agent_id = agent.id

    response = client.post(
        f"/supervisor/task/{task_id}/assign",
        data={
            "agent_id": agent_id,
            "assignment_csrf_token": assignment_token(client, task_id)
        },
        follow_redirects=True
    )

    assert b"This agent is no longer available or does not meet all mapped task requirements" in response.data

    with app.app_context():

        assignment = TaskAssignment.query.filter_by(
            task_id=task_id
        ).first()

        task = db.session.get(
            Task,
            task_id
        )

        assert assignment is None
        assert task.status == "Pending"


def test_agent_can_complete_assigned_task(app, client):

    task_id = create_test_task(app)

    with app.app_context():

        supervisor = Supervisor.query.filter_by(
            email="supervisor@test.com"
        ).first()

        agent = OnboardingAgent.query.filter_by(
            email="netease-6376@demo.invalid"
        ).first()

        task = db.session.get(
            Task,
            task_id
        )

        task.status = "Assigned"

        initial_workload = agent.workload or 0

        # Simulate an active assignment
        agent.workload = initial_workload + 1

        assignment = TaskAssignment(
            task_id=task.id,
            agent_id=agent.id,
            supervisor_id=supervisor.id,
            status="Assigned"
        )

        db.session.add(assignment)
        db.session.commit()

        assignment_id = assignment.id
        agent_id = agent.id

    login_agent(client)

    response = client.post(
        f"/agent/assignment/{assignment_id}/complete",
        follow_redirects=True
    )

    assert response.status_code == 200

    with app.app_context():

        assignment = db.session.get(
            TaskAssignment,
            assignment_id
        )

        task = db.session.get(
            Task,
            task_id
        )

        agent = db.session.get(
            OnboardingAgent,
            agent_id
        )

        assert assignment.status == "Completed"
        assert task.status == "Completed"

        # Workload should decrease after completion
        assert agent.workload == initial_workload


def test_workload_cannot_go_below_zero(app, client):

    task_id = create_test_task(app)

    with app.app_context():

        supervisor = Supervisor.query.filter_by(
            email="supervisor@test.com"
        ).first()

        agent = OnboardingAgent.query.filter_by(
            email="netease-6376@demo.invalid"
        ).first()

        task = db.session.get(
            Task,
            task_id
        )

        task.status = "Assigned"

        # Test the lower workload boundary
        agent.workload = 0

        assignment = TaskAssignment(
            task_id=task.id,
            agent_id=agent.id,
            supervisor_id=supervisor.id,
            status="Assigned"
        )

        db.session.add(assignment)
        db.session.commit()

        assignment_id = assignment.id
        agent_id = agent.id

    login_agent(client)

    response = client.post(
        f"/agent/assignment/{assignment_id}/complete",
        follow_redirects=True
    )

    assert response.status_code == 200

    with app.app_context():

        agent = db.session.get(
            OnboardingAgent,
            agent_id
        )

        assert agent.workload == 0


def test_agent_cannot_access_supervisor_dashboard(client):

    login_agent(client)

    response = client.get(
        "/supervisor/dashboard",
        follow_redirects=False
    )

    assert response.status_code == 302


def test_recommendation_output_is_valid(app):

    task_id = create_test_task(app)

    with app.app_context():

        service = HybridRecommendationService()

        recommendations = service.get_recommendations(
            task_id,
            limit=5
        )

        assert len(recommendations) > 0

        scores = []

        for recommendation in recommendations:

            assert "agent_id" in recommendation
            assert "score" in recommendation
            assert "cbf_score" in recommendation
            assert "cf_score" in recommendation
            assert "kg_score" in recommendation
            assert "decision" in recommendation
            assert "explanation" in recommendation

            assert 0 <= recommendation["score"] <= 1
            assert 0 <= recommendation["cbf_score"] <= 1
            assert 0 <= recommendation["cf_score"] <= 1
            assert 0 <= recommendation["kg_score"] <= 1

            assert recommendation["decision"] == "Supervisor review required"
            assert recommendation["source_worker_id"] == "6376"
            assert recommendation["model_weights"] == [0.1, 0.5, 0.4]

            scores.append(
                recommendation["score"]
            )

        assert scores == sorted(
            scores,
            reverse=True
        )


def test_agent_cannot_complete_another_agents_task(app, client):

    task_id = create_test_task(app)

    with app.app_context():

        supervisor = Supervisor.query.filter_by(
            email="supervisor@test.com"
        ).first()

        grace = OnboardingAgent.query.filter_by(
            email="netease-6376@demo.invalid"
        ).first()

        task = db.session.get(
            Task,
            task_id
        )

        task.status = "Assigned"

        assignment = TaskAssignment(
            task_id=task.id,
            agent_id=grace.id,
            supervisor_id=supervisor.id,
            status="Assigned"
        )

        db.session.add(assignment)
        db.session.commit()

        assignment_id = assignment.id

    login_agent(
        client,
        email="netease-13495@demo.invalid"
    )

    response = client.post(
        f"/agent/assignment/{assignment_id}/complete",
        follow_redirects=True
    )

    assert b"You are not allowed to update this assignment" in response.data

    with app.app_context():

        assignment = db.session.get(
            TaskAssignment,
            assignment_id
        )

        task = db.session.get(
            Task,
            task_id
        )

        assert assignment.status == "Assigned"
        assert task.status == "Assigned"

def assignment_token(client, task_id):
    response = client.get(f"/supervisor/task/{task_id}/recommendations")
    assert response.status_code == 200
    with client.session_transaction() as session:
        return session["assignment_csrf_token"]


def test_assignment_requires_token(app, client):
    task_id = create_test_task(app)
    login_supervisor(client)
    with app.app_context():
        worker = OnboardingAgent.query.filter_by(email="netease-6376@demo.invalid").one()
        worker_id, workload = worker.id, worker.workload
    client.post(f"/supervisor/task/{task_id}/assign", data={"agent_id": worker_id})
    with app.app_context():
        assert TaskAssignment.query.count() == 0
        assert db.session.get(Task, task_id).status == "Pending"
        assert db.session.get(OnboardingAgent, worker_id).workload == workload


def test_other_supervisor_cannot_access_or_assign(app, client):
    task_id = create_test_task(app)
    with app.app_context():
        other = Supervisor(name="Other", email="other@test.com")
        other.set_password("password123")
        db.session.add(other)
        db.session.commit()
    client.post("/auth/login", data={"email": "other@test.com", "password": "password123"})
    assert client.get(f"/supervisor/task/{task_id}/recommendations").status_code == 403
    assert client.post(f"/supervisor/task/{task_id}/assign", data={"agent_id": 1}).status_code == 403
    with app.app_context():
        assert TaskAssignment.query.count() == 0


def test_direct_source_capability_recommendation_reaches_page(app, client):
    task_id = create_test_task(app)
    with app.app_context():
        task = db.session.get(Task, task_id)
        task.task_type = "NetEase capability 56"
        link = TaskSkill.query.filter_by(task_id=task_id).one()
        link.skill_id = Skill.query.filter_by(name="NetEase capability 56").one().id
        db.session.commit()
        result = HybridRecommendationService().get_recommendations(task_id)[0]
    login_supervisor(client)
    response = client.get(f"/supervisor/task/{task_id}/recommendations")
    assert response.status_code == 200
    assert result["agent_name"].encode() in response.data
    assert f'name="agent_id" value="{result["agent_id"]}"'.encode() in response.data
    assert b'assignment_csrf_token' in response.data
