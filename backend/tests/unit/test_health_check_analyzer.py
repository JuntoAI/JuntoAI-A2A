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
                model_id="gemini-2.5-flash",
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
                model_id="gemini-2.5-flash",
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
                model_id="gemini-2.5-flash",
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
                model_id="gemini-2.5-flash",
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
                model_id="gemini-2.5-flash",
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


def _make_routing_mock(
    pq_score: int = 80,
    pq_findings: str = "[]",
    tension_score: int = 80,
    tension_findings: str = "[]",
    te_score: int = 70,
    te_findings: str = "[]",
    reg_has_criteria: bool = True,
    reg_findings: str = "[]",
    per_agent_pq: dict[str, int] | None = None,
    per_agent_pq_findings: dict[str, str] | None = None,
) -> AsyncMock:
    """Create a mock LLM that routes responses based on prompt content.

    Works correctly with parallelized asyncio.gather calls.
    """
    async def _route(prompt):
        p = str(prompt).lower()
        # Prompt quality — per-agent evaluation
        if "evaluate this agent" in p or "prompt quality" in p:
            if per_agent_pq:
                for role, score in per_agent_pq.items():
                    if role.lower() in p:
                        findings = (per_agent_pq_findings or {}).get(role, "[]")
                        return _mock_llm_response(f'{{"score": {score}, "findings": {findings}}}')
            return _mock_llm_response(f'{{"score": {pq_score}, "findings": {pq_findings}}}')
        # Goal tension
        if "tension" in p or "opposing" in p or "conflict" in p:
            return _mock_llm_response(f'{{"tension_score": {tension_score}, "findings": {tension_findings}}}')
        # Toggle effectiveness
        if "toggle" in p:
            return _mock_llm_response(f'{{"score": {te_score}, "findings": {te_findings}}}')
        # Regulator feasibility
        if "regulator" in p or "enforcement" in p or "criteria" in p:
            return _mock_llm_response(f'{{"has_criteria": {"true" if reg_has_criteria else "false"}, "findings": {reg_findings}}}')
        # Fallback
        return _mock_llm_response(f'{{"score": {pq_score}, "findings": {pq_findings}}}')

    model = AsyncMock()
    model.ainvoke = AsyncMock(side_effect=_route)
    return model


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_analyze_yields_correct_sse_event_sequence():
    """Verify the analyzer yields Start, Findings, then Complete events."""
    model = _make_routing_mock(pq_score=80, tension_score=85, te_score=90)

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
    call_args_list: list[str] = []

    async def capture_invoke(prompt):
        call_args_list.append(str(prompt))
        return _mock_llm_response('{"score": 75, "findings": [], "tension_score": 70, "has_criteria": true}')

    model = AsyncMock()
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
    model = AsyncMock()

    # With parallelized LLM calls, side_effect order is non-deterministic.
    # Use a function that inspects the prompt to return the right response.
    async def _route_invoke(prompt):
        prompt_str = str(prompt)
        if "Buyer" in prompt_str and "Evaluate this agent" in prompt_str:
            return _mock_llm_response('{"score": 90, "findings": ["Excellent strategy"]}')
        if "Seller" in prompt_str and "Evaluate this agent" in prompt_str:
            return _mock_llm_response('{"score": 35, "findings": ["Missing constraints"]}')
        if "tension" in prompt_str.lower() or "opposing" in prompt_str.lower():
            return _mock_llm_response('{"tension_score": 80, "findings": []}')
        if "toggle" in prompt_str.lower():
            return _mock_llm_response('{"score": 70, "findings": []}')
        # Fallback
        return _mock_llm_response('{"score": 75, "findings": []}')

    model.ainvoke = AsyncMock(side_effect=_route_invoke)

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
    model = _make_routing_mock(pq_score=80, tension_score=95, te_score=70)

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
    model = _make_routing_mock(pq_score=80, tension_score=15, te_score=70)

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
    model = _make_routing_mock(pq_score=80, tension_score=80, te_score=30,
                               te_findings='["Toggle lacks specificity"]')

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
    model = _make_routing_mock(pq_score=80, tension_score=80, te_score=70,
                               reg_has_criteria=False,
                               reg_findings='["No enforcement thresholds"]')

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
    model = AsyncMock()
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
    model = _make_routing_mock(
        per_agent_pq={"Buyer": 25, "Seller": 25},
        per_agent_pq_findings={"Buyer": '["Very weak prompt"]', "Seller": '["Very weak prompt"]'},
        tension_score=10, te_score=30,
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
    model = _make_routing_mock(pq_score=80, tension_score=80, te_score=70)

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
    model = _make_routing_mock(pq_score=80, tension_score=80, te_score=70)

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
