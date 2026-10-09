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
            email="grace@test.com",
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
            email="unavailable@test.com",
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

        db.session.commit()

        yield app

        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):

    return app.test_client()


@pytest.fixture()
def runner(app):

    return app.test_cli_runner()