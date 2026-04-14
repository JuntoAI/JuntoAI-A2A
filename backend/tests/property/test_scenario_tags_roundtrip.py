"""Property-based test for ArenaScenario tags round-trip serialization.

Feature: persona-landing-pages
Property 3: ArenaScenario tags round-trip
"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.scenarios.models import ArenaScenario


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_tag_string = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N")),
    min_size=1, max_size=20,
)

_tags_strategy = st.one_of(
    st.none(),
    st.just([]),
    st.lists(_tag_string, min_size=1, max_size=5, unique=True),
)


def _build_scenario_with_tags(tags: list[str] | None) -> dict:
    """Build a minimal valid ArenaScenario dict with the given tags."""
    d = {
        "id": "roundtrip-test",
        "name": "Round Trip Test",
        "description": "Testing tags round-trip",
        "agents": [
            {
                "role": "Buyer", "name": "Alice", "type": "negotiator",
                "persona_prompt": "You are a buyer.", "goals": ["Buy low"],
                "budget": {"min": 100.0, "max": 200.0, "target": 150.0},
                "tone": "assertive", "output_fields": ["offer"],
                "model_id": "gemini-3-flash-preview",
            },
            {
                "role": "Seller", "name": "Bob", "type": "negotiator",
                "persona_prompt": "You are a seller.", "goals": ["Sell high"],
                "budget": {"min": 100.0, "max": 200.0, "target": 150.0},
                "tone": "firm", "output_fields": ["offer"],
                "model_id": "gemini-3-flash-preview",
            },
        ],
        "toggles": [{
            "id": "toggle_1", "label": "Secret info",
            "target_agent_role": "Buyer",
            "hidden_context_payload": {"secret": "value"},
        }],
        "negotiation_params": {
            "max_turns": 10, "agreement_threshold": 1000.0,
            "turn_order": ["Buyer", "Seller"],
        },
        "outcome_receipt": {
            "equivalent_human_time": "~2 weeks",
            "process_label": "Acquisition",
        },
    }
    if tags is not None:
        d["tags"] = tags
    return d


# ---------------------------------------------------------------------------
# Feature: persona-landing-pages
# Property 3: ArenaScenario tags round-trip
# **Validates: Requirements 4.1, 4.2**
#
# For any valid ArenaScenario instance with an arbitrary tags list (including
# None, empty list, or list of arbitrary strings), serializing to JSON via
# model_dump() and deserializing via model_validate() SHALL produce an
# equivalent ArenaScenario with identical tags.
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(tags=_tags_strategy)
def test_arena_scenario_tags_round_trip(tags):
    """model_validate(model_dump()) produces equivalent tags for any tag value."""
    data = _build_scenario_with_tags(tags)
    original = ArenaScenario.model_validate(data)

    dumped = original.model_dump()
    restored = ArenaScenario.model_validate(dumped)

    assert restored.tags == original.tags, (
        f"Tags mismatch: original={original.tags}, restored={restored.tags}"
    )
    assert restored == original
