"""Capability compatibility from training participation, not synthetic skills."""
import math

def build_profiles(training_rows):
    profiles = {}
    for row in training_rows:
        counts = profiles.setdefault(row['agent_id'], {})
        counts[row['capability']] = counts.get(row['capability'], 0) + 1
    return profiles

def score(profile, required_capabilities):
    required = set(required_capabilities)
    if not required or not profile:
        return 0.0
    # Cosine similarity of log participation counts and multi-hot task requirements.
    vector = {c: math.log1p(n) for c, n in profile.items()}
    norm = math.sqrt(sum(v*v for v in vector.values()))
    return sum(vector.get(c, 0) for c in required) / (norm * math.sqrt(len(required))) if norm else 0.0
