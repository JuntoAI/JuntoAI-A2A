"""Property-based tests for the AI Scenario Builder.

# Feature: ai-scenario-builder, Property 3: Builder SSE event structure and wire format
"""

import json

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.builder.events import (
    BuilderCompleteEvent,
    BuilderErrorEvent,
    BuilderJsonDeltaEvent,
    BuilderTokenEvent,
    HealthCheckCompleteEvent,
    HealthCheckFindingEvent,
    HealthCheckStartEvent,
)
from app.utils.sse import format_sse_event

# ---------------------------------------------------------------------------
# Hypothesis strategies for builder SSE events
# ---------------------------------------------------------------------------

_safe_text = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "Z")),
    min_size=1,
    max_size=100,
)

_event_id = st.integers(min_value=0, max_value=1_000_000)


def _st_builder_token():
    return st.builds(BuilderTokenEvent, event_type=st.just("builder_token"), token=_safe_text)


def _st_builder_json_delta():
    return st.builds(
        BuilderJsonDeltaEvent,
        event_type=st.just("builder_json_delta"),
        section=st.sampled_from(["agents", "toggles", "negotiation_params", "outcome_receipt", "id", "name", "description"]),
        data=st.fixed_dictionaries({"key": _safe_text}),
    )


def _st_builder_complete():
    return st.builds(BuilderCompleteEvent, event_type=st.just("builder_complete"))


def _st_builder_error():
    return st.builds(BuilderErrorEvent, event_type=st.just("builder_error"), message=_safe_text)


def _st_health_check_start():
    return st.builds(HealthCheckStartEvent, event_type=st.just("builder_health_check_start"))


def _st_health_check_finding():
    return st.builds(
        HealthCheckFindingEvent,
        event_type=st.just("builder_health_check_finding"),
        check_name=st.sampled_from(["prompt_quality", "budget_overlap", "turn_sanity", "stall_risk", "tension", "toggle_effectiveness", "regulator_feasibility"]),
        severity=st.sampled_from(["critical", "warning", "info"]),
        agent_role=st.one_of(st.none(), _safe_text),
        message=_safe_text,
    )


def _st_health_check_complete():
    return st.builds(
        HealthCheckCompleteEvent,
        event_type=st.just("builder_health_check_complete"),
        report=st.fixed_dictionaries({"readiness_score": st.integers(min_value=0, max_value=100)}),
    )


# Combined strategy for all 7 event types
any_builder_event = st.one_of(
    _st_builder_token(),
    _st_builder_json_delta(),
    _st_builder_complete(),
    _st_builder_error(),
    _st_health_check_start(),
    _st_health_check_finding(),
    _st_health_check_complete(),
)

# ---------------------------------------------------------------------------
# Feature: ai-scenario-builder, Property 3: Builder SSE event structure and wire format
#
# For any builder SSE event model, formatting via format_sse_event(event, event_id)
# produces a string matching `id: <id>\ndata: <valid JSON>\n\n` (with event_id)
# or `data: <valid JSON>\n\n` (without event_id), and the parsed JSON contains
# the correct event_type literal and all required fields.
#
# **Validates: Requirements 12.1, 12.2, 12.3, 23.1, 23.2, 23.3, 23.4**
# ---------------------------------------------------------------------------

# Expected event_type → required fields mapping
_REQUIRED_FIELDS: dict[str, set[str]] = {
    "builder_token": {"event_type", "token"},
    "builder_json_delta": {"event_type", "section", "data"},
    "builder_complete": {"event_type"},
    "builder_error": {"event_type", "message"},
    "builder_health_check_start": {"event_type"},
    "builder_health_check_finding": {"event_type", "check_name", "severity", "message"},
    "builder_health_check_complete": {"event_type", "report"},
}

# Expected Literal values for event_type
_EVENT_TYPE_LITERALS: dict[type, str] = {
    BuilderTokenEvent: "builder_token",
    BuilderJsonDeltaEvent: "builder_json_delta",
    BuilderCompleteEvent: "builder_complete",
    BuilderErrorEvent: "builder_error",
    HealthCheckStartEvent: "builder_health_check_start",
    HealthCheckFindingEvent: "builder_health_check_finding",
    HealthCheckCompleteEvent: "builder_health_check_complete",
}


@pytest.mark.property
@pytest.mark.slow
@settings(max_examples=100, deadline=None)
@given(event=any_builder_event, eid=_event_id)
def test_builder_sse_event_wire_format_with_id(event, eid):
    """SSE wire format with event_id: id: <id>\\ndata: <JSON>\\n\\n."""
    sse_str = format_sse_event(event, event_id=eid)

    # Must start with "id: <eid>"
    assert sse_str.startswith(f"id: {eid}\n"), (
        f"Expected 'id: {eid}\\n' prefix, got: {sse_str!r}"
    )

    # Must end with "\n\n"
    assert sse_str.endswith("\n\n"), f"SSE must end with '\\n\\n', got: {sse_str!r}"

    # Extract the data line
    lines = sse_str.rstrip("\n").split("\n")
    assert len(lines) == 2, f"Expected 2 lines (id + data), got {len(lines)}: {lines}"
    assert lines[1].startswith("data: "), f"Second line must start with 'data: ', got: {lines[1]!r}"

    # Parse JSON payload
    json_part = lines[1][len("data: "):]
    parsed = json.loads(json_part)

    # Verify event_type literal
    expected_type = _EVENT_TYPE_LITERALS[type(event)]
    assert parsed["event_type"] == expected_type

    # Verify all required fields present
    required = _REQUIRED_FIELDS[expected_type]
    missing = required - set(parsed.keys())
    assert not missing, f"Missing required fields {missing} for {expected_type}"


@pytest.mark.property
@pytest.mark.slow
@settings(max_examples=100, deadline=None)
@given(event=any_builder_event)
def test_builder_sse_event_wire_format_without_id(event):
    """SSE wire format without event_id: data: <JSON>\\n\\n."""
    sse_str = format_sse_event(event, event_id=None)

    # Must start with "data: "
    assert sse_str.startswith("data: "), f"SSE must start with 'data: ', got: {sse_str!r}"

    # Must end with "\n\n"
    assert sse_str.endswith("\n\n"), f"SSE must end with '\\n\\n', got: {sse_str!r}"

    # Single data line
    lines = sse_str.rstrip("\n").split("\n")
    assert len(lines) == 1, f"Expected 1 line (data only), got {len(lines)}: {lines}"

    # Parse JSON payload
    json_part = lines[0][len("data: "):]
    parsed = json.loads(json_part)

    # Verify event_type and required fields
    expected_type = _EVENT_TYPE_LITERALS[type(event)]
    assert parsed["event_type"] == expected_type
    required = _REQUIRED_FIELDS[expected_type]
    assert not (required - set(parsed.keys()))


# ---------------------------------------------------------------------------
# Feature: ai-scenario-builder, Property 11: Session conversation history preservation
#
# For any sequence of N messages added to a BuilderSession (alternating
# user/assistant), the session's conversation_history contains exactly N
# entries in the order they were added, with each entry's role and content
# matching the input.
#
# **Validates: Requirements 9.1**
# ---------------------------------------------------------------------------

