"""Toggle Injector — assembles hidden_context dicts from activated toggles."""

from typing import Any

from app.scenarios.exceptions import InvalidToggleError
from app.scenarios.models import ArenaScenario


def build_hidden_context(
    scenario: ArenaScenario,
    active_toggle_ids: list[str],
) -> dict[str, Any]:
    """Build hidden_context dict from activated toggles.

    Returns:
        Dict keyed by agent role, values are merged toggle payloads.

    Raises:
        InvalidToggleError: If a toggle_id doesn't exist in the scenario.
    """
    if not active_toggle_ids:
        return {}

    toggle_map = {t.id: t for t in scenario.toggles}
    hidden_context: dict[str, Any] = {}

    for toggle_id in active_toggle_ids:
        if toggle_id not in toggle_map:
            raise InvalidToggleError(toggle_id, scenario.id)
        toggle = toggle_map[toggle_id]
        role = toggle.target_agent_role
        if role not in hidden_context:
            hidden_context[role] = {}
        # Shallow merge — later toggles overwrite conflicting keys
        hidden_context[role].update(toggle.hidden_context_payload)

    return hidden_context
