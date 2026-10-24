"""User-approved demonstration labels; these do not rename source data or features."""
import re
from types import MappingProxyType


SKILL_LABELS = MappingProxyType({
    "50": "SIM Registration",
    "53": "M-PESA Onboarding",
    "56": "KYC Verification",
    "69": "Account Activation",
})


def skill_label(value):
    text = str(value)
    code = text.removeprefix("NetEase capability ")
    return SKILL_LABELS.get(code, text)


def skill_explanation(value):
    """Operational explanations; provenance and technical details live in README."""
    text = str(value)
    if text.startswith(("Demonstration mapping:", "Display name and location")):
        return ""
    if text.startswith("Training participation supports"):
        return "Related past task history contributes to this recommendation."
    if text.startswith("No training participation recorded"):
        return "There is limited past task history for this requirement."
    outcomes = re.fullmatch(r"Recorded training outcomes for this capability: (\d+)/(\d+) successful\.", text)
    if outcomes:
        good, total = outcomes.groups()
        if total == "0":
            return "No past results are available for this requirement."
        return f"Successful past responses for this requirement: {good} out of {total}."
    if text.startswith("Knowledge graph links"):
        return "Completed related tasks provide additional evidence."
    neighbors = re.fullmatch(r"Graph co-participation links to (\d+) training workers contribute a neighbor prior\.", text)
    if neighbors:
        return f"Shared task history with {neighbors.group(1)} other workers contributes to the ranking."
    return ""