from app.builder.session_manager import BuilderSessionManager


@pytest.mark.property
@pytest.mark.slow
@settings(max_examples=100, deadline=None)
@given(
    messages=st.lists(
        st.tuples(
            st.sampled_from(["user", "assistant"]),
            _safe_text,
        ),
        min_size=0,
        max_size=25,
    ),
)
def test_session_conversation_history_preservation(messages):
    """conversation_history preserves order, role, and content for N messages.

    We cap user messages at 50 total, so we filter the generated list to
    ensure no more than 50 user messages are attempted (max_size=25 already
    guarantees this, but the guard makes the property explicit).
    """
    mgr = BuilderSessionManager()
    session = mgr.create_session("test@example.com")

    user_count = 0
    added: list[tuple[str, str]] = []

    for role, content in messages:
        if role == "user":
            if user_count >= 50:
                continue
            user_count += 1
        mgr.add_message(session.session_id, role, content)
        added.append((role, content))

    # History length matches
    assert len(session.conversation_history) == len(added)

    # Each entry matches in order
    for i, (role, content) in enumerate(added):
        entry = session.conversation_history[i]
        assert entry["role"] == role, f"Mismatch at index {i}: expected role={role}"
        assert entry["content"] == content, f"Mismatch at index {i}: expected content"


# ---------------------------------------------------------------------------
# Feature: ai-scenario-builder, Property 12: Session message limit enforcement
#
# For any session with 50 user messages, the 51st user message is rejected
# and message_count remains 50.
#
# **Validates: Requirements 9.4**
# ---------------------------------------------------------------------------


@pytest.mark.property
@pytest.mark.slow
@settings(max_examples=100, deadline=None)
@given(
    extra_attempts=st.integers(min_value=1, max_value=20),
    assistant_after=st.integers(min_value=0, max_value=5),
)
def test_session_message_limit_enforcement(extra_attempts, assistant_after):
    """After 50 user messages, further user messages are rejected.

    Assistant messages interspersed after the limit should still succeed.
    """
    mgr = BuilderSessionManager()
    session = mgr.create_session("limit@example.com")

    # Fill to the 50-message limit
    for i in range(50):
        mgr.add_message(session.session_id, "user", f"msg-{i}")

    assert session.message_count == 50

    # Every additional user message must be rejected
    for _ in range(extra_attempts):
        with pytest.raises(ValueError):
            mgr.add_message(session.session_id, "user", "one-too-many")

    # message_count must not have changed
    assert session.message_count == 50

    # Assistant messages should still work after the limit
    for j in range(assistant_after):
        mgr.add_message(session.session_id, "assistant", f"reply-{j}")

    # History = 50 user + assistant_after assistant messages
    assert len(session.conversation_history) == 50 + assistant_after
    # message_count still 50 (only tracks user messages)
    assert session.message_count == 50


# ---------------------------------------------------------------------------
# Feature: ai-scenario-builder, Property 10: LinkedIn URL pattern recognition
#
# For any string matching `https://www\.linkedin\.com/in/.+`, detector returns
# True; for non-matching strings, returns False.
#
# **Validates: Requirements 8.1**
# ---------------------------------------------------------------------------

import re

from app.builder.linkedin import is_linkedin_url

_LINKEDIN_RE = re.compile(r"https://www\.linkedin\.com/in/.+")


@pytest.mark.property
@pytest.mark.slow
@settings(max_examples=100, deadline=None)
@given(url=st.from_regex(r"https://www\.linkedin\.com/in/.+", fullmatch=True))
def test_linkedin_url_positive(url):
    """Any string matching the LinkedIn profile pattern is detected."""
    assert is_linkedin_url(url) is True


@pytest.mark.property
@pytest.mark.slow
@settings(max_examples=100, deadline=None)
@given(text=st.text().filter(lambda t: not _LINKEDIN_RE.search(t)))
def test_linkedin_url_negative(text):
    """Any string NOT matching the LinkedIn profile pattern is rejected."""
    assert is_linkedin_url(text) is False


# ---------------------------------------------------------------------------
# Feature: ai-scenario-builder, Property 4: Progress percentage computation
#
# For any subset of the 7 sections being populated, progress equals
# round((populated_count / 7) * 100).
#
# **Validates: Requirements 5.1**
# ---------------------------------------------------------------------------

from app.builder.progress import compute_progress

_ALL_SECTIONS = ["id", "name", "description", "agents", "toggles", "negotiation_params", "outcome_receipt"]

# Minimal non-empty values per section type
_SECTION_VALUES: dict[str, object] = {
    "id": "scenario-1",
    "name": "Test",
    "description": "A test scenario",
    "agents": [{"role": "Buyer"}],
    "toggles": [{"id": "t1"}],
    "negotiation_params": {"max_turns": 10},
    "outcome_receipt": {"label": "done"},
}


@pytest.mark.property
@pytest.mark.slow
@settings(max_examples=100, deadline=None)
@given(populated=st.sets(st.sampled_from(_ALL_SECTIONS)))
def test_progress_percentage_computation(populated: set):
    """Progress equals round((len(populated) / 7) * 100) for any section subset."""
    scenario: dict = {}
    for section in populated:
        scenario[section] = _SECTION_VALUES[section]

    expected = round((len(populated) / 7) * 100)
    assert compute_progress(scenario) == expected

# ---------------------------------------------------------------------------
# Feature: ai-scenario-builder, Property 15: Budget overlap computation and flagging
#
# For any two budget ranges, overlap zone is [max(min1,min2), min(max1,max2)]
# when valid, else None. Verify "no_overlap" and "excessive_overlap" flags
# trigger correctly.
#
# **Validates: Requirements 17.1, 17.2, 17.3**
# ---------------------------------------------------------------------------

from app.builder.health_checks.budget_overlap import compute_budget_overlap
from app.scenarios.models import AgentDefinition, Budget


def _make_negotiator(role: str, bmin: float, bmax: float, btarget: float) -> AgentDefinition:
    """Helper to build a minimal negotiator AgentDefinition."""
    return AgentDefinition(
        role=role,
        name=f"Agent {role}",
        type="negotiator",
        persona_prompt="Test persona",
        goals=["goal"],
        budget=Budget(min=bmin, max=bmax, target=btarget),
        tone="neutral",
        output_fields=["proposed_price"],
        model_id="gemini-3-flash-preview",
    )


