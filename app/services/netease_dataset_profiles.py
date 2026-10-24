from app.services.worker_display_names import worker_display_name
import csv
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def load_dataset_profiles():
    project_root = Path(__file__).resolve().parents[2]
    dataset_path = (
        project_root / "ml" / "data" / "netease" / "observations.csv"
    )

    profiles = {}

    with dataset_path.open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            worker_id = row["agent_id"]

            # Keep workers without training history, but do not use
            # validation or test outcomes in their displayed history.
            profile = profiles.setdefault(
                worker_id,
                {
                    "source_worker_id": worker_id,
                    "display_name": worker_display_name(worker_id),
                    "capabilities": set(),
                    "training_tasks": set(),
                    "training_responses": 0,
                    "successful_responses": 0,
                },
            )

            if row["split"] != "train":
                continue

            profile["capabilities"].add(row["capability"])
            profile["training_tasks"].add(row["task_id"])
            profile["training_responses"] += 1
            profile["successful_responses"] += int(
                row["answer"] == row["truth"]
            )

    for profile in profiles.values():
        profile["capabilities"] = sorted(
            profile["capabilities"], key=int
        )
        profile["training_task_count"] = len(
            profile.pop("training_tasks")
        )

        total = profile["training_responses"]
        profile["training_success_rate"] = (
            100 * profile["successful_responses"] / total
            if total else None
        )

    return profiles