"""Health Check Analyzer — AI-powered simulation readiness analysis.

# Feature: ai-scenario-builder
# Requirements: 14.1, 14.2, 14.6, 15.1-15.4, 16.1-16.4, 18.1-18.4,
#               21.1-21.4, 22.3-22.5
"""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator
from typing import Any

from langchain_core.language_models import BaseChatModel

from app.builder.events import (
    HealthCheckCompleteEvent,
    HealthCheckFindingEvent,
    HealthCheckStartEvent,
)
from app.builder.health_checks.budget_overlap import compute_budget_overlap
from app.builder.health_checks.readiness import compute_readiness_score
from app.builder.health_checks.stall_risk import assess_stall_risk
from app.builder.health_checks.turn_sanity import check_turn_sanity
from app.builder.models import AgentPromptScore, HealthCheckReport
from app.config import settings
from app.scenarios.models import ArenaScenario

logger = logging.getLogger(__name__)

# Type alias for the SSE events yielded by the analyzer
HealthCheckSSEEvent = HealthCheckStartEvent | HealthCheckFindingEvent | HealthCheckCompleteEvent


def _build_default_model() -> BaseChatModel:
    """Create the default Gemini model via Vertex AI for health checks."""
    from langchain_google_vertexai import ChatVertexAI

    return ChatVertexAI(
        model_name="gemini-2.5-pro-preview-05-06",
        project=settings.GOOGLE_CLOUD_PROJECT,
        location=os.environ.get("VERTEX_AI_LOCATION", "us-east5"),
        max_output_tokens=2048,
    )


def _format_gold_standard_summary(scenarios: list[ArenaScenario]) -> str:
    """Build a concise summary of gold-standard scenarios for LLM context."""
    parts: list[str] = []
    for s in scenarios:
        agent_lines = []
        for a in s.agents:
            agent_lines.append(
                f"  - {a.role} ({a.type}): goals={a.goals}, "
                f"budget=[{a.budget.min}-{a.budget.max}], tone={a.tone}"
            )
        parts.append(
            f"Scenario: {s.name}\n"
            f"  Description: {s.description}\n"
            f"  Agents:\n" + "\n".join(agent_lines)
        )
    return "\n\n".join(parts)


def _finding(
    check_name: str,
    severity: str,
    message: str,
    agent_role: str | None = None,
) -> HealthCheckFindingEvent:
    """Helper to create a HealthCheckFindingEvent."""
    return HealthCheckFindingEvent(
        event_type="builder_health_check_finding",
        check_name=check_name,
        severity=severity,  # type: ignore[arg-type]
        agent_role=agent_role,
        message=message,
    )