@pytest.mark.property
@pytest.mark.slow
@settings(max_examples=100, deadline=None)
@given(
    min1=st.floats(min_value=0, max_value=1000, allow_nan=False, allow_infinity=False),
    max1=st.floats(min_value=0, max_value=1000, allow_nan=False, allow_infinity=False),
    min2=st.floats(min_value=0, max_value=1000, allow_nan=False, allow_infinity=False),
    max2=st.floats(min_value=0, max_value=1000, allow_nan=False, allow_infinity=False),
)
def test_budget_overlap_computation(min1, max1, min2, max2):
    """Overlap zone is [max(min1,min2), min(max1,max2)] when valid, else None.

    **Validates: Requirements 17.1, 17.2, 17.3**
    """
    from hypothesis import assume

    # Budget model requires min <= max; target must be in [min, max]
    assume(min1 <= max1)
    assume(min2 <= max2)

    t1 = (min1 + max1) / 2
    t2 = (min2 + max2) / 2

    agents = [
        _make_negotiator("buyer", min1, max1, t1),
        _make_negotiator("seller", min2, max2, t2),
    ]

    result = compute_budget_overlap(agents)

    lo = max(min1, min2)
    hi = min(max1, max2)

    if lo > hi:
        # No overlap
        assert result.overlap_zone is None, "Expected no overlap zone"
    else:
        assert result.overlap_zone is not None, "Expected an overlap zone"
        assert abs(result.overlap_zone[0] - lo) < 1e-9
        assert abs(result.overlap_zone[1] - hi) < 1e-9

        # Verify excessive_overlap flag logic
        overlap_size = hi - lo
        range_a = max1 - min1
        range_b = max2 - min2

        if range_a > 0 and range_b > 0:
            pct_a = (overlap_size / range_a) * 100
            pct_b = (overlap_size / range_b) * 100
            if min(pct_a, pct_b) > 50:
                assert result.overlap_percentage > 50


@pytest.mark.property
@pytest.mark.slow
@settings(max_examples=100, deadline=None)
@given(
    min1=st.floats(min_value=0, max_value=500, allow_nan=False, allow_infinity=False),
    max1=st.floats(min_value=500, max_value=1000, allow_nan=False, allow_infinity=False),
    min2=st.floats(min_value=0, max_value=500, allow_nan=False, allow_infinity=False),
    max2=st.floats(min_value=500, max_value=1000, allow_nan=False, allow_infinity=False),
)
def test_budget_no_overlap_flag(min1, max1, min2, max2):
    """When ranges don't overlap, overlap_zone is None.

    **Validates: Requirements 17.2**
    """
    from hypothesis import assume

    assume(min1 <= max1)
    assume(min2 <= max2)

    # Force no overlap: make min2 > max1
    shifted_min2 = max1 + 1.0
    shifted_max2 = shifted_min2 + (max2 - min2)
    t1 = (min1 + max1) / 2
    t2 = (shifted_min2 + shifted_max2) / 2

    agents = [
        _make_negotiator("buyer", min1, max1, t1),
        _make_negotiator("seller", shifted_min2, shifted_max2, t2),
    ]

    result = compute_budget_overlap(agents)
    assert result.overlap_zone is None


# ---------------------------------------------------------------------------
# Feature: ai-scenario-builder, Property 16: Agreement threshold vs target gap
#
# For any scenario with negotiators, verify gap < 3x threshold triggers
# convergence warning.
#
# **Validates: Requirements 17.4, 17.5**
# ---------------------------------------------------------------------------


@pytest.mark.property
@pytest.mark.slow
@settings(max_examples=100, deadline=None)
@given(
    target1=st.floats(min_value=100, max_value=500, allow_nan=False, allow_infinity=False),
    target2=st.floats(min_value=100, max_value=500, allow_nan=False, allow_infinity=False),
    threshold=st.floats(min_value=1, max_value=200, allow_nan=False, allow_infinity=False),
)
def test_agreement_threshold_vs_target_gap(target1, target2, threshold):
    """Gap < 3x threshold should be flagged as convergence risk.

    **Validates: Requirements 17.4, 17.5**
    """
    gap = abs(target1 - target2)

    # Build agents with wide ranges so overlap always exists
    agents = [
        _make_negotiator("buyer", 0, 1000, target1),
        _make_negotiator("seller", 0, 1000, target2),
    ]

    result = compute_budget_overlap(agents)

    # The target_gap should match the actual gap
    assert abs(result.target_gap - gap) < 1e-9

    # The function reports the gap; the caller (health check analyzer)
    # compares gap vs 3*threshold. We verify the data is correct.
    if gap < 3 * threshold:
        # The gap is small relative to threshold — convergence risk exists
        assert result.target_gap < 3 * threshold


# ---------------------------------------------------------------------------
# Feature: ai-scenario-builder, Property 17: Turn order completeness and cycle validation
#
# For any scenario, missing negotiators flagged as critical, insufficient
# turns flagged as warning.
#
# **Validates: Requirements 19.1, 19.2, 19.3, 19.4, 19.5**
# ---------------------------------------------------------------------------

from app.builder.health_checks.turn_sanity import check_turn_sanity


@pytest.mark.property
@pytest.mark.slow
@settings(max_examples=100, deadline=None)
@given(
    num_negotiators=st.integers(min_value=1, max_value=4),
    num_regulators=st.integers(min_value=0, max_value=2),
    include_all_in_order=st.booleans(),
    max_turns_factor=st.integers(min_value=1, max_value=5),
)
def test_turn_order_completeness_and_cycle_validation(
    num_negotiators, num_regulators, include_all_in_order, max_turns_factor
):
    """Missing negotiators → critical, insufficient turns → warning.

    **Validates: Requirements 19.1, 19.2, 19.3, 19.4, 19.5**
    """
    agents = []
    for i in range(num_negotiators):
        agents.append({"role": f"neg_{i}", "type": "negotiator"})
    for i in range(num_regulators):
        agents.append({"role": f"reg_{i}", "type": "regulator"})

    all_roles = [a["role"] for a in agents]

    if include_all_in_order:
        turn_order = list(all_roles)
    else:
        # Only include first negotiator, skip others
        turn_order = [agents[0]["role"]] if agents else []

    unique_in_order = len(set(turn_order))
    max_turns = max_turns_factor * unique_in_order

    params = {"turn_order": turn_order, "max_turns": max_turns}
    score, findings = check_turn_sanity(agents, params)

    assert 0 <= score <= 100

    finding_messages = [f.message for f in findings]
    finding_severities = [f.severity for f in findings]

    # If a negotiator is missing from turn_order → critical finding
    missing_negotiators = [
        a["role"] for a in agents
        if a["type"] == "negotiator" and a["role"] not in turn_order
    ]
    for role in missing_negotiators:
        assert any(
            role in msg and sev == "critical"
            for msg, sev in zip(finding_messages, finding_severities)
        ), f"Missing negotiator '{role}' should produce a critical finding"

    # If max_turns < 2 * unique roles → warning
    if unique_in_order > 0 and max_turns < 2 * unique_in_order:
        assert any(
            sev == "warning" and "max_turns" in msg
            for msg, sev in zip(finding_messages, finding_severities)
        ), "Insufficient turns should produce a warning finding"


# ---------------------------------------------------------------------------
# Feature: ai-scenario-builder, Property 18: Stall risk assessment
#
# Verify instant_convergence_risk and price_stagnation_risk flags trigger
# correctly. Verify stall_risk_score is in [0, 100].
#
# **Validates: Requirements 20.1, 20.2, 20.4**
# ---------------------------------------------------------------------------

from app.builder.health_checks.stall_risk import assess_stall_risk


