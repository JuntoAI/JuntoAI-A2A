"""Progress percentage computation for the AI Scenario Builder."""

_SECTIONS = ("id", "name", "description", "agents", "toggles", "negotiation_params", "outcome_receipt")


def compute_progress(partial_scenario: dict) -> int:
    """Return the completion percentage (0-100) of *partial_scenario*.

    A section is "populated" when the key exists and the value is non-empty
    (non-empty string, non-empty list, non-empty dict, or any other truthy value).
    """
    count = sum(
        1
        for section in _SECTIONS
        if section in partial_scenario and partial_scenario[section]
    )
    return round((count / 7) * 100)
