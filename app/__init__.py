from flask import Flask, redirect, url_for, session
from flask_login import current_user

from config import Config
from app.extensions import db, login_manager, migrate


def create_app(test_config=None):

    app = Flask(__name__)

    from app.services.skill_display_labels import skill_label, skill_explanation
    app.add_template_filter(skill_label, "skill_label")
    app.add_template_filter(skill_explanation, "skill_explanation")

    app.config.from_object(Config)

    if test_config:
        app.config.update(test_config)

    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)

    @app.context_processor
    def account_display_context():
        if current_user.is_authenticated:
            from app.services.account_display_name import account_display_name
            return {"account_display_name": account_display_name(current_user)}
        return {}

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
            worker = db.session.get(OnboardingAgent, record_id, populate_existing=True)
            if worker is not None and worker.account_disabled:
                # Revoke the browser session when its account is deactivated.
                for key in ('_user_id', '_fresh', '_id'):
                    session.pop(key, None)
                session['_remember'] = 'clear'
                return None
            return worker

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