"""Property-based tests for persona-based scenario filtering.

Feature: persona-landing-pages
Uses Hypothesis to verify filtering correctness and sort order preservation.
"""

import json

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.scenarios.models import ArenaScenario, DIFFICULTY_ORDER
from app.scenarios.registry import ScenarioRegistry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VALID_DIFFICULTIES = list(DIFFICULTY_ORDER.keys())
_VALID_CATEGORIES = ["Corporate", "Sales", "Community", "General", "Everyday"]


def _build_scenario_dict(
    scenario_id: str,
    name: str = "Test",
    category: str = "General",
    difficulty: str = "intermediate",
    tags: list[str] | None = None,
) -> dict:
    """Build a minimal valid ArenaScenario dict with configurable tags."""
    d = {
        "id": scenario_id,
        "name": name,
        "description": f"Desc for {scenario_id}",
        "category": category,
        "difficulty": difficulty,
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


def _write_scenario(directory, filename, data):
    path = directory / filename
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

_persona_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N")),
    min_size=1, max_size=15,
)

_tag_list_strategy = st.one_of(
    st.none(),
    st.lists(_persona_strategy, min_size=0, max_size=5, unique=True),
)

_scenario_entry_strategy = st.fixed_dictionaries({
    "id": st.text(
        alphabet=st.characters(whitelist_categories=("L", "N")),
        min_size=1, max_size=15,
    ),
    "category": st.sampled_from(_VALID_CATEGORIES),
    "difficulty": st.sampled_from(_VALID_DIFFICULTIES),
    "tags": _tag_list_strategy,
})


# ---------------------------------------------------------------------------
# Feature: persona-landing-pages
# Property 1: Persona filtering correctness
# **Validates: Requirements 3.1, 3.2, 3.5, 3.6, 4.4**
#
# For any persona value P and for any list of scenarios with arbitrary tag
# combinations, filtering by persona P SHALL return only scenarios where
# either (a) the scenario has no tags (tags is None) or (b) P is contained
# in the scenario's tags list. No scenario whose tags list exists and does
# not contain P shall appear in the filtered result.
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(
    scenarios=st.lists(_scenario_entry_strategy, min_size=1, max_size=10, unique_by=lambda e: e["id"]),
    persona=_persona_strategy,
)
def test_persona_filtering_correctness(scenarios, persona, tmp_path_factory):
    """Every returned scenario has tags=None or persona in tags; excluded ones don't match."""
    tmp_dir = tmp_path_factory.mktemp("pf")

    for entry in scenarios:
        data = _build_scenario_dict(
            scenario_id=entry["id"],
            name=f"S_{entry['id']}",
            category=entry["category"],
            difficulty=entry["difficulty"],
            tags=entry["tags"],
        )
        _write_scenario(tmp_dir, f"{entry['id']}.scenario.json", data)

    registry = ScenarioRegistry(scenarios_dir=str(tmp_dir))
    result = registry.list_scenarios(persona=persona)
    result_ids = {r["id"] for r in result}

    # Assert: every returned scenario has tags=None or persona in tags
    for r in result:
        assert r["tags"] is None or persona in r["tags"], (
            f"Scenario {r['id']} returned with tags={r['tags']} "
            f"but persona={persona!r} not in tags"
        )

    # Assert: no excluded scenario should have matching tags
    for entry in scenarios:
        if entry["id"] not in result_ids:
            assert entry["tags"] is not None and persona not in entry["tags"], (
                f"Scenario {entry['id']} excluded but tags={entry['tags']} "
                f"should have been included for persona={persona!r}"
            )


# ---------------------------------------------------------------------------
# Feature: persona-landing-pages
# Property 2: Category sort order preserved after persona filtering
# **Validates: Requirements 3.4, 4.6**
#
# For any persona filter applied to any list of scenarios, the resulting
# filtered list SHALL maintain category-based grouping where categories
# appear in alphabetical order with "General" always last, and within each
# category, scenarios are ordered by difficulty then name.
# ---------------------------------------------------------------------------


def _expected_sort_key(entry: dict) -> tuple:
    """Mirror the registry's sort key for verification."""
    cat = entry["category"]
    cat_key = (1, cat) if cat == "General" else (0, cat)
    diff_key = DIFFICULTY_ORDER.get(entry["difficulty"], 1)
    return (*cat_key, diff_key, entry["name"])


@settings(max_examples=100)
@given(
    scenarios=st.lists(_scenario_entry_strategy, min_size=1, max_size=10, unique_by=lambda e: e["id"]),
    persona=st.one_of(st.none(), _persona_strategy),
)
def test_category_sort_order_preserved_after_filtering(scenarios, persona, tmp_path_factory):
    """Filtered results maintain category-alphabetical (General last), difficulty, name order."""
    tmp_dir = tmp_path_factory.mktemp("sort")

    for entry in scenarios:
        data = _build_scenario_dict(
            scenario_id=entry["id"],
            name=f"S_{entry['id']}",
            category=entry["category"],
            difficulty=entry["difficulty"],
            tags=entry["tags"],
        )
        _write_scenario(tmp_dir, f"{entry['id']}.scenario.json", data)

    registry = ScenarioRegistry(scenarios_dir=str(tmp_dir))
    result = registry.list_scenarios(persona=persona)

    # Verify the result is sorted correctly
    expected_order = sorted(result, key=_expected_sort_key)
    assert [r["id"] for r in result] == [r["id"] for r in expected_order], (
        f"Sort order violated. Got: {[r['id'] for r in result]}, "
        f"Expected: {[r['id'] for r in expected_order]}"
    )
