"""Pretty Printer — serializes ArenaScenario to formatted JSON."""

from app.scenarios.models import ArenaScenario


def pretty_print(scenario: ArenaScenario) -> str:
    """Serialize an ArenaScenario to a 2-space indented JSON string."""
    return scenario.model_dump_json(indent=2)