class HealthCheckAnalyzer:
    """Performs 7 health checks on a scenario and streams SSE events."""

    def __init__(self, model: BaseChatModel | None = None) -> None:
        self._model = model

    @property
    def model(self) -> BaseChatModel:
        if self._model is None:
            self._model = _build_default_model()
        return self._model

    async def analyze(
        self,
        scenario: ArenaScenario,
        gold_standard_scenarios: list[ArenaScenario],
    ) -> AsyncIterator[HealthCheckSSEEvent]:
        """Run all 7 health checks and yield SSE events progressively."""
        yield HealthCheckStartEvent(event_type="builder_health_check_start")

        findings: list[HealthCheckFindingEvent] = []
        gold_summary = _format_gold_standard_summary(gold_standard_scenarios)

        # 1. Prompt quality (LLM)
        pq_scores, pq_findings = await self._check_prompt_quality(scenario, gold_summary)
        findings.extend(pq_findings)
        for f in pq_findings:
            yield f
        prompt_quality_score = (
            round(sum(s.prompt_quality_score for s in pq_scores) / len(pq_scores))
            if pq_scores
            else 0
        )

        # 2. Goal tension (LLM)
        tension_score, tension_findings = await self._check_goal_tension(scenario, gold_summary)
        findings.extend(tension_findings)
        for f in tension_findings:
            yield f

        # 3. Budget overlap (pure function)
        bo_result = compute_budget_overlap(scenario.agents)
        bo_findings = self._budget_overlap_findings(bo_result)
        findings.extend(bo_findings)
        for f in bo_findings:
            yield f
        budget_overlap_score = self._budget_overlap_score(bo_result)

        # 4. Toggle effectiveness (LLM)
        te_score, te_findings = await self._check_toggle_effectiveness(scenario, gold_summary)
        findings.extend(te_findings)
        for f in te_findings:
            yield f

        # 5. Turn sanity (pure function)
        agents_dicts = [a.model_dump() for a in scenario.agents]
        params_dict = scenario.negotiation_params.model_dump()
        ts_score, ts_findings = check_turn_sanity(agents_dicts, params_dict)
        findings.extend(ts_findings)
        for f in ts_findings:
            yield f

        # 6. Stall risk (pure function)
        stall_agents = [
            {
                "type": a.type,
                "budget": {"min": a.budget.min, "max": a.budget.max, "target": a.budget.target},
            }
            for a in scenario.agents
        ]
        stall_params = {
            "agreement_threshold": scenario.negotiation_params.agreement_threshold,
        }
        stall_result = assess_stall_risk(stall_agents, stall_params)
        stall_findings = self._stall_risk_findings(stall_result)
        findings.extend(stall_findings)
        for f in stall_findings:
            yield f

        # 7. Regulator feasibility (LLM)
        reg_findings = await self._check_regulator_feasibility(scenario, gold_summary)
        findings.extend(reg_findings)
        for f in reg_findings:
            yield f

        # Compute readiness score
        readiness_score, tier = compute_readiness_score(
            prompt_quality=prompt_quality_score,
            tension=tension_score,
            budget_overlap=budget_overlap_score,
            toggle_effectiveness=te_score,
            turn_sanity=ts_score,
            stall_risk=stall_result.stall_risk_score,
        )

        # Build recommendations ordered by severity
        recommendations = self._build_recommendations(findings)

        report = HealthCheckReport(
            readiness_score=readiness_score,
            tier=tier,
            prompt_quality_scores=pq_scores,
            tension_score=tension_score,
            budget_overlap_score=budget_overlap_score,
            budget_overlap_detail=bo_result,
            toggle_effectiveness_score=te_score,
            turn_sanity_score=ts_score,
            stall_risk=stall_result,
            findings=findings,
            recommendations=recommendations,
        )

        yield HealthCheckCompleteEvent(
            event_type="builder_health_check_complete",
            report=report.model_dump(),
        )


    # ------------------------------------------------------------------
    # LLM-powered checks
    # ------------------------------------------------------------------

    async def _check_prompt_quality(
        self,
        scenario: ArenaScenario,
        gold_summary: str,
    ) -> tuple[list[AgentPromptScore], list[HealthCheckFindingEvent]]:
        """Evaluate each agent's persona_prompt and goals (Req 15)."""
        scores: list[AgentPromptScore] = []
        findings: list[HealthCheckFindingEvent] = []

        for agent in scenario.agents:
            prompt = (
                "You are an expert AI scenario designer evaluating agent prompt quality.\n\n"
                f"Gold-standard scenario examples:\n{gold_summary}\n\n"
                f"Evaluate this agent definition:\n"
                f"  Role: {agent.role}\n"
                f"  Name: {agent.name}\n"
                f"  Type: {agent.type}\n"
                f"  Persona Prompt: {agent.persona_prompt}\n"
                f"  Goals: {agent.goals}\n"
                f"  Tone: {agent.tone}\n\n"
                "Score the prompt quality from 0-100 based on:\n"
                "1. Clear negotiation strategy\n"
                "2. Specific character background\n"
                "3. Behavioral constraints (what agent will/won't do)\n"
                "4. Sufficient context for LLM reasoning about trade-offs\n"
                "5. Goal specificity and internal consistency\n\n"
                "Respond with ONLY a JSON object: "
                '{"score": <int 0-100>, "findings": [<string>, ...]}'
            )
            try:
                response = await self.model.ainvoke(prompt)
                parsed = self._parse_json_response(response.content)
                score = max(0, min(100, int(parsed.get("score", 50))))
                agent_findings = parsed.get("findings", [])
            except Exception:
                logger.exception("Prompt quality check failed for agent %s", agent.role)
                score = 50
                agent_findings = ["Could not evaluate prompt quality (LLM error)"]

            scores.append(
                AgentPromptScore(
                    role=agent.role,
                    name=agent.name,
                    prompt_quality_score=score,
                    findings=agent_findings,
                )
            )

            if score < 60:
                severity = "critical" if score < 40 else "warning"
                findings.append(
                    _finding(
                        "prompt_quality",
                        severity,
                        f"Agent '{agent.role}' prompt quality score is {score}/100. "
                        f"Consider adding more specific negotiation strategy and behavioral constraints.",
                        agent_role=agent.role,
                    )
                )

        return scores, findings

    async def _check_goal_tension(
        self,
        scenario: ArenaScenario,
        gold_summary: str,
    ) -> tuple[int, list[HealthCheckFindingEvent]]:
        """Check if negotiators have opposing goals (Req 16)."""
        findings: list[HealthCheckFindingEvent] = []
        negotiators = [a for a in scenario.agents if a.type == "negotiator"]

        if len(negotiators) < 2:
            findings.append(
                _finding(
                    "tension",
                    "critical",
                    "Fewer than 2 negotiator agents — no tension possible.",
                )
            )
            return 0, findings

        agent_descriptions = "\n".join(
            f"  {a.role}: goals={a.goals}, budget=[{a.budget.min}-{a.budget.max}], "
            f"target={a.budget.target}"
            for a in negotiators
        )

        prompt = (
            "You are an expert AI scenario designer evaluating goal tension.\n\n"
            f"Gold-standard examples:\n{gold_summary}\n\n"
            f"Evaluate the tension between these negotiator agents:\n{agent_descriptions}\n\n"
            "Score the goal tension from 0-100 where:\n"
            "  0 = identical goals, no conflict\n"
            "  50 = moderate tension\n"
            "  100 = strong opposing interests\n\n"
            "Check for:\n"
            "1. Opposing pressure on the primary negotiation dimension\n"
            "2. Multi-dimensional friction (price, terms, timeline, scope)\n"
            "3. Whether goals create meaningful back-and-forth\n\n"
            "Respond with ONLY a JSON object: "
            '{"tension_score": <int 0-100>, "findings": [<string>, ...]}'
        )

        try:
            response = await self.model.ainvoke(prompt)
            parsed = self._parse_json_response(response.content)
            tension_score = max(0, min(100, int(parsed.get("tension_score", 50))))
            llm_findings = parsed.get("findings", [])
        except Exception:
            logger.exception("Goal tension check failed")
            tension_score = 50
            llm_findings = ["Could not evaluate goal tension (LLM error)"]

        if tension_score < 30:
            findings.append(
                _finding(
                    "tension",
                    "critical",
                    f"Low goal tension ({tension_score}/100). "
                    "Negotiators may not have genuinely opposing interests.",
                )
            )
        elif tension_score < 60:
            findings.append(
                _finding(
                    "tension",
                    "warning",
                    f"Moderate goal tension ({tension_score}/100). "
                    "Consider adding more opposing dimensions.",
                )
            )

        for msg in llm_findings:
            findings.append(_finding("tension", "info", msg))

        return tension_score, findings

    async def _check_toggle_effectiveness(
        self,
        scenario: ArenaScenario,
        gold_summary: str,
    ) -> tuple[int, list[HealthCheckFindingEvent]]:
        """Evaluate each toggle's hidden_context_payload (Req 18)."""
        findings: list[HealthCheckFindingEvent] = []

        if not scenario.toggles:
            return 50, findings

        toggle_scores: list[int] = []
        agent_map = {a.role: a for a in scenario.agents}

        for toggle in scenario.toggles:
            target_agent = agent_map.get(toggle.target_agent_role)
            agent_context = ""
            if target_agent:
                agent_context = (
                    f"  Target agent persona: {target_agent.persona_prompt}\n"
                    f"  Target agent goals: {target_agent.goals}\n"
                )

            prompt = (
                "You are an expert AI scenario designer evaluating toggle effectiveness.\n\n"
                f"Gold-standard examples:\n{gold_summary}\n\n"
                f"Evaluate this toggle:\n"
                f"  Toggle ID: {toggle.id}\n"
                f"  Label: {toggle.label}\n"
                f"  Target Agent: {toggle.target_agent_role}\n"
                f"  Hidden Context Payload: {toggle.hidden_context_payload}\n"
                f"{agent_context}\n"
                "Score from 0-100 based on:\n"
                "1. Contains actionable information that would alter negotiation strategy\n"
                "2. References specific negotiation dimensions (price, terms, leverage)\n"
                "3. Would plausibly change the agent's proposed_price or stance\n"
                "4. Compatible with the target agent's persona\n\n"
                "Respond with ONLY a JSON object: "
                '{"score": <int 0-100>, "findings": [<string>, ...]}'
            )

            try:
                response = await self.model.ainvoke(prompt)
                parsed = self._parse_json_response(response.content)
                score = max(0, min(100, int(parsed.get("score", 50))))
                toggle_findings = parsed.get("findings", [])
            except Exception:
                logger.exception("Toggle effectiveness check failed for %s", toggle.id)
                score = 50
                toggle_findings = ["Could not evaluate toggle (LLM error)"]

            toggle_scores.append(score)

            if score < 50:
                findings.append(
                    _finding(
                        "toggle_effectiveness",
                        "warning",
                        f"Toggle '{toggle.label}' effectiveness score is {score}/100. "
                        "Hidden context may not meaningfully alter agent behavior.",
                    )
                )

            for msg in toggle_findings:
                findings.append(_finding("toggle_effectiveness", "info", msg))

        avg_score = round(sum(toggle_scores) / len(toggle_scores)) if toggle_scores else 50
        return avg_score, findings

    async def _check_regulator_feasibility(
        self,
        scenario: ArenaScenario,
        gold_summary: str,
    ) -> list[HealthCheckFindingEvent]:
        """Check regulator agents for enforcement criteria (Req 21)."""
        findings: list[HealthCheckFindingEvent] = []
        regulators = [a for a in scenario.agents if a.type == "regulator"]

        if not regulators:
            return findings

        negotiator_dims = ", ".join(
            f"{a.role}: goals={a.goals}"
            for a in scenario.agents
            if a.type == "negotiator"
        )

        for reg in regulators:
            prompt = (
                "You are an expert AI scenario designer evaluating regulator feasibility.\n\n"
                f"Gold-standard examples:\n{gold_summary}\n\n"
                f"Evaluate this regulator agent:\n"
                f"  Role: {reg.role}\n"
                f"  Persona Prompt: {reg.persona_prompt}\n"
                f"  Goals: {reg.goals}\n\n"
                f"Negotiator dimensions: {negotiator_dims}\n\n"
                "Check for:\n"
                "1. Specific enforcement criteria (thresholds, policies, rules)\n"
                "2. Goals that could trigger WARNING or BLOCKED status\n"
                "3. Goals reference dimensions negotiators actually negotiate on\n\n"
                "Respond with ONLY a JSON object: "
                '{"has_criteria": <bool>, "findings": [<string>, ...]}'
            )

            try:
                response = await self.model.ainvoke(prompt)
                parsed = self._parse_json_response(response.content)
                has_criteria = parsed.get("has_criteria", True)
                reg_findings = parsed.get("findings", [])
            except Exception:
                logger.exception("Regulator feasibility check failed for %s", reg.role)
                has_criteria = True
                reg_findings = ["Could not evaluate regulator (LLM error)"]

            if not has_criteria:
                findings.append(
                    _finding(
                        "regulator_feasibility",
                        "warning",
                        f"Regulator '{reg.role}' lacks specific enforcement criteria. "
                        "Add concrete thresholds or policy references.",
                        agent_role=reg.role,
                    )
                )

            for msg in reg_findings:
                findings.append(
                    _finding("regulator_feasibility", "info", msg, agent_role=reg.role)
                )

        return findings


    # ------------------------------------------------------------------
    # Pure-function finding helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _budget_overlap_findings(
        result: Any,
    ) -> list[HealthCheckFindingEvent]:
        """Convert BudgetOverlapResult into findings."""
        findings: list[HealthCheckFindingEvent] = []

        if result.overlap_zone is None:
            findings.append(
                _finding(
                    "budget_overlap",
                    "critical",
                    "No budget overlap between negotiators. "
                    "The negotiation will likely always end in failure.",
                )
            )
        elif result.overlap_percentage > 50:
            findings.append(
                _finding(
                    "budget_overlap",
                    "warning",
                    f"Excessive budget overlap ({result.overlap_percentage:.0f}%). "
                    "The negotiation may converge too quickly.",
                )
            )

        return findings

    @staticmethod
    def _budget_overlap_score(result: Any) -> int:
        """Derive a 0-100 score from BudgetOverlapResult."""
        if result.overlap_zone is None:
            return 20
        if result.overlap_percentage > 50:
            return 60
        return 85

    @staticmethod
    def _stall_risk_findings(result: Any) -> list[HealthCheckFindingEvent]:
        """Convert StallRiskResult into findings."""
        findings: list[HealthCheckFindingEvent] = []
        for risk in result.risks:
            if risk == "instant_convergence_risk":
                findings.append(
                    _finding(
                        "stall_risk",
                        "warning",
                        "Instant convergence risk: negotiator targets are within "
                        "agreement_threshold of each other.",
                    )
                )
            elif risk == "price_stagnation_risk":
                findings.append(
                    _finding(
                        "stall_risk",
                        "warning",
                        "Price stagnation risk: a negotiator's budget range is too "
                        "narrow relative to agreement_threshold.",
                    )
                )
        return findings

    # ------------------------------------------------------------------
    # Recommendation builder
    # ------------------------------------------------------------------

    @staticmethod
    def _build_recommendations(
        findings: list[HealthCheckFindingEvent],
    ) -> list[str]:
        """Build ordered recommendations: critical first, then warnings."""
        critical: list[str] = []
        warnings: list[str] = []

        for f in findings:
            if f.severity == "critical":
                critical.append(f"[CRITICAL] {f.check_name}: {f.message}")
            elif f.severity == "warning":
                warnings.append(f"[WARNING] {f.check_name}: {f.message}")

        return critical + warnings

    # ------------------------------------------------------------------
    # JSON parsing helper
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_json_response(content: Any) -> dict:
        """Best-effort parse of LLM JSON response."""
        import json

        text = str(content).strip()

        # Strip markdown code fences if present
        if text.startswith("```"):
            lines = text.split("\n")
            # Remove first and last lines (fences)
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines).strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Try to find JSON object in the text
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                try:
                    return json.loads(text[start:end])
                except json.JSONDecodeError:
                    pass
            return {}
