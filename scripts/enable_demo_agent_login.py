import json
import sys
from getpass import getpass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app
from app.extensions import db
from app.models import OnboardingAgent

app = create_app()

with app.app_context():
    mapping_path = (
        Path(app.instance_path) / "netease_agent_bindings.json"
    )
    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))

    agent = db.session.get(OnboardingAgent, 1051)

    if (
        agent is None
        or str(mapping["worker_bindings"].get("1051")) != "6376"
        or agent.email != "netease-6376@demo.invalid"
    ):
        raise SystemExit("Agent identity check failed. No changes made.")

    print(f"Enable demonstration login for: {agent.name}")
    print(f"Email: {agent.email}")

    password = getpass("Choose a password (at least 12 characters): ")
    confirmation = getpass("Confirm password: ")

    if len(password) < 12:
        raise SystemExit("Password too short. No changes made.")

    if password != confirmation:
        raise SystemExit("Passwords do not match. No changes made.")

    agent.set_password(password)
    db.session.commit()

    print("Demonstration login enabled.")