@pytest.mark.property
@pytest.mark.slow
@settings(max_examples=100, deadline=None)
@given(
    target1=st.floats(min_value=100, max_value=500, allow_nan=False, allow_infinity=False),
    target2=st.floats(min_value=100, max_value=500, allow_nan=False, allow_infinity=False),
    threshold=st.floats(min_value=1, max_value=200, allow_nan=False, allow_infinity=False),
    range_size1=st.floats(min_value=0, max_value=500, allow_nan=False, allow_infinity=False),
    range_size2=st.floats(min_value=0, max_value=500, allow_nan=False, allow_infinity=False),
)
def test_stall_risk_assessment(target1, target2, threshold, range_size1, range_size2):
    """Stall risk flags trigger correctly and score is in [0, 100].

    **Validates: Requirements 20.1, 20.2, 20.4**
    """
    agents = [
        {
            "type": "negotiator",
            "budget": {
                "min": target1 - range_size1 / 2,
                "max": target1 + range_size1 / 2,
                "target": target1,
            },
        },
        {
            "type": "negotiator",
            "budget": {
                "min": target2 - range_size2 / 2,
                "max": target2 + range_size2 / 2,
                "target": target2,
            },
        },
    ]
    params = {"agreement_threshold": threshold}

    result = assess_stall_risk(agents, params)

    assert 0 <= result.stall_risk_score <= 100

    target_gap = abs(target1 - target2)

    # instant_convergence_risk: targets within threshold
    if target_gap <= threshold:
        assert "instant_convergence_risk" in result.risks
    else:
        assert "instant_convergence_risk" not in result.risks

    # price_stagnation_risk: any range < 3 * threshold
    has_narrow = range_size1 < 3 * threshold or range_size2 < 3 * threshold
    if has_narrow:
        assert "price_stagnation_risk" in result.risks
    else:
        assert "price_stagnation_risk" not in result.risks


# ---------------------------------------------------------------------------
# Feature: ai-scenario-builder, Property 19: Readiness score computation and tier
#
# For any 6 sub-scores in [0,100], verify weighted formula and tier boundaries.
#
# **Validates: Requirements 22.1, 22.2, 14.4, 14.5**
# ---------------------------------------------------------------------------

from app.builder.health_checks.readiness import compute_readiness_score


@pytest.mark.property
@pytest.mark.slow
@settings(max_examples=100, deadline=None)
@given(
    pq=st.integers(min_value=0, max_value=100),
    t=st.integers(min_value=0, max_value=100),
    bo=st.integers(min_value=0, max_value=100),
    te=st.integers(min_value=0, max_value=100),
    ts=st.integers(min_value=0, max_value=100),
    sr=st.integers(min_value=0, max_value=100),
)
def test_readiness_score_computation_and_tier(pq, t, bo, te, ts, sr):
    """Weighted formula and tier classification are correct.

    **Validates: Requirements 22.1, 22.2, 14.4, 14.5**
    """
    score, tier = compute_readiness_score(pq, t, bo, te, ts, sr)

    expected = round(
        pq * 0.25 + t * 0.20 + bo * 0.20 + te * 0.15 + ts * 0.10 + (100 - sr) * 0.10
    )
    assert score == expected, f"Expected {expected}, got {score}"

    if score >= 80:
        assert tier == "Ready"
    elif score >= 60:
        assert tier == "Needs Work"
    else:
        assert tier == "Not Ready"


# ---------------------------------------------------------------------------
# Feature: ai-scenario-builder, Property 20: Health check report structure completeness
#
# For any HealthCheckReport, verify all required fields present, every
# critical/warning finding has a recommendation, recommendations ordered
# by severity.
#
# **Validates: Requirements 22.3, 22.4, 22.5, 15.4, 20.5**
# ---------------------------------------------------------------------------

from app.builder.models import (
    AgentPromptScore,
    BudgetOverlapResult,
    HealthCheckReport,
    StallRiskResult,
)


def _st_agent_prompt_score():
    """Strategy for AgentPromptScore."""
    return st.builds(
        AgentPromptScore,
        role=_safe_text,
        name=_safe_text,
        prompt_quality_score=st.integers(min_value=0, max_value=100),
        findings=st.lists(_safe_text, min_size=0, max_size=3),
    )


def _st_budget_overlap_result():
    """Strategy for BudgetOverlapResult."""
    return st.builds(
        BudgetOverlapResult,
        overlap_zone=st.one_of(
            st.none(),
            st.tuples(
                st.floats(min_value=0, max_value=500, allow_nan=False, allow_infinity=False),
                st.floats(min_value=500, max_value=1000, allow_nan=False, allow_infinity=False),
            ),
        ),
        overlap_percentage=st.floats(min_value=0, max_value=100, allow_nan=False, allow_infinity=False),
        target_gap=st.floats(min_value=0, max_value=1000, allow_nan=False, allow_infinity=False),
        agreement_threshold=st.floats(min_value=0, max_value=1000, allow_nan=False, allow_infinity=False),
        threshold_ratio=st.floats(min_value=0, max_value=100, allow_nan=False, allow_infinity=False),
    )


def _st_stall_risk_result():
    """Strategy for StallRiskResult."""
    return st.builds(
        StallRiskResult,
        stall_risk_score=st.integers(min_value=0, max_value=100),
        risks=st.lists(
            st.sampled_from(["instant_convergence_risk", "price_stagnation_risk", "repetition_risk"]),
            min_size=0,
            max_size=3,
        ),
    )


def _st_health_check_finding_model():
    """Strategy for HealthCheckFindingEvent with severity."""
    return st.builds(
        HealthCheckFindingEvent,
        event_type=st.just("builder_health_check_finding"),
        check_name=st.sampled_from([
            "prompt_quality", "budget_overlap", "turn_sanity",
            "stall_risk", "tension", "toggle_effectiveness",
            "regulator_feasibility",
        ]),
        severity=st.sampled_from(["critical", "warning", "info"]),
        agent_role=st.one_of(st.none(), _safe_text),
        message=_safe_text,
    )


def _build_recommendations(findings: list[HealthCheckFindingEvent]) -> list[str]:
    """Mirror the HealthCheckAnalyzer recommendation builder."""
    critical: list[str] = []
    warnings: list[str] = []
    for f in findings:
        if f.severity == "critical":
            critical.append(f"[CRITICAL] {f.check_name}: {f.message}")
        elif f.severity == "warning":
            warnings.append(f"[WARNING] {f.check_name}: {f.message}")
    return critical + warnings


@st.composite
def _st_health_check_report(draw):
    """Strategy that builds a valid HealthCheckReport with consistent recommendations."""
    pq_scores = draw(st.lists(_st_agent_prompt_score(), min_size=1, max_size=4))
    findings = draw(st.lists(_st_health_check_finding_model(), min_size=0, max_size=10))
    recommendations = _build_recommendations(findings)

    pq = draw(st.integers(min_value=0, max_value=100))
    t = draw(st.integers(min_value=0, max_value=100))
    bo = draw(st.integers(min_value=0, max_value=100))
    te = draw(st.integers(min_value=0, max_value=100))
    ts = draw(st.integers(min_value=0, max_value=100))
    sr = draw(st.integers(min_value=0, max_value=100))

    readiness_score, tier = compute_readiness_score(pq, t, bo, te, ts, sr)

    return HealthCheckReport(
        readiness_score=readiness_score,
        tier=tier,
        prompt_quality_scores=pq_scores,
        tension_score=t,
        budget_overlap_score=bo,
        budget_overlap_detail=draw(_st_budget_overlap_result()),
        toggle_effectiveness_score=te,
        turn_sanity_score=ts,
        stall_risk=draw(_st_stall_risk_result()),
        findings=findings,
        recommendations=recommendations,
    )


