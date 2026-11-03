import json
import pytest

from app import create_app
from app.extensions import db

from app.models import (
    Supervisor,
    OnboardingAgent,
    Administrator,
    Skill,
    AgentSkill
)


@pytest.fixture()
def app(tmp_path):

    test_database = tmp_path / "test.db"

    app = create_app({
        "TESTING": True,
        "SECRET_KEY": "test-secret-key",
        "SQLALCHEMY_DATABASE_URI":
            f"sqlite:///{test_database}"
    })

    app.instance_path = str(tmp_path)

    with app.app_context():

        db.create_all()

        # -------------------------
        # Supervisor
        # -------------------------

        supervisor = Supervisor(
            name="Test Supervisor",
            email="supervisor@test.com"
        )

        supervisor.set_password(
            "password123"
        )


        # -------------------------
        # Administrator
        # -------------------------

        administrator = Administrator(
            name="Test Administrator",
            email="admin@test.com"
        )

        administrator.set_password(
            "password123"
        )


        # -------------------------
        # Agents
        # -------------------------

        agent1 = OnboardingAgent(
            name="Grace Test",
            email="netease-6376@demo.invalid",
            specialization="KYC Verification",
            location="Nairobi",
            availability=True,
            workload=1,
            performance_score=88.0
        )

        agent1.set_password(
            "password123"
        )


        agent2 = OnboardingAgent(
            name="Unavailable Agent",
            email="netease-13495@demo.invalid",
            specialization="KYC Verification",
            location="Nairobi",
            availability=False,
            workload=0,
            performance_score=95.0
        )

        agent2.set_password(
            "password123"
        )


        db.session.add_all([
            supervisor,
            administrator,
            agent1,
            agent2
        ])

        db.session.flush()


        # -------------------------
        # Skills
        # -------------------------

        kyc_skill = Skill(
            name="KYC Verification"
        )

        customer_skill = Skill(
            name="Customer Service"
        )

        db.session.add_all([
            kyc_skill,
            customer_skill
        ])

        db.session.flush()


        # -------------------------
        # Agent Skills
        # -------------------------

        db.session.add_all([

            AgentSkill(
                agent_id=agent1.id,
                skill_id=kyc_skill.id,
                proficiency_level="Advanced"
            ),

            AgentSkill(
                agent_id=agent1.id,
                skill_id=customer_skill.id,
                proficiency_level="Advanced"
            ),

            AgentSkill(
                agent_id=agent2.id,
                skill_id=kyc_skill.id,
                proficiency_level="Advanced"
            )
        ])

        source_skill = Skill(name="NetEase capability 56")
        db.session.add(source_skill)
        db.session.flush()
        for agent in (agent1, agent2):
            db.session.add(AgentSkill(agent_id=agent.id, skill_id=source_skill.id,
                                     proficiency_level="Observed participation"))
        (tmp_path / "netease_agent_bindings.json").write_text(json.dumps({
            "schema_version": 1, "status": "ready",
            "worker_bindings": {str(agent1.id): "6376", str(agent2.id): "13495"}
        }), encoding="utf-8")
        (tmp_path / "onboarding_capability_mapping.json").write_text(json.dumps({
            "schema_version": 1,
            "skill_to_capabilities": {"KYC Verification": ["56"], "NetEase capability 56": ["56"]}
        }), encoding="utf-8")
        db.session.commit()

        yield app

        db.session.remove()
        db.drop_all()
        db.engine.dispose()


@pytest.fixture()
def client(app):

    return app.test_client()


@pytest.fixture()
def runner(app):

    return app.test_cli_runner()

def task_venue_fields(client, location="Nairobi"):
    """Supply a real form token and a disposable test venue for task POSTs."""
    from app.models import WorkVenue
    city = location if location in ('Nairobi', 'Mombasa', 'Kisumu', 'Nakuru', 'Eldoret') else 'Nairobi'
    with client.application.app_context():
        venue = WorkVenue.query.filter_by(city=city, is_active=True).first()
        if venue is None:
            venue = WorkVenue(city=city, name='Test service point', address='Test address')
            db.session.add(venue)
            db.session.commit()
        venue_id = venue.id
    client.get('/supervisor/task/create')
    with client.session_transaction() as session:
        token = session['task_create_csrf_token']
    return dict(venue_id=str(venue_id), reporting_point='Test reception', task_create_csrf_token=token)


@pytest.fixture()
def legacy_setup_code(monkeypatch):
    """Keep older invitation lifecycle tests focused on invitation redemption.

    The real email-code checks are exercised in test_setup_email_verification.
    """
    import app.auth.setup_flow as flow
    monkeypatch.setattr(flow, 'check_verification_code', lambda role, token, email, code: None)
