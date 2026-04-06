"""Readiness score computation and tier classification.

# Feature: ai-scenario-builder
# Requirements: 22.1, 22.2
"""

from __future__ import annotations


def compute_readiness_score(
    prompt_quality: int,
    tension: int,
    budget_overlap: int,
    toggle_effectiveness: int,
    turn_sanity: int,
    stall_risk: int,
) -> tuple[int, str]:
    """Compute weighted readiness score and classify into a tier.

    Formula:
        round(pq*0.25 + t*0.20 + bo*0.20 + te*0.15 + ts*0.10 + (100-sr)*0.10)

    Tiers:
        80-100 → "Ready"
        60-79  → "Needs Work"
        0-59   → "Not Ready"

    All inputs must be ints in [0, 100].
    """
    score = round(
        prompt_quality * 0.25
        + tension * 0.20
        + budget_overlap * 0.20
        + toggle_effectiveness * 0.15
        + turn_sanity * 0.10
        + (100 - stall_risk) * 0.10
    )

    if score >= 80:
        tier = "Ready"
    elif score >= 60:
        tier = "Needs Work"
    else:
        tier = "Not Ready"

    return score, tier