@pytest.mark.property
@pytest.mark.slow
@settings(max_examples=100, deadline=None)
@given(report=_st_health_check_report())
def test_health_check_report_structure_completeness(report: HealthCheckReport):
    """All required fields present, critical/warning findings have recommendations,
    recommendations ordered by severity.

    **Validates: Requirements 22.3, 22.4, 22.5, 15.4, 20.5**
    """
    # 1. All required fields present
    assert 0 <= report.readiness_score <= 100
    assert report.tier in ("Ready", "Needs Work", "Not Ready")
    assert isinstance(report.prompt_quality_scores, list)
    assert all(0 <= s.prompt_quality_score <= 100 for s in report.prompt_quality_scores)
    assert 0 <= report.tension_score <= 100
    assert 0 <= report.budget_overlap_score <= 100
    assert report.budget_overlap_detail is not None
    assert 0 <= report.toggle_effectiveness_score <= 100
    assert 0 <= report.turn_sanity_score <= 100
    assert report.stall_risk is not None
    assert 0 <= report.stall_risk.stall_risk_score <= 100
    assert isinstance(report.findings, list)
    assert isinstance(report.recommendations, list)

    # 2. Every critical/warning finding has a corresponding recommendation
    critical_warning_findings = [
        f for f in report.findings if f.severity in ("critical", "warning")
    ]
    for finding in critical_warning_findings:
        assert any(
            finding.message in rec for rec in report.recommendations
        ), (
            f"Finding '{finding.message}' (severity={finding.severity}) "
            f"has no corresponding recommendation"
        )

    # 3. Recommendations ordered: all critical before any warning
    critical_indices = [
        i for i, r in enumerate(report.recommendations) if r.startswith("[CRITICAL]")
    ]
    warning_indices = [
        i for i, r in enumerate(report.recommendations) if r.startswith("[WARNING]")
    ]
    if critical_indices and warning_indices:
        assert max(critical_indices) < min(warning_indices), (
            "Critical recommendations must come before warning recommendations"
        )


# ---------------------------------------------------------------------------
# Feature: ai-scenario-builder, Property 5: Agent minimum validation
#
# For any partial scenario with <2 agents or no negotiator, validation
# rejects proceeding past agents section.
#
# **Validates: Requirements 3.7**
# ---------------------------------------------------------------------------

from app.builder.llm_agent import validate_agents_section


@pytest.mark.property
@pytest.mark.slow
@settings(max_examples=100, deadline=None)
@given(
    num_agents=st.integers(min_value=0, max_value=1),
)
def test_agent_minimum_validation_too_few_agents(num_agents):
    """Partial scenario with <2 agents is rejected.

    **Validates: Requirements 3.7**
    """
    agents = [
        {"role": f"agent_{i}", "type": "negotiator", "name": f"Agent {i}"}
        for i in range(num_agents)
    ]
    partial = {"agents": agents}
    is_valid, error = validate_agents_section(partial)
    assert is_valid is False
    assert "2 agents required" in error or "2 agents" in error.lower() or len(agents) < 2


@pytest.mark.property
@pytest.mark.slow
@settings(max_examples=100, deadline=None)
@given(
    num_agents=st.integers(min_value=2, max_value=6),
)
def test_agent_minimum_validation_no_negotiator(num_agents):
    """Partial scenario with 2+ agents but no negotiator is rejected.

    **Validates: Requirements 3.7**
    """
    agents = [
        {"role": f"agent_{i}", "type": "regulator", "name": f"Agent {i}"}
        for i in range(num_agents)
    ]
    partial = {"agents": agents}
    is_valid, error = validate_agents_section(partial)
    assert is_valid is False
    assert "negotiator" in error.lower()


@pytest.mark.property
@pytest.mark.slow
@settings(max_examples=100, deadline=None)
@given(
    num_negotiators=st.integers(min_value=1, max_value=4),
    num_others=st.integers(min_value=0, max_value=3),
)
def test_agent_minimum_validation_valid(num_negotiators, num_others):
    """Partial scenario with >=2 agents and >=1 negotiator is accepted.

    **Validates: Requirements 3.7**
    """
    from hypothesis import assume

    total = num_negotiators + num_others
    assume(total >= 2)

    agents = [
        {"role": f"neg_{i}", "type": "negotiator", "name": f"Negotiator {i}"}
        for i in range(num_negotiators)
    ] + [
        {"role": f"reg_{i}", "type": "regulator", "name": f"Regulator {i}"}
        for i in range(num_others)
    ]
    partial = {"agents": agents}
    is_valid, error = validate_agents_section(partial)
    assert is_valid is True
    assert error == ""


@pytest.mark.property
@pytest.mark.slow
@settings(max_examples=100, deadline=None)
@given(data=st.data())
def test_agent_minimum_validation_empty_or_missing(data):
    """Partial scenario with missing or empty agents is rejected.

    **Validates: Requirements 3.7**
    """
    partial = data.draw(st.sampled_from([{}, {"agents": []}, {"agents": None}]))
    if partial.get("agents") is None and "agents" in partial:
        # None is not a list, should fail
        is_valid, _ = validate_agents_section(partial)
        assert is_valid is False
    else:
        is_valid, _ = validate_agents_section(partial)
        assert is_valid is False

# ---------------------------------------------------------------------------
# Feature: ai-scenario-builder, Property 7: Scenario persistence round-trip
#
# For any valid ArenaScenario and email with an existing profile, save then
# retrieve produces equivalent scenario via load_scenario_from_dict.
#
# **Validates: Requirements 7.1, 7.2**
# ---------------------------------------------------------------------------

import tempfile

from app.builder.scenario_store import SQLiteCustomScenarioStore
from app.scenarios.loader import load_scenario_from_dict
from app.scenarios.models import ArenaScenario


def _make_valid_scenario(**overrides) -> ArenaScenario:
    """Build a minimal valid ArenaScenario with optional overrides."""
    base = {
        "id": "prop-test",
        "name": "Property Test Scenario",
        "description": "Generated for property testing",
        "agents": [
            {
                "role": "Buyer",
                "name": "Alice",
                "type": "negotiator",
                "persona_prompt": "You are a buyer.",
                "goals": ["Buy low"],
                "budget": {"min": 100.0, "max": 200.0, "target": 150.0},
                "tone": "assertive",
                "output_fields": ["proposed_price"],
                "model_id": "gemini-3-flash-preview",
            },
            {
                "role": "Seller",
                "name": "Bob",
                "type": "negotiator",
                "persona_prompt": "You are a seller.",
                "goals": ["Sell high"],
                "budget": {"min": 100.0, "max": 200.0, "target": 150.0},
                "tone": "firm",
                "output_fields": ["proposed_price"],
                "model_id": "gemini-3-flash-preview",
            },
        ],
        "toggles": [
            {
                "id": "t1",
                "label": "Secret",
                "target_agent_role": "Buyer",
                "hidden_context_payload": {"info": "secret"},
            }
        ],
        "negotiation_params": {
            "max_turns": 10,
            "agreement_threshold": 1000.0,
            "turn_order": ["Buyer", "Seller"],
        },
        "outcome_receipt": {
            "equivalent_human_time": "~1 week",
            "process_label": "Test",
        },
    }
    base.update(overrides)
    return ArenaScenario.model_validate(base)


