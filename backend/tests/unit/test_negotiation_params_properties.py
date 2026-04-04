"""Property-based tests for NegotiationParams backward compatibility.

# Feature: 110_hybrid-agent-memory, Property 1: Round-trip serialization of NegotiationParams
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from app.scenarios.models import NegotiationParams

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Required fields for a valid NegotiationParams
_base_params = st.fixed_dictionaries({
    "max_turns": st.integers(min_value=1, max_value=100),
    "agreement_threshold": st.floats(
        min_value=0.01, max_value=1e9, allow_nan=False, allow_infinity=False
    ),
    "turn_order": st.lists(
        st.text(min_size=1, max_size=20), min_size=1, max_size=5
    ),
})

# Optional new fields — sometimes present, sometimes absent
_optional_new_fields = st.fixed_dictionaries(
    {},
    optional={
        "sliding_window_size": st.integers(min_value=1, max_value=50),
        "milestone_interval": st.integers(min_value=2, max_value=50),
    },
)


@st.composite
def negotiation_params_dicts(draw: st.DrawFn) -> dict:
    """Generate NegotiationParams dicts, some with new fields, some without."""
    base = draw(_base_params)
    optional = draw(_optional_new_fields)
    return {**base, **optional}


# ---------------------------------------------------------------------------
# Property 1: Round-trip serialization with and without new fields
# ---------------------------------------------------------------------------


class TestProperty1NegotiationParamsRoundTrip:
    """**Validates: Requirements 1.3, 1.4, 9.6**

    Property 1: Round-trip serialization of NegotiationParams with and without
    new fields.

    For any valid NegotiationParams dict (with or without sliding_window_size
    and milestone_interval), model_validate always succeeds, defaults are
    applied correctly, and round-trip through model_dump preserves values.
    """

    @settings(max_examples=100)
    @given(data=negotiation_params_dicts())
    def test_model_validate_always_succeeds(self, data: dict):
        params = NegotiationParams.model_validate(data)
        assert params.max_turns == data["max_turns"]
        assert params.turn_order == data["turn_order"]

    @settings(max_examples=100)
    @given(data=negotiation_params_dicts())
    def test_defaults_applied_when_fields_absent(self, data: dict):
        params = NegotiationParams.model_validate(data)

        if "sliding_window_size" in data:
            assert params.sliding_window_size == data["sliding_window_size"]
        else:
            assert params.sliding_window_size == 3

        if "milestone_interval" in data:
            assert params.milestone_interval == data["milestone_interval"]
        else:
            assert params.milestone_interval == 4

    @settings(max_examples=100)
    @given(data=negotiation_params_dicts())
    def test_round_trip_preserves_values(self, data: dict):
        params = NegotiationParams.model_validate(data)
        dumped = params.model_dump()
        restored = NegotiationParams.model_validate(dumped)
        assert restored == params
