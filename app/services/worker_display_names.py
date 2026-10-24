"""Demonstration aliases only; never used for identity, eligibility or scoring."""
import json
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType


@lru_cache(maxsize=1)
def _names():
    path = Path(__file__).resolve().parents[2] / "ml/models/netease/display_profiles.json"
    with path.open(encoding="utf-8") as stream:
        profiles = json.load(stream)
    names = {}
    for source_id, profile in profiles.items():
        name = profile.get("agent_name")
        if str(profile.get("source_worker_id")) != source_id or not isinstance(name, str) or not name.strip():
            raise ValueError("Invalid demonstration name mapping.")
        names[source_id] = name.strip()
    if len(set(names.values())) != len(names):
        raise ValueError("Demonstration names must be unique within this dataset.")
    return MappingProxyType(names)


def worker_display_name(source_worker_id):
    """Look up an alias using an explicit source ID, never a database ID."""
    try:
        return _names()[str(source_worker_id)]
    except KeyError:
        raise ValueError("No demonstration name for this source worker.") from None
