from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from app.extensions import db


class OnboardingAgent(UserMixin, db.Model):
    __tablename__ = "onboarding_agents"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    specialization = db.Column(db.String(100))
    location = db.Column(db.String(100))
    availability = db.Column(db.Boolean, default=True)
    workload = db.Column(db.Integer, default=0)
    performance_score = db.Column(db.Float, default=0.0)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_id(self):
        return f"agent:{self.id}"

    @property
    def role(self):
        return "agent"

    def __repr__(self):
        return f"<OnboardingAgent {self.email}>"