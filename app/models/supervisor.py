from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from app.extensions import db


class Supervisor(UserMixin, db.Model):
    __tablename__ = "supervisors"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    account_disabled = db.Column(db.Boolean, nullable=False, default=False, server_default=db.false())

    @property
    def is_active(self):
        return not self.account_disabled

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_id(self):
        from app.services.auth_session import session_id_for
        return session_id_for(self)

    @property
    def role(self):
        return "supervisor"

    def __repr__(self):
        return f"<Supervisor {self.email}>"
