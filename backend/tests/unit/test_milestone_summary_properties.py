"""Property-based tests for milestone summary serialization round-trip.

# Feature: 110_hybrid-agent-memory, Property 3: Round-trip consistency of
# milestone_summaries through NegotiationStateModel
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from app.models.negotiation import NegotiationStateModel

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# A single milestone summary entry: {"turn_number": int, "summary": str}
_milestone_entry = st.fixed_dictionaries({
    "turn_number": st.integers(min_value=1, max_value=200),
    "summary": st.text(min_size=0, max_size=300),
})

# A list of milestone entries for one agent role
_milestone_list = st.lists(_milestone_entry, min_size=0, max_size=10)

# Role names — short printable strings
_role_name = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N")),
    min_size=1,
    max_size=20,
)

# Full milestone_summaries dict: role -> list of entries
_milestone_summaries = st.dictionaries(
    keys=_role_name,
    values=_milestone_list,
    min_size=0,
    max_size=5,
)


# ---------------------------------------------------------------------------
# Property 3: Round-trip consistency of milestone_summaries
# ---------------------------------------------------------------------------


class TestProperty3MilestoneSummaryRoundTrip:
    """**Validates: Requirements 10.1, 10.2, 10.3**

    Property 3: Round-trip consistency of milestone_summaries through
    NegotiationStateModel.

    For any valid milestone_summaries dict with turn_number (int) and summary
    (str) entries, serializing via model_dump() and reconstructing via
    NegotiationStateModel(**data) preserves all data without loss.
    """

    @settings(max_examples=100)
    @given(milestone_summaries=_milestone_summaries)
    def test_model_dump_reconstruct_preserves_milestones(
        self, milestone_summaries: dict
    ):
        model = NegotiationStateModel(
            session_id="sess-001",
            scenario_id="test-scenario",
            milestone_summaries=milestone_summaries,
        )

        dumped = model.model_dump()
        restored = NegotiationStateModel(**dumped)

        assert restored.milestone_summaries == milestone_summaries

    @settings(max_examples=100)
    @given(milestone_summaries=_milestone_summaries)
    def test_json_round_trip_preserves_milestones(
        self, milestone_summaries: dict
    ):
        model = NegotiationStateModel(
            session_id="sess-001",
            scenario_id="test-scenario",
            milestone_summaries=milestone_summaries,
        )

        json_str = model.model_dump_json()
        restored = NegotiationStateModel.model_validate_json(json_str)

        assert restored.milestone_summaries == milestone_summaries

    @settings(max_examples=100)
    @given(milestone_summaries=_milestone_summaries)
    def test_milestone_entries_contain_only_json_serializable_types(
        self, milestone_summaries: dict
    ):
        """Verify entries contain only JSON-serializable primitives (Req 10.2)."""
        model = NegotiationStateModel(
            session_id="sess-001",
            scenario_id="test-scenario",
            milestone_summaries=milestone_summaries,
        )

        dumped = model.model_dump()
        for role, entries in dumped["milestone_summaries"].items():
            assert isinstance(role, str)
            for entry in entries:
                assert isinstance(entry["turn_number"], int)
                assert isinstance(entry["summary"], str)