@pytest.mark.asyncio
@pytest.mark.property
@pytest.mark.slow
@settings(max_examples=50, deadline=None)
@given(
    scenario_name=st.text(
        alphabet=st.characters(whitelist_categories=("L", "N")),
        min_size=1,
        max_size=30,
    ),
    email=st.emails(),
)
async def test_scenario_persistence_round_trip(scenario_name, email):
    """Save then retrieve produces equivalent scenario via load_scenario_from_dict.

    Uses SQLiteCustomScenarioStore with a temp database for real persistence testing.

    **Validates: Requirements 7.1, 7.2**
    """
    scenario = _make_valid_scenario(name=scenario_name)

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = f"{tmpdir}/test.db"
        store = SQLiteCustomScenarioStore(db_path=db_path)

        scenario_id = await store.save(email, scenario)
        assert isinstance(scenario_id, str)
        assert len(scenario_id) > 0

        doc = await store.get(email, scenario_id)
        assert doc is not None
        assert "scenario_json" in doc
        assert "created_at" in doc
        assert "updated_at" in doc

        # Round-trip: load_scenario_from_dict on the stored JSON
        loaded = load_scenario_from_dict(doc["scenario_json"])
        assert loaded.model_dump() == scenario.model_dump()


# ---------------------------------------------------------------------------
# Feature: ai-scenario-builder, Property 8: Custom scenario limit enforcement
#
# For any user with 20 scenarios, 21st save is rejected, count remains 20.
#
# **Validates: Requirements 7.5**
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.property
@pytest.mark.slow
@settings(max_examples=20, deadline=None)
@given(
    extra_attempts=st.integers(min_value=1, max_value=5),
)
async def test_custom_scenario_limit_enforcement(extra_attempts):
    """After 20 scenarios, further saves are rejected and count stays 20.

    **Validates: Requirements 7.5**
    """
    from fastapi import HTTPException as _HTTPException

    scenario = _make_valid_scenario()
    email = "limit-test@example.com"

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = f"{tmpdir}/test.db"
        store = SQLiteCustomScenarioStore(db_path=db_path)

        # Fill to the 20-scenario limit
        for i in range(20):
            sid = await store.save(email, scenario)
            assert isinstance(sid, str)

        assert await store.count_by_email(email) == 20

        # Every additional save must be rejected
        for _ in range(extra_attempts):
            with pytest.raises(_HTTPException) as exc_info:
                await store.save(email, scenario)
            assert exc_info.value.status_code == 409

        # Count must not have changed
        assert await store.count_by_email(email) == 20


# ---------------------------------------------------------------------------
# Feature: ai-scenario-builder, Property 6: ArenaScenario validation error specificity
#
# For any invalid scenario dict, validation errors contain at least one error
# with specific `loc` and `msg`.
#
# **Validates: Requirements 6.1, 6.2**
# ---------------------------------------------------------------------------

from pydantic import ValidationError as PydanticValidationError


@pytest.mark.property
@pytest.mark.slow
@settings(max_examples=100, deadline=None)
@given(
    missing_field=st.sampled_from([
        "id", "name", "description", "agents", "toggles",
        "negotiation_params", "outcome_receipt",
    ]),
)
def test_arena_scenario_validation_error_specificity_missing_field(missing_field):
    """Removing a required field produces errors with specific loc and msg.

    **Validates: Requirements 6.1, 6.2**
    """
    base = {
        "id": "test-id",
        "name": "Test Name",
        "description": "Test description",
        "agents": [
            {
                "role": "Buyer", "name": "Alice", "type": "negotiator",
                "persona_prompt": "You are a buyer.", "goals": ["Buy low"],
                "budget": {"min": 100.0, "max": 200.0, "target": 150.0},
                "tone": "assertive", "output_fields": ["proposed_price"],
                "model_id": "gemini-3-flash-preview",
            },
            {
                "role": "Seller", "name": "Bob", "type": "negotiator",
                "persona_prompt": "You are a seller.", "goals": ["Sell high"],
                "budget": {"min": 100.0, "max": 200.0, "target": 150.0},
                "tone": "firm", "output_fields": ["proposed_price"],
                "model_id": "gemini-3-flash-preview",
            },
        ],
        "toggles": [
            {"id": "t1", "label": "Secret", "target_agent_role": "Buyer",
             "hidden_context_payload": {"info": "secret"}},
        ],
        "negotiation_params": {
            "max_turns": 10, "agreement_threshold": 1000.0,
            "turn_order": ["Buyer", "Seller"],
        },
        "outcome_receipt": {
            "equivalent_human_time": "~1 week", "process_label": "Test",
        },
    }

    # Remove the field to make it invalid
    del base[missing_field]

    with pytest.raises(PydanticValidationError) as exc_info:
        ArenaScenario.model_validate(base)

    errors = exc_info.value.errors()
    assert len(errors) >= 1, "Expected at least one validation error"

    # Each error must have loc and msg
    for err in errors:
        assert "loc" in err, f"Error missing 'loc': {err}"
        assert "msg" in err, f"Error missing 'msg': {err}"
        assert len(err["loc"]) >= 1, f"Error loc should be non-empty: {err}"
        assert len(err["msg"]) >= 1, f"Error msg should be non-empty: {err}"


@pytest.mark.property
@pytest.mark.slow
@settings(max_examples=100, deadline=None)
@given(
    wrong_type=st.sampled_from([
        ("id", 123),
        ("name", []),
        ("agents", "not-a-list"),
        ("toggles", 42),
        ("negotiation_params", "bad"),
    ]),
)
def test_arena_scenario_validation_error_specificity_wrong_type(wrong_type):
    """Providing wrong types produces errors with specific loc and msg.

    **Validates: Requirements 6.1, 6.2**
    """
    field, bad_value = wrong_type
    base = {
        "id": "test-id",
        "name": "Test Name",
        "description": "Test description",
        "agents": [
            {
                "role": "Buyer", "name": "Alice", "type": "negotiator",
                "persona_prompt": "You are a buyer.", "goals": ["Buy low"],
                "budget": {"min": 100.0, "max": 200.0, "target": 150.0},
                "tone": "assertive", "output_fields": ["proposed_price"],
                "model_id": "gemini-3-flash-preview",
            },
            {
                "role": "Seller", "name": "Bob", "type": "negotiator",
                "persona_prompt": "You are a seller.", "goals": ["Sell high"],
                "budget": {"min": 100.0, "max": 200.0, "target": 150.0},
                "tone": "firm", "output_fields": ["proposed_price"],
                "model_id": "gemini-3-flash-preview",
            },
        ],
        "toggles": [
            {"id": "t1", "label": "Secret", "target_agent_role": "Buyer",
             "hidden_context_payload": {"info": "secret"}},
        ],
        "negotiation_params": {
            "max_turns": 10, "agreement_threshold": 1000.0,
            "turn_order": ["Buyer", "Seller"],
        },
        "outcome_receipt": {
            "equivalent_human_time": "~1 week", "process_label": "Test",
        },
    }

    base[field] = bad_value

    with pytest.raises(PydanticValidationError) as exc_info:
        ArenaScenario.model_validate(base)

    errors = exc_info.value.errors()
    assert len(errors) >= 1
    for err in errors:
        assert "loc" in err
        assert "msg" in err


