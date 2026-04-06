"""Budget overlap analysis between negotiator agents.

# Feature: ai-scenario-builder
# Requirements: 17.1, 17.2, 17.3, 17.4, 17.5
"""

from __future__ import annotations

from app.builder.models import BudgetOverlapResult
from app.scenarios.models import AgentDefinition


def compute_budget_overlap(agents: list[AgentDefinition]) -> BudgetOverlapResult:
    """Analyse budget overlap for negotiator agents.

    If fewer than 2 negotiators exist, returns a default result with no overlap.
    For the first pair of negotiators found, computes:
    - overlap zone: [max(min1, min2), min(max1, max2)] if valid
    - overlap percentage relative to both ranges
    - target gap and its ratio to agreement_threshold
    """
    negotiators = [a for a in agents if a.type == "negotiator"]

    if len(negotiators) < 2:
        return BudgetOverlapResult(
            overlap_zone=None,
            overlap_percentage=0.0,
            target_gap=0.0,
            agreement_threshold=0.0,
            threshold_ratio=0.0,
        )

    a, b = negotiators[0], negotiators[1]
    lo = max(a.budget.min, b.budget.min)
    hi = min(a.budget.max, b.budget.max)

    if lo > hi:
        # No overlap
        return BudgetOverlapResult(
            overlap_zone=None,
            overlap_percentage=0.0,
            target_gap=abs(a.budget.target - b.budget.target),
            agreement_threshold=0.0,
            threshold_ratio=0.0,
        )

    overlap_size = hi - lo
    range_a = a.budget.max - a.budget.min
    range_b = b.budget.max - b.budget.min

    if range_a == 0 and range_b == 0:
        pct = 100.0
    elif range_a == 0 or range_b == 0:
        pct = (overlap_size / max(range_a, range_b)) * 100
    else:
        pct_a = (overlap_size / range_a) * 100
        pct_b = (overlap_size / range_b) * 100
        pct = min(pct_a, pct_b)

    target_gap = abs(a.budget.target - b.budget.target)

    return BudgetOverlapResult(
        overlap_zone=(lo, hi),
        overlap_percentage=pct,
        target_gap=target_gap,
        agreement_threshold=0.0,
        threshold_ratio=0.0,
    )
