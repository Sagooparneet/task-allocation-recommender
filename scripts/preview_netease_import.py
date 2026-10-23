from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app
from app.models import OnboardingAgent
from ml.src.recommender import load_artifacts


def main():
    profiles = load_artifacts()["profiles"]
    planned = []

    for source_id, profile in sorted(profiles.items()):
        if profile["source_worker_id"] != source_id:
            raise ValueError(f"Source ID mismatch: {source_id}")

        planned.append({
            "source_worker_id": source_id,
            "display_id": profile["agent_id"],
            "name": profile["agent_name"],
            # Storage placeholder—not a real worker email.
            "email": f"netease-{source_id}@demo.invalid",
            "capabilities": profile["skills"],
        })

    display_ids = [row["display_id"] for row in planned]
    emails = [row["email"] for row in planned]

    if len(set(display_ids)) != len(display_ids):
        raise ValueError("Duplicate display IDs found.")

    if len(set(emails)) != len(emails):
        raise ValueError("Duplicate placeholder emails found.")

    app = create_app()

    with app.app_context():
        existing = OnboardingAgent.query.all()
        existing_emails = {agent.email.lower() for agent in existing}
        collisions = [
            row for row in planned
            if row["email"].lower() in existing_emails
        ]

        print("PREVIEW ONLY — no database changes")
        print("Existing database agents:", len(existing))
        print("NetEase profiles available:", len(planned))
        print("Placeholder email collisions:", len(collisions))

        print("\nFIRST FIVE PROPOSED PROFILES")
        for row in planned[:5]:
            print(row)

        print("\nExisting agents and assignments remain unchanged.")
        print("Names are synthetic demonstration identities.")
        print("Source worker IDs will be retained in an explicit mapping.")

        if collisions:
            print("\nSTOP: resolve collisions before importing.")
        else:
            print("\nPreview checks passed.")


if __name__ == "__main__":
    main()