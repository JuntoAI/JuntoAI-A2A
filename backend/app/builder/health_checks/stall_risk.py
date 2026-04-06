"""Stall risk assessment for negotiation scenarios.

# Feature: ai-scenario-builder
# Requirements: 20.1, 20.2, 20.4, 20.5
"""

from __future__ import annotations

from app.builder.models import StallRiskResult


def assess_stall_risk(
    agents: list[dict],
    negotiation_params: dict,
) -> StallRiskResult:
    """Evaluate stall risk based on agent budgets and negotiation params.

    Parameters
    ----------
    agents:
        List of dicts with ``"type"`` and ``"budget"`` keys.
        Budget has ``"min"``, ``"max"``, ``"target"`` floats.
    negotiation_params:
        Dict with ``"agreement_threshold"`` (float).

    Returns
    -------
    StallRiskResult with score 0-100 and list of risk flags.
    """
    risks: list[str] = []
    threshold = negotiation_params.get("agreement_threshold", 0.0)

    negotiators = [a for a in agents if a.get("type") == "negotiator"]

    score = 0

    # Check instant convergence: target prices within agreement_threshold
    targets = [a["budget"]["target"] for a in negotiators if "budget" in a]
    if len(targets) >= 2:
        min_target = min(targets)
        max_target = max(targets)
        target_gap = max_target - min_target
        if threshold > 0 and target_gap <= threshold:
            risks.append("instant_convergence_risk")
            score += 40

    # Check price stagnation: budget range < 3 * agreement_threshold
    for a in negotiators:
        budget = a.get("budget", {})
        b_min = budget.get("min", 0.0)
        b_max = budget.get("max", 0.0)
        b_range = b_max - b_min
        if threshold > 0 and b_range < 3 * threshold:
            risks.append("price_stagnation_risk")
            score += 30
            break  # one flag is enough

    score = min(score, 100)
    return StallRiskResult(stall_risk_score=score, risks=risks)
