from datetime import datetime, timedelta

from app import create_app
from app.extensions import db

from app.models import (
    Supervisor,
    OnboardingAgent,
    Administrator,
    Task,
    Skill,
    AgentSkill,
    TaskSkill,
)


app = create_app()


with app.app_context():

    # Create all database tables
    db.create_all()

    # Avoid inserting duplicate seed data
    if Supervisor.query.first():
        print("Database already contains seed data.")
        exit()

    # -------------------------
    # Supervisor
    # -------------------------

    supervisor = Supervisor(
        name="Jane Wanjiku",
        email="supervisor@example.com",
    )
    supervisor.set_password("password123")

    db.session.add(supervisor)

    # -------------------------
    # Administrator
    # -------------------------

    administrator = Administrator(
        name="System Administrator",
        email="admin@example.com",
    )
    administrator.set_password("password123")

    db.session.add(administrator)

    # -------------------------
    # Onboarding Agents
    # -------------------------

    agent1 = OnboardingAgent(
        name="Grace Achieng",
        email="grace@example.com",
        specialization="KYC Verification",
        location="Nairobi",
        availability=True,
        workload=2,
        performance_score=88.0,
    )
    agent1.set_password("password123")

    agent2 = OnboardingAgent(
        name="Brian Mwangi",
        email="brian@example.com",
        specialization="SIM Registration",
        location="Nairobi",
        availability=True,
        workload=1,
        performance_score=84.0,
    )
    agent2.set_password("password123")

    agent3 = OnboardingAgent(
        name="Amina Hassan",
        email="amina@example.com",
        specialization="M-PESA Onboarding",
        location="Mombasa",
        availability=True,
        workload=3,
        performance_score=91.0,
    )
    agent3.set_password("password123")

    agent4 = OnboardingAgent(
        name="Kevin Kiptoo",
        email="kevin@example.com",
        specialization="Account Activation",
        location="Nakuru",
        availability=False,
        workload=2,
        performance_score=80.0,
    )
    agent4.set_password("password123")

    db.session.add_all([
        agent1,
        agent2,
        agent3,
        agent4,
    ])

    # Save first so IDs are generated
    db.session.flush()

    # -------------------------
    # Skills
    # -------------------------

    kyc_skill = Skill(name="KYC Verification")
    sim_skill = Skill(name="SIM Registration")
    mpesa_skill = Skill(name="M-PESA Onboarding")
    account_skill = Skill(name="Account Activation")
    customer_skill = Skill(name="Customer Service")

    db.session.add_all([
        kyc_skill,
        sim_skill,
        mpesa_skill,
        account_skill,
        customer_skill,
    ])

    db.session.flush()

    # -------------------------
    # Agent Skills
    # -------------------------

    agent_skills = [

        AgentSkill(
            agent_id=agent1.id,
            skill_id=kyc_skill.id,
            proficiency_level="Advanced",
        ),

        AgentSkill(
            agent_id=agent1.id,
            skill_id=customer_skill.id,
            proficiency_level="Advanced",
        ),

        AgentSkill(
            agent_id=agent2.id,
            skill_id=sim_skill.id,
            proficiency_level="Advanced",
        ),

        AgentSkill(
            agent_id=agent2.id,
            skill_id=customer_skill.id,
            proficiency_level="Intermediate",
        ),

        AgentSkill(
            agent_id=agent3.id,
            skill_id=mpesa_skill.id,
            proficiency_level="Advanced",
        ),

        AgentSkill(
            agent_id=agent3.id,
            skill_id=kyc_skill.id,
            proficiency_level="Intermediate",
        ),

        AgentSkill(
            agent_id=agent4.id,
            skill_id=account_skill.id,
            proficiency_level="Advanced",
        ),
    ]

    db.session.add_all(agent_skills)

    # -------------------------
    # Tasks
    # -------------------------

    task1 = Task(
        task_type="KYC Verification",
        description="Verify customer identity documents for account onboarding.",
        location="Nairobi",
        priority="High",
        deadline=datetime.now() + timedelta(days=2),
        status="Pending",
        supervisor_id=supervisor.id,
    )

    task2 = Task(
        task_type="SIM Registration",
        description="Register and verify a new telecommunications customer.",
        location="Nairobi",
        priority="Medium",
        deadline=datetime.now() + timedelta(days=3),
        status="Pending",
        supervisor_id=supervisor.id,
    )

    task3 = Task(
        task_type="M-PESA Onboarding",
        description="Assist a customer with M-PESA service onboarding.",
        location="Mombasa",
        priority="High",
        deadline=datetime.now() + timedelta(days=1),
        status="Pending",
        supervisor_id=supervisor.id,
    )

    task4 = Task(
        task_type="Account Activation",
        description="Complete digital account activation for a new customer.",
        location="Nakuru",
        priority="Medium",
        deadline=datetime.now() + timedelta(days=4),
        status="Pending",
        supervisor_id=supervisor.id,
    )

    db.session.add_all([
        task1,
        task2,
        task3,
        task4,
    ])

    db.session.flush()

    # -------------------------
    # Task Skills
    # -------------------------

    task_skills = [

        TaskSkill(
            task_id=task1.id,
            skill_id=kyc_skill.id,
        ),

        TaskSkill(
            task_id=task2.id,
            skill_id=sim_skill.id,
        ),

        TaskSkill(
            task_id=task3.id,
            skill_id=mpesa_skill.id,
        ),

        TaskSkill(
            task_id=task4.id,
            skill_id=account_skill.id,
        ),
    ]

    db.session.add_all(task_skills)

    # Save everything
    db.session.commit()

    print("Database created and seeded successfully.")