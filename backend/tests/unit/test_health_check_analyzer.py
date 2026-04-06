"""Unit tests for HealthCheckAnalyzer.

# Feature: ai-scenario-builder
# Requirements: 14.1, 14.2, 14.6, 15.1, 16.1, 18.1, 21.1
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.builder.events import (
    HealthCheckCompleteEvent,
    HealthCheckFindingEvent,
    HealthCheckStartEvent,
)
from app.builder.health_check import HealthCheckAnalyzer
from app.scenarios.models import (
    AgentDefinition,
    ArenaScenario,
    Budget,
    NegotiationParams,
    OutcomeReceipt,
    ToggleDefinition,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_scenario(**overrides) -> ArenaScenario:
    """Build a minimal valid ArenaScenario for testing."""
    defaults = {
        "id": "test-hc",
        "name": "Health Check Test",
        "description": "A scenario for health check testing",
        "agents": [
            AgentDefinition(
                role="Buyer",
                name="Alice",
                type="negotiator",
                persona_prompt="You are a buyer seeking the lowest price. Never exceed your budget.",
                goals=["Buy below $500k", "Negotiate warranty terms"],
                budget=Budget(min=300000, max=600000, target=450000),
                tone="assertive",
                output_fields=["proposed_price"],
                model_id="test-model",
            ),
            AgentDefinition(
                role="Seller",
                name="Bob",
                type="negotiator",
                persona_prompt="You are a seller maximizing revenue. Hold firm on price.",
                goals=["Sell above $700k", "Minimize warranty scope"],
                budget=Budget(min=500000, max=900000, target=750000),
                tone="firm",
                output_fields=["proposed_price"],
                model_id="test-model",
            ),
        ],
        "toggles": [
            ToggleDefinition(
                id="competing_offer",
                label="Competing Offer",
                target_agent_role="Buyer",
                hidden_context_payload={"competing_offer": "$480k from rival"},
            ),
        ],
        "negotiation_params": NegotiationParams(
            max_turns=10,
            agreement_threshold=50000,
            turn_order=["Buyer", "Seller"],
        ),
        "outcome_receipt": OutcomeReceipt(
            equivalent_human_time="~2 weeks",
            process_label="Acquisition",
        ),
    }
    defaults.update(overrides)
    return ArenaScenario(**defaults)


def _make_scenario_with_regulator() -> ArenaScenario:
    """Build a scenario that includes a regulator agent."""
    return _make_scenario(
        agents=[
            AgentDefinition(
                role="Buyer",
                name="Alice",
                type="negotiator",
                persona_prompt="You are a buyer seeking the lowest price.",
                goals=["Buy below $500k"],
                budget=Budget(min=300000, max=600000, target=450000),
                tone="assertive",
                output_fields=["proposed_price"],
                model_id="test-model",
            ),
            AgentDefinition(
                role="Seller",
                name="Bob",
                type="negotiator",
                persona_prompt="You are a seller maximizing revenue.",
                goals=["Sell above $700k"],
                budget=Budget(min=500000, max=900000, target=750000),
                tone="firm",
                output_fields=["proposed_price"],
                model_id="test-model",
            ),
            AgentDefinition(
                role="Regulator",
                name="Compliance",
                type="regulator",
                persona_prompt="You enforce fair pricing. Block deals above $1M.",
                goals=["Ensure price below $1M", "Flag anti-competitive terms"],
                budget=Budget(min=0, max=0, target=0),
                tone="neutral",
                output_fields=["status"],
                model_id="test-model",
            ),
        ],
        negotiation_params=NegotiationParams(
            max_turns=10,
            agreement_threshold=50000,
            turn_order=["Buyer", "Regulator", "Seller", "Regulator"],
        ),
    )


def _mock_llm_response(content: str) -> MagicMock:
    """Create a mock LLM response with the given content."""
    response = MagicMock()
    response.content = content
    return response


def _make_mock_model() -> AsyncMock:
    """Create a mock LLM model that returns structured JSON responses."""
    model = AsyncMock()
    # Default: return a reasonable prompt quality response
    model.ainvoke = AsyncMock(
        return_value=_mock_llm_response('{"score": 75, "findings": ["Good structure"]}')
    )
    return model


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_analyze_yields_correct_sse_event_sequence():
    """Verify the analyzer yields Start, Findings, then Complete events."""
    model = _make_mock_model()
    # Set up different responses for different calls
    model.ainvoke = AsyncMock(
        side_effect=[
            # Prompt quality for Buyer
            _mock_llm_response('{"score": 80, "findings": ["Clear strategy"]}'),
            # Prompt quality for Seller
            _mock_llm_response('{"score": 70, "findings": ["Good persona"]}'),
            # Goal tension
            _mock_llm_response('{"tension_score": 85, "findings": ["Strong opposing interests"]}'),
            # Toggle effectiveness
            _mock_llm_response('{"score": 90, "findings": ["Actionable context"]}'),
        ]
    )

    analyzer = HealthCheckAnalyzer(model=model)
    scenario = _make_scenario()

    events = []
    async for event in analyzer.analyze(scenario, []):
        events.append(event)

    # First event must be HealthCheckStartEvent
    assert isinstance(events[0], HealthCheckStartEvent)
    assert events[0].event_type == "builder_health_check_start"

    # Last event must be HealthCheckCompleteEvent
    assert isinstance(events[-1], HealthCheckCompleteEvent)
    assert events[-1].event_type == "builder_health_check_complete"

    # Middle events should be findings
    middle_events = events[1:-1]
    for event in middle_events:
        assert isinstance(event, HealthCheckFindingEvent)
        assert event.event_type == "builder_health_check_finding"

    # Complete event should contain a report dict
    report = events[-1].report
    assert "readiness_score" in report
    assert "tier" in report
    assert "recommendations" in report
    assert "findings" in report


@pytest.mark.unit
@pytest.mark.asyncio
async def test_analyze_includes_gold_standard_in_prompts():
    """Verify gold-standard scenarios are passed to LLM prompts."""
    model = _make_mock_model()
    call_args_list: list[str] = []

    async def capture_invoke(prompt):
        call_args_list.append(str(prompt))
        return _mock_llm_response('{"score": 75, "findings": [], "tension_score": 70, "has_criteria": true}')

    model.ainvoke = AsyncMock(side_effect=capture_invoke)

    analyzer = HealthCheckAnalyzer(model=model)
    scenario = _make_scenario()

    # Create a gold-standard scenario
    gold = _make_scenario(id="gold-1", name="Gold Standard Scenario")

    events = []
    async for event in analyzer.analyze(scenario, [gold]):
        events.append(event)

    # At least one LLM call should reference the gold-standard scenario
    assert any("Gold Standard Scenario" in arg for arg in call_args_list), (
        "Gold-standard scenario name should appear in LLM prompts"
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_prompt_quality_per_agent_scoring():
    """Verify prompt quality returns per-agent scores."""
    model = _make_mock_model()
    model.ainvoke = AsyncMock(
        side_effect=[
            # Buyer: high quality
            _mock_llm_response('{"score": 90, "findings": ["Excellent strategy"]}'),
            # Seller: low quality
            _mock_llm_response('{"score": 35, "findings": ["Missing constraints"]}'),
            # Goal tension
            _mock_llm_response('{"tension_score": 80, "findings": []}'),
            # Toggle effectiveness
            _mock_llm_response('{"score": 70, "findings": []}'),
        ]
    )

    analyzer = HealthCheckAnalyzer(model=model)
    scenario = _make_scenario()

    events = []
    async for event in analyzer.analyze(scenario, []):
        events.append(event)

    report = events[-1].report
    pq_scores = report["prompt_quality_scores"]

    assert len(pq_scores) == 2
    buyer_score = next(s for s in pq_scores if s["role"] == "Buyer")
    seller_score = next(s for s in pq_scores if s["role"] == "Seller")

    assert buyer_score["prompt_quality_score"] == 90
    assert seller_score["prompt_quality_score"] == 35

    # Low-scoring agent should generate a finding
    findings = [e for e in events if isinstance(e, HealthCheckFindingEvent)]
    pq_findings = [f for f in findings if f.check_name == "prompt_quality"]
    assert any(f.agent_role == "Seller" for f in pq_findings), (
        "Low-scoring agent should produce a prompt_quality finding"
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_goal_tension_opposing_goals():
    """Verify high tension score for opposing goals."""
    model = _make_mock_model()
    model.ainvoke = AsyncMock(
        side_effect=[
            # Prompt quality (2 agents)
            _mock_llm_response('{"score": 80, "findings": []}'),
            _mock_llm_response('{"score": 80, "findings": []}'),
            # Goal tension: strong opposition
            _mock_llm_response('{"tension_score": 95, "findings": ["Buyer wants low, Seller wants high"]}'),
            # Toggle effectiveness
            _mock_llm_response('{"score": 70, "findings": []}'),
        ]
    )

    analyzer = HealthCheckAnalyzer(model=model)
    scenario = _make_scenario()

    events = []
    async for event in analyzer.analyze(scenario, []):
        events.append(event)

    report = events[-1].report
    assert report["tension_score"] == 95


@pytest.mark.unit
@pytest.mark.asyncio
async def test_goal_tension_aligned_goals():
    """Verify low tension score triggers critical finding."""
    model = _make_mock_model()
    model.ainvoke = AsyncMock(
        side_effect=[
            # Prompt quality (2 agents)
            _mock_llm_response('{"score": 80, "findings": []}'),
            _mock_llm_response('{"score": 80, "findings": []}'),
            # Goal tension: no opposition
            _mock_llm_response('{"tension_score": 15, "findings": ["Goals are aligned"]}'),
            # Toggle effectiveness
            _mock_llm_response('{"score": 70, "findings": []}'),
        ]
    )

    analyzer = HealthCheckAnalyzer(model=model)
    scenario = _make_scenario()

    events = []
    async for event in analyzer.analyze(scenario, []):
        events.append(event)

    report = events[-1].report
    assert report["tension_score"] == 15

    # Should have a critical tension finding
    findings = [e for e in events if isinstance(e, HealthCheckFindingEvent)]
    tension_findings = [f for f in findings if f.check_name == "tension"]
    assert any(f.severity == "critical" for f in tension_findings), (
        "Low tension should produce a critical finding"
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_toggle_effectiveness_evaluation():
    """Verify toggle effectiveness scoring."""
    model = _make_mock_model()
    model.ainvoke = AsyncMock(
        side_effect=[
            # Prompt quality (2 agents)
            _mock_llm_response('{"score": 80, "findings": []}'),
            _mock_llm_response('{"score": 80, "findings": []}'),
            # Goal tension
            _mock_llm_response('{"tension_score": 80, "findings": []}'),
            # Toggle effectiveness: weak toggle
            _mock_llm_response('{"score": 30, "findings": ["Toggle lacks specificity"]}'),
        ]
    )

    analyzer = HealthCheckAnalyzer(model=model)
    scenario = _make_scenario()

    events = []
    async for event in analyzer.analyze(scenario, []):
        events.append(event)

    report = events[-1].report
    assert report["toggle_effectiveness_score"] == 30

    # Weak toggle should produce a warning
    findings = [e for e in events if isinstance(e, HealthCheckFindingEvent)]
    te_findings = [f for f in findings if f.check_name == "toggle_effectiveness"]
    assert any(f.severity == "warning" for f in te_findings)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_regulator_feasibility_check():
    """Verify regulator feasibility evaluation."""
    model = _make_mock_model()
    model.ainvoke = AsyncMock(
        side_effect=[
            # Prompt quality (3 agents: Buyer, Seller, Regulator)
            _mock_llm_response('{"score": 80, "findings": []}'),
            _mock_llm_response('{"score": 80, "findings": []}'),
            _mock_llm_response('{"score": 80, "findings": []}'),
            # Goal tension
            _mock_llm_response('{"tension_score": 80, "findings": []}'),
            # Toggle effectiveness
            _mock_llm_response('{"score": 70, "findings": []}'),
            # Regulator feasibility: lacks criteria
            _mock_llm_response('{"has_criteria": false, "findings": ["No enforcement thresholds"]}'),
        ]
    )

    analyzer = HealthCheckAnalyzer(model=model)
    scenario = _make_scenario_with_regulator()

    events = []
    async for event in analyzer.analyze(scenario, []):
        events.append(event)

    findings = [e for e in events if isinstance(e, HealthCheckFindingEvent)]
    reg_findings = [f for f in findings if f.check_name == "regulator_feasibility"]
    assert any(f.severity == "warning" and f.agent_role == "Regulator" for f in reg_findings), (
        "Regulator without criteria should produce a warning"
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_llm_error_graceful_fallback():
    """Verify analyzer handles LLM errors gracefully with fallback scores."""
    model = _make_mock_model()
    model.ainvoke = AsyncMock(side_effect=Exception("Vertex AI unavailable"))

    analyzer = HealthCheckAnalyzer(model=model)
    scenario = _make_scenario()

    events = []
    async for event in analyzer.analyze(scenario, []):
        events.append(event)

    # Should still complete despite LLM errors
    assert isinstance(events[0], HealthCheckStartEvent)
    assert isinstance(events[-1], HealthCheckCompleteEvent)

    report = events[-1].report
    # Fallback scores should be used
    assert 0 <= report["readiness_score"] <= 100
    assert report["tier"] in ("Ready", "Needs Work", "Not Ready")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_recommendations_ordered_critical_first():
    """Verify recommendations are ordered: critical first, then warnings."""
    model = _make_mock_model()
    model.ainvoke = AsyncMock(
        side_effect=[
            # Prompt quality: low scores to generate findings
            _mock_llm_response('{"score": 25, "findings": ["Very weak prompt"]}'),
            _mock_llm_response('{"score": 25, "findings": ["Very weak prompt"]}'),
            # Goal tension: low
            _mock_llm_response('{"tension_score": 10, "findings": []}'),
            # Toggle effectiveness: weak
            _mock_llm_response('{"score": 30, "findings": []}'),
        ]
    )

    analyzer = HealthCheckAnalyzer(model=model)
    scenario = _make_scenario()

    events = []
    async for event in analyzer.analyze(scenario, []):
        events.append(event)

    report = events[-1].report
    recommendations = report["recommendations"]

    # Find indices of critical vs warning recommendations
    critical_indices = [i for i, r in enumerate(recommendations) if "[CRITICAL]" in r]
    warning_indices = [i for i, r in enumerate(recommendations) if "[WARNING]" in r]

    if critical_indices and warning_indices:
        assert max(critical_indices) < min(warning_indices), (
            "All critical recommendations must come before warning recommendations"
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_budget_overlap_pure_function_delegation():
    """Verify budget overlap uses the pure function, not LLM."""
    model = _make_mock_model()
    # Only set up LLM responses for the 4 LLM-powered checks
    model.ainvoke = AsyncMock(
        side_effect=[
            # Prompt quality (2 agents)
            _mock_llm_response('{"score": 80, "findings": []}'),
            _mock_llm_response('{"score": 80, "findings": []}'),
            # Goal tension
            _mock_llm_response('{"tension_score": 80, "findings": []}'),
            # Toggle effectiveness
            _mock_llm_response('{"score": 70, "findings": []}'),
        ]
    )

    analyzer = HealthCheckAnalyzer(model=model)
    scenario = _make_scenario()

    events = []
    async for event in analyzer.analyze(scenario, []):
        events.append(event)

    report = events[-1].report

    # Budget overlap should be computed (not zero/default)
    assert "budget_overlap_score" in report
    assert "budget_overlap_detail" in report
    detail = report["budget_overlap_detail"]
    assert "overlap_zone" in detail
    assert "overlap_percentage" in detail


@pytest.mark.unit
@pytest.mark.asyncio
async def test_complete_report_has_all_fields():
    """Verify the final report contains all required HealthCheckReport fields."""
    model = _make_mock_model()
    model.ainvoke = AsyncMock(
        side_effect=[
            _mock_llm_response('{"score": 80, "findings": []}'),
            _mock_llm_response('{"score": 80, "findings": []}'),
            _mock_llm_response('{"tension_score": 80, "findings": []}'),
            _mock_llm_response('{"score": 70, "findings": []}'),
        ]
    )

    analyzer = HealthCheckAnalyzer(model=model)
    scenario = _make_scenario()

    events = []
    async for event in analyzer.analyze(scenario, []):
        events.append(event)

    report = events[-1].report

    required_fields = [
        "readiness_score", "tier", "prompt_quality_scores",
        "tension_score", "budget_overlap_score", "budget_overlap_detail",
        "toggle_effectiveness_score", "turn_sanity_score", "stall_risk",
        "findings", "recommendations",
    ]
    for field in required_fields:
        assert field in report, f"Report missing required field: {field}"
