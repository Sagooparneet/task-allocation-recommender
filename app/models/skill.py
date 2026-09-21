from app.extensions import db


class Skill(db.Model):
    __tablename__ = "skills"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)

    def __repr__(self):
        return f"<Skill {self.name}>"


class AgentSkill(db.Model):
    __tablename__ = "agent_skills"

    id = db.Column(db.Integer, primary_key=True)

    agent_id = db.Column(
        db.Integer,
        db.ForeignKey("onboarding_agents.id"),
        nullable=False
    )

    skill_id = db.Column(
        db.Integer,
        db.ForeignKey("skills.id"),
        nullable=False
    )

    proficiency_level = db.Column(
        db.String(30),
        default="Intermediate"
    )

    agent = db.relationship(
        "OnboardingAgent",
        backref="agent_skills"
    )

    skill = db.relationship(
        "Skill",
        backref="agent_skills"
    )


class TaskSkill(db.Model):
    __tablename__ = "task_skills"

    id = db.Column(db.Integer, primary_key=True)

    task_id = db.Column(
        db.Integer,
        db.ForeignKey("tasks.id"),
        nullable=False
    )

    skill_id = db.Column(
        db.Integer,
        db.ForeignKey("skills.id"),
        nullable=False
    )

    skill = db.relationship(
        "Skill",
        backref="task_skills"
    )

    task = db.relationship(
        "Task",
        backref="task_skills"
    )