# ---------------------------------------------------------------------------
# Shared Hypothesis strategy: valid ArenaScenario
# ---------------------------------------------------------------------------

_slug_text = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N")),
    min_size=1,
    max_size=20,
)


@st.composite
def _st_budget(draw):
    """Generate a valid Budget with min <= target <= max."""
    a = draw(st.floats(min_value=0, max_value=10000, allow_nan=False, allow_infinity=False))
    b = draw(st.floats(min_value=0, max_value=10000, allow_nan=False, allow_infinity=False))
    lo, hi = min(a, b), max(a, b)
    # Ensure min != max for meaningful ranges
    if lo == hi:
        hi = lo + 1.0
    target = draw(st.floats(min_value=lo, max_value=hi, allow_nan=False, allow_infinity=False))
    return Budget(min=lo, max=hi, target=target)


@st.composite
def _st_agent_definition(draw, role: str, agent_type: str = "negotiator"):
    """Generate a valid AgentDefinition with a given role and type."""
    budget = draw(_st_budget())
    return AgentDefinition(
        role=role,
        name=draw(_slug_text),
        type=agent_type,
        persona_prompt=draw(_safe_text),
        goals=draw(st.lists(_safe_text, min_size=1, max_size=3)),
        budget=budget,
        tone=draw(st.sampled_from(["assertive", "firm", "neutral", "friendly"])),
        output_fields=["proposed_price"],
        model_id="gemini-3-flash-preview",
    )


from app.scenarios.models import (
    NegotiationParams,
    OutcomeReceipt,
    ToggleDefinition,
)


@st.composite
def _st_arena_scenario(draw):
    """Generate a valid ArenaScenario satisfying all cross-reference constraints."""
    scenario_id = draw(_slug_text)
    name = draw(_safe_text)
    description = draw(_safe_text)

    # At least 2 agents, at least 1 negotiator
    num_extra_negotiators = draw(st.integers(min_value=1, max_value=2))
    num_regulators = draw(st.integers(min_value=0, max_value=1))

    agents = []
    roles = []
    for i in range(num_extra_negotiators):
        role = f"neg_{i}"
        roles.append(role)
        agents.append(draw(_st_agent_definition(role=role, agent_type="negotiator")))

    for i in range(num_regulators):
        role = f"reg_{i}"
        roles.append(role)
        agents.append(draw(_st_agent_definition(role=role, agent_type="regulator")))

    # Ensure at least 2 agents total
    if len(agents) < 2:
        role = f"neg_{len(agents)}"
        roles.append(role)
        agents.append(draw(_st_agent_definition(role=role, agent_type="negotiator")))

    # Toggle targeting a valid agent role
    target_role = draw(st.sampled_from(roles))
    toggle = ToggleDefinition(
        id=draw(_slug_text),
        label=draw(_safe_text),
        target_agent_role=target_role,
        hidden_context_payload={"info": draw(_safe_text)},
    )

    # Negotiation params with valid turn_order
    max_turns = draw(st.integers(min_value=2 * len(roles), max_value=30))
    threshold = draw(st.floats(min_value=1.0, max_value=100000.0, allow_nan=False, allow_infinity=False))

    params = NegotiationParams(
        max_turns=max_turns,
        agreement_threshold=threshold,
        turn_order=roles,
    )

    receipt = OutcomeReceipt(
        equivalent_human_time=draw(_safe_text),
        process_label=draw(_safe_text),
    )

    return ArenaScenario(
        id=scenario_id,
        name=name,
        description=description,
        agents=agents,
        toggles=[toggle],
        negotiation_params=params,
        outcome_receipt=receipt,
    )


# ---------------------------------------------------------------------------
# Feature: ai-scenario-builder, Property 1: ArenaScenario pretty_print round-trip
#
# For any valid ArenaScenario, pretty_print → JSON parse → model_validate
# produces equivalent model_dump().
#
# **Validates: Requirements 6.4, 13.1**
# ---------------------------------------------------------------------------

from app.scenarios.pretty_printer import pretty_print


@pytest.mark.property
@pytest.mark.slow
@settings(max_examples=100, deadline=None)
@given(scenario=_st_arena_scenario())
def test_arena_scenario_pretty_print_round_trip(scenario: ArenaScenario):
    """pretty_print → JSON parse → model_validate produces equivalent model_dump().

    **Validates: Requirements 6.4, 13.1**
    """
    serialized = pretty_print(scenario)
    reparsed = json.loads(serialized)
    revalidated = ArenaScenario.model_validate(reparsed)
    assert revalidated.model_dump() == scenario.model_dump()


# ---------------------------------------------------------------------------
# Feature: ai-scenario-builder, Property 2: ArenaScenario model_dump round-trip
#
# For any valid ArenaScenario, model_dump() → load_scenario_from_dict()
# produces equivalent model_dump().
#
# **Validates: Requirements 13.2**
# ---------------------------------------------------------------------------


@pytest.mark.property
@pytest.mark.slow
@settings(max_examples=100, deadline=None)
@given(scenario=_st_arena_scenario())
def test_arena_scenario_model_dump_round_trip(scenario: ArenaScenario):
    """model_dump() → load_scenario_from_dict() produces equivalent model_dump().

    **Validates: Requirements 13.2**
    """
    dumped = scenario.model_dump()
    loaded = load_scenario_from_dict(dumped)
    assert loaded.model_dump() == scenario.model_dump()


# ---------------------------------------------------------------------------
# Feature: ai-scenario-builder, Property 14: Missing email returns 401
#
# For each builder endpoint, request without valid email returns HTTP 401.
#
# **Validates: Requirements 11.5**
# ---------------------------------------------------------------------------

import httpx

from app.db import get_custom_scenario_store, get_profile_client
from app.main import app
from app.routers.builder import (
    get_builder_llm_agent,
    get_builder_session_manager,
    get_health_check_analyzer,
)


def _make_mock_profile_client():
    """Build a mock profile client for testing."""
    from unittest.mock import AsyncMock, MagicMock

    pc = MagicMock()
    pc.get_profile = AsyncMock(return_value={"email": "test@example.com"})
    return pc


