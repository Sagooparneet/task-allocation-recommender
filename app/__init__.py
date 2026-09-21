from flask import Flask, redirect, url_for
from flask_login import current_user

from config import Config
from app.extensions import db, login_manager


def create_app():

    app = Flask(__name__)

    app.config.from_object(Config)

    db.init_app(app)
    login_manager.init_app(app)

    # Import models
    from app.models import (
        Supervisor,
        OnboardingAgent,
        Administrator
    )

    @login_manager.user_loader
    def load_user(user_id):

        try:
            role, record_id = user_id.split(":")
            record_id = int(record_id)

        except (ValueError, TypeError):
            return None

        if role == "supervisor":
            return db.session.get(
                Supervisor,
                record_id
            )

        if role == "agent":
            return db.session.get(
                OnboardingAgent,
                record_id
            )

        if role == "administrator":
            return db.session.get(
                Administrator,
                record_id
            )

        return None

    # Import blueprints
    from app.auth.routes import auth_bp
    from app.supervisor.routes import supervisor_bp
    from app.agent.routes import agent_bp
    from app.admin.routes import admin_bp

    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(supervisor_bp)
    app.register_blueprint(agent_bp)
    app.register_blueprint(admin_bp)

    @app.route("/")
    def home():

        if current_user.is_authenticated:

            if current_user.role == "supervisor":
                return redirect(
                    url_for("supervisor.dashboard")
                )

            if current_user.role == "agent":
                return redirect(
                    url_for("agent.dashboard")
                )

            if current_user.role == "administrator":
                return redirect(
                    url_for("admin.dashboard")
                )

        return redirect(
            url_for("auth.login")
        )

    return app