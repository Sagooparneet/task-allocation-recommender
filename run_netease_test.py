from pathlib import Path
import secrets

from sqlalchemy.engine import URL

from app import create_app


project_root = Path(__file__).resolve().parent
test_instance = project_root / "instance" / "netease_setup_test"

required_files = [
    "task_allocation.db",
    "netease_agent_bindings.json",
    "onboarding_capability_mapping.json",
    "setup_complete.json",
]

for filename in required_files:
    if not (test_instance / filename).is_file():
        raise SystemExit(f"Missing test installation file: {filename}")

app = create_app({
    "SQLALCHEMY_DATABASE_URI": URL.create(
        "sqlite",
        database=str(test_instance / "task_allocation.db"),
    ),
    "SECRET_KEY": secrets.token_hex(32),
    "SESSION_COOKIE_NAME": "intellitask_netease_test",
})

app.instance_path = str(test_instance)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001, debug=False)