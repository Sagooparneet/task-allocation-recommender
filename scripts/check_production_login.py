import os
import secrets
import sys
from getpass import getpass
from pathlib import Path

from sqlalchemy.engine import URL

project = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project))

instance = project / "instance" / "deployment_test"
database = instance / "task_allocation.db"

if not database.is_file():
    raise SystemExit("Deployment-test database not found.")

os.environ["INTELLITASK_SECRET_KEY"] = secrets.token_hex(32)
os.environ["INTELLITASK_DATABASE_URL"] = URL.create(
    "sqlite",
    database=str(database),
).render_as_string(hide_password=False)
os.environ["INTELLITASK_INSTANCE_PATH"] = str(instance)

from wsgi import app
from app.extensions import db

with app.app_context():
    if Path(db.engine.url.database).resolve() != database.resolve():
        raise SystemExit("Unexpected database selected. Test stopped.")

email = input("Deployment-test supervisor email: ").strip().lower()
password = getpass("Deployment-test supervisor password: ")

with app.test_client() as client:
    response = client.post(
        "/auth/login",
        base_url="https://localhost",
        data={"email": email, "password": password},
        follow_redirects=False,
    )

    with client.session_transaction(
        base_url="https://localhost"
    ) as session:
        user_id = session.get("_user_id", "")

    if not user_id.startswith("supervisor:"):
        raise SystemExit(
            "Login failed. Check the deployment-test credentials."
        )

    print("Supervisor login: PASS")

    cookie_headers = response.headers.getlist("Set-Cookie")
    secure_cookie = any(
        "intellitask_session=" in header
        and "; Secure" in header
        and "; HttpOnly" in header
        and "SameSite=Lax" in header
        for header in cookie_headers
    )

    if not secure_cookie:
        raise SystemExit("Session cookie protection check failed.")

    print("Session cookie protections: PASS")

    dashboard = client.get(
        "/supervisor/dashboard",
        base_url="https://localhost",
    )

    if dashboard.status_code != 200:
        raise SystemExit(
            f"Dashboard check failed: HTTP {dashboard.status_code}"
        )

    print("Authenticated supervisor dashboard: PASS")

print("Finished. No database records were changed.")