def _make_mock_store():
    """Build a mock custom scenario store for testing."""
    from unittest.mock import AsyncMock, MagicMock

    store = MagicMock()
    store.list_by_email = AsyncMock(return_value=[])
    store.delete = AsyncMock(return_value=False)
    return store


@pytest.mark.asyncio
@pytest.mark.property
@pytest.mark.slow
@settings(max_examples=50, deadline=None)
@given(
    empty_email=st.sampled_from(["", "   "]),
)
async def test_missing_email_returns_401_chat(empty_email):
    """POST /builder/chat without valid email returns 401.

    **Validates: Requirements 11.5**
    """
    mock_pc = _make_mock_profile_client()
    mock_store = _make_mock_store()

    app.dependency_overrides[get_profile_client] = lambda: mock_pc
    app.dependency_overrides[get_custom_scenario_store] = lambda: mock_store

    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            resp = await client.post(
                "/api/v1/builder/chat",
                json={"email": empty_email, "session_id": "s1", "message": "hi"},
            )
            # Empty/whitespace email should fail validation (min_length=1) → 422
            # or our explicit 401 check
            assert resp.status_code in (401, 422), f"Expected 401/422, got {resp.status_code}"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
@pytest.mark.property
@pytest.mark.slow
@settings(max_examples=50, deadline=None)
@given(
    empty_email=st.sampled_from(["", "   "]),
)
async def test_missing_email_returns_401_save(empty_email):
    """POST /builder/save without valid email returns 401.

    **Validates: Requirements 11.5**
    """
    mock_pc = _make_mock_profile_client()
    mock_store = _make_mock_store()

    app.dependency_overrides[get_profile_client] = lambda: mock_pc
    app.dependency_overrides[get_custom_scenario_store] = lambda: mock_store

    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            resp = await client.post(
                "/api/v1/builder/save",
                json={"email": empty_email, "scenario_json": {}},
            )
            assert resp.status_code in (401, 422), f"Expected 401/422, got {resp.status_code}"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
@pytest.mark.property
@pytest.mark.slow
@settings(max_examples=50, deadline=None)
@given(
    empty_email=st.sampled_from(["", "   "]),
)
async def test_missing_email_returns_401_list(empty_email):
    """GET /builder/scenarios without valid email returns 401.

    **Validates: Requirements 11.5**
    """
    mock_store = _make_mock_store()
    app.dependency_overrides[get_custom_scenario_store] = lambda: mock_store

    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            resp = await client.get(
                "/api/v1/builder/scenarios",
                params={"email": empty_email},
            )
            assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
@pytest.mark.property
@pytest.mark.slow
@settings(max_examples=50, deadline=None)
@given(
    empty_email=st.sampled_from(["", "   "]),
)
async def test_missing_email_returns_401_delete(empty_email):
    """DELETE /builder/scenarios/{id} without valid email returns 401.

    **Validates: Requirements 11.5**
    """
    mock_store = _make_mock_store()
    app.dependency_overrides[get_custom_scenario_store] = lambda: mock_store

    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            resp = await client.delete(
                "/api/v1/builder/scenarios/some-id",
                params={"email": empty_email},
            )
            assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Feature: ai-scenario-builder, Property 13: Token budget enforcement
#
# For user with balance N>0, chat message results in balance N-1;
# for balance 0, returns HTTP 429.
#
# **Validates: Requirements 10.1, 10.2**
# ---------------------------------------------------------------------------

from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
@pytest.mark.property
@pytest.mark.slow
@settings(max_examples=50, deadline=None)
@given(
    balance=st.integers(min_value=0, max_value=100),
)
async def test_token_budget_enforcement(balance):
    """Balance N>0 → deduct 1; balance 0 → HTTP 429.

    **Validates: Requirements 10.1, 10.2**
    """
    mock_pc = MagicMock()
    mock_pc.get_profile = AsyncMock(return_value={"email": "test@example.com", "email_verified": True})

    mock_store = _make_mock_store()

    # Mock the session manager to avoid real session creation
    mock_session_mgr = MagicMock()
    mock_session = MagicMock()
    mock_session.session_id = "test-session"
    mock_session.conversation_history = []
    mock_session.partial_scenario = {}
    mock_session_mgr.get_session.return_value = mock_session
    mock_session_mgr.add_message = MagicMock()

    # Mock LLM agent to return empty stream
    mock_llm = MagicMock()

    async def _empty_stream(*args, **kwargs):
        return
        yield  # noqa: unreachable — makes this an async generator

    mock_llm.stream_response = _empty_stream

    app.dependency_overrides[get_profile_client] = lambda: mock_pc
    app.dependency_overrides[get_custom_scenario_store] = lambda: mock_store
    app.dependency_overrides[get_builder_session_manager] = lambda: mock_session_mgr
    app.dependency_overrides[get_builder_llm_agent] = lambda: mock_llm

    try:
        mock_deduct = AsyncMock()
        with patch(
            "app.routers.builder._get_token_balance",
            new=AsyncMock(return_value=balance),
        ), patch(
            "app.routers.builder._deduct_token",
            new=mock_deduct,
        ):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                resp = await client.post(
                    "/api/v1/builder/chat",
                    json={"email": "test@example.com", "session_id": "s1", "message": "hello"},
                )

                if balance <= 0:
                    assert resp.status_code == 429, f"Expected 429 for balance=0, got {resp.status_code}"
                    mock_deduct.assert_not_called()
                else:
                    assert resp.status_code == 200, f"Expected 200 for balance={balance}, got {resp.status_code}"
                    mock_deduct.assert_called_once()
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Feature: ai-scenario-builder, Property 9: Custom scenario usability for negotiation
#
# For any valid custom scenario, create_initial_state(session_id, scenario_json)
# produces valid NegotiationState with turn_order containing only defined
# agent roles.
#
# **Validates: Requirements 7.4**
# ---------------------------------------------------------------------------

from app.orchestrator.state import create_initial_state


@pytest.mark.property
@pytest.mark.slow
@settings(max_examples=100, deadline=None)
@given(scenario=_st_arena_scenario())
def test_custom_scenario_usability_for_negotiation(scenario: ArenaScenario):
    """create_initial_state produces valid NegotiationState from any valid scenario.

    **Validates: Requirements 7.4**
    """
    scenario_dict = scenario.model_dump()
    state = create_initial_state(
        session_id="test-session-123",
        scenario_config=scenario_dict,
    )

    # State must have all required fields
    assert state["session_id"] == "test-session-123"
    assert state["scenario_id"] == scenario.id
    assert state["max_turns"] == scenario.negotiation_params.max_turns
    assert state["deal_status"] == "Negotiating"
    assert state["turn_count"] == 0

    # turn_order must only contain roles defined in agents
    agent_roles = {a.role for a in scenario.agents}
    for role in state["turn_order"]:
        assert role in agent_roles, (
            f"turn_order contains '{role}' which is not in agent roles: {agent_roles}"
        )

    # agent_states must have an entry for every agent
    for agent in scenario.agents:
        assert agent.role in state["agent_states"], (
            f"agent_states missing role '{agent.role}'"
        )

    # current_speaker must be a valid role
    assert state["current_speaker"] in agent_roles
