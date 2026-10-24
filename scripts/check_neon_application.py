"""Check the configured Flask application against Neon using read-only transactions."""
import os
import secrets
import sys
from getpass import getpass
from pathlib import Path

from sqlalchemy import event, text
from sqlalchemy.engine import make_url


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def main():
    project = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(project))
    url = make_url(getpass("Paste your Neon connection string: ").strip())
    require(url.get_backend_name() in ("postgres", "postgresql"), "PostgreSQL required.")
    require(bool(url.host) and url.host.endswith(".neon.tech"), "Neon hostname required.")
    os.environ["INTELLITASK_DATABASE_URL"] = url.set(
        drivername="postgresql+psycopg"
    ).render_as_string(hide_password=False)
    os.environ["INTELLITASK_SECRET_KEY"] = secrets.token_hex(32)

    from wsgi import app
    from app.extensions import db
    from app.models import OnboardingAgent
    from app.services.netease_recommendation_service import NetEaseRecommendationService
    from ml.src.recommender import load_artifacts

    app.config["PROPAGATE_EXCEPTIONS"] = True
    require(app.config.get("NETEASE_BINDING_STORAGE") == "database", "Database binding mode required.")
    with app.app_context():
        engine = db.engine
        engine.dispose()

        @event.listens_for(engine, "connect")
        def make_read_only(connection, connection_record):
            connection.read_only = True

        try:
            require(db.session.execute(text("SHOW transaction_read_only")).scalar() == "on",
                    "Read-only protection required.")
            print("Neon read-only connection: PASS")
            bindings, capabilities = NetEaseRecommendationService()._read_configuration()
            profiles = load_artifacts()["profiles"]
            require(set(bindings.values()) == set(profiles), "Worker mapping set differs from saved model.")
            workers = {str(worker.id): worker for worker in OnboardingAgent.query.all()}
            for database_id, source_id in bindings.items():
                worker = workers.get(database_id)
                require(worker is not None and worker.email == f"netease-{source_id}@demo.invalid",
                        "Worker identity mismatch.")
            print(f"Database worker identities verified: {len(bindings)}")
            print("Database-backed ML configuration: PASS")
            print("Capability labels:", ", ".join(sorted(capabilities)))

            email = input("Hosted supervisor email: ").strip().lower()
            password = getpass("Hosted supervisor password: ")
            with app.test_client() as client:
                response = client.post("/auth/login", base_url="https://localhost",
                                       data={"email": email, "password": password})
                with client.session_transaction(base_url="https://localhost") as session:
                    require(str(session.get("_user_id", "")).startswith("supervisor:"),
                            "Supervisor login failed.")
                print("Hosted supervisor login: PASS")
                require(any("intellitask_session=" in header and "; Secure" in header
                            and "; HttpOnly" in header and "SameSite=Lax" in header
                            for header in response.headers.getlist("Set-Cookie")),
                        "Session cookie protections missing.")
                print("Session cookie protections: PASS")
                response = client.get("/supervisor/dashboard", base_url="https://localhost")
                require(response.status_code == 200, "Authenticated dashboard failed.")
                print("Dashboard using Neon: PASS")
        finally:
            db.session.remove()
            engine.dispose()
    print("Finished. Database transactions were read-only; no records were changed.")
    print("This checks the local Flask application with Neon, not a public web server.")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"Check failed ({type(error).__name__}). Connection details hidden.")
        print("Share the last PASS line and error type, not your connection string or password.")
        raise SystemExit(1) from None
