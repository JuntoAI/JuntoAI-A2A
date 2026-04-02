"""Stall detector for negotiation loops.

Analyzes negotiation history to detect when agents are stuck in
repetitive patterns — same prices, same arguments, no meaningful
progress. Returns actionable diagnostics that can terminate a run
early and advise scenario authors on what to fix.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class StallDiagnosis:
    """Result of stall analysis on a negotiation state."""

    is_stalled: bool = False
    stall_type: str = ""
    confidence: float = 0.0
    advice: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_stalled": self.is_stalled,
            "stall_type": self.stall_type,
            "confidence": round(self.confidence, 2),
            "advice": self.advice,
            "details": self.details,
        }


# Minimum turns before stall detection kicks in (need enough data)
_MIN_TURNS_FOR_DETECTION = 3

# Price movement thresholds
_PRICE_STALL_WINDOW = 3  # consecutive proposals to check
_PRICE_MOVEMENT_THRESHOLD_PCT = 0.02  # 2% of current offer

# Message similarity threshold (Jaccard on word sets)
_MESSAGE_SIMILARITY_THRESHOLD = 0.6
_MESSAGE_SIMILARITY_WINDOW = 3


def detect_stall(state: dict[str, Any]) -> StallDiagnosis:
    """Run all stall detection heuristics on the current state.

    Returns the highest-confidence diagnosis found, or a non-stalled
    diagnosis if everything looks healthy.
    """
    turn_count = state.get("turn_count", 0)
    if turn_count < _MIN_TURNS_FOR_DETECTION:
        return StallDiagnosis()

    checks = [
        _check_price_ping_pong(state),
        _check_price_stagnation(state),
        _check_message_repetition(state),
        _check_instant_convergence(state),
    ]

    # Return the highest-confidence stall found
    stalls = [c for c in checks if c.is_stalled]
    if not stalls:
        return StallDiagnosis()

    return max(stalls, key=lambda d: d.confidence)


def _get_negotiator_history(
    history: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Extract only negotiator entries from history."""
    return [h for h in history if h.get("agent_type") == "negotiator"]


def _get_prices_by_role(
    history: list[dict[str, Any]],
) -> dict[str, list[float]]:
    """Group proposed prices by agent role."""
    prices: dict[str, list[float]] = {}
    for entry in _get_negotiator_history(history):
        role = entry.get("role", "")
        content = entry.get("content", {})
        price = content.get("proposed_price", 0.0)
        if price > 0:
            prices.setdefault(role, []).append(price)
    return prices


def _check_price_ping_pong(state: dict[str, Any]) -> StallDiagnosis:
    """Detect when two agents keep proposing the same prices back and forth.

    Pattern: A proposes X, B proposes Y, A proposes X again, B proposes Y again.
    """
    history = state.get("history", [])
    prices_by_role = _get_prices_by_role(history)

    if len(prices_by_role) < 2:
        return StallDiagnosis()

    for role, prices in prices_by_role.items():
        if len(prices) < _PRICE_STALL_WINDOW:
            continue

        recent = prices[-_PRICE_STALL_WINDOW:]
        # Check if all recent prices are essentially the same
        if len(recent) >= 2:
            price_range = max(recent) - min(recent)
            avg_price = sum(recent) / len(recent)
            if avg_price > 0:
                movement_pct = price_range / avg_price
                if movement_pct < _PRICE_MOVEMENT_THRESHOLD_PCT:
                    return StallDiagnosis(
                        is_stalled=True,
                        stall_type="price_ping_pong",
                        confidence=0.9,
                        advice=[
                            f"Agent '{role}' has proposed nearly identical prices "
                            f"for {_PRICE_STALL_WINDOW} consecutive turns.",
                            "Scenario fix: Widen the gap between agent budget ranges "
                            "so there is more room to negotiate.",
                            "Scenario fix: Add strategic instructions telling agents "
                            "to make concessions tied to non-price terms.",
                            "Scenario fix: Reduce agreement_threshold to force "
                            "agents closer before declaring agreement.",
                        ],
                        details={
                            "agent": role,
                            "recent_prices": recent,
                            "movement_pct": round(movement_pct * 100, 2),
                        },
                    )

    return StallDiagnosis()


def _check_price_stagnation(state: dict[str, Any]) -> StallDiagnosis:
    """Detect when the overall current_offer hasn't moved meaningfully."""
    history = state.get("history", [])
    neg_history = _get_negotiator_history(history)

    if len(neg_history) < _PRICE_STALL_WINDOW * 2:
        return StallDiagnosis()

    # Get last N negotiator prices regardless of role
    recent_prices = []
    for entry in neg_history[-(_PRICE_STALL_WINDOW * 2):]:
        content = entry.get("content", {})
        price = content.get("proposed_price", 0.0)
        if price > 0:
            recent_prices.append(price)

    if len(recent_prices) < 4:
        return StallDiagnosis()

    price_range = max(recent_prices) - min(recent_prices)
    avg_price = sum(recent_prices) / len(recent_prices)

    if avg_price > 0:
        movement_pct = price_range / avg_price
        if movement_pct < _PRICE_MOVEMENT_THRESHOLD_PCT:
            return StallDiagnosis(
                is_stalled=True,
                stall_type="price_stagnation",
                confidence=0.85,
                advice=[
                    "All negotiators have converged to nearly the same price "
                    "but agreement hasn't been declared.",
                    "Scenario fix: Lower the agreement_threshold so this "
                    "price proximity triggers agreement.",
                    "Scenario fix: Ensure agent budget ranges have meaningful "
                    "overlap — if ranges don't overlap, agents can't converge.",
                ],
                details={
                    "recent_prices": recent_prices,
                    "price_range": round(price_range, 2),
                    "movement_pct": round(movement_pct * 100, 2),
                },
            )

    return StallDiagnosis()


def _jaccard_similarity(text_a: str, text_b: str) -> float:
    """Word-level Jaccard similarity between two texts."""
    words_a = set(text_a.lower().split())
    words_b = set(text_b.lower().split())
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    union = words_a | words_b
    return len(intersection) / len(union) if union else 0.0


def _check_message_repetition(state: dict[str, Any]) -> StallDiagnosis:
    """Detect when agents are sending substantially similar messages."""
    history = state.get("history", [])
    neg_history = _get_negotiator_history(history)

    # Group messages by role
    messages_by_role: dict[str, list[str]] = {}
    for entry in neg_history:
        role = entry.get("role", "")
        content = entry.get("content", {})
        msg = content.get("public_message", "")
        if msg:
            messages_by_role.setdefault(role, []).append(msg)

    for role, messages in messages_by_role.items():
        if len(messages) < _MESSAGE_SIMILARITY_WINDOW:
            continue

        recent = messages[-_MESSAGE_SIMILARITY_WINDOW:]
        # Compare each pair of consecutive messages
        similarities = []
        for i in range(len(recent) - 1):
            sim = _jaccard_similarity(recent[i], recent[i + 1])
            similarities.append(sim)

        avg_similarity = sum(similarities) / len(similarities)
        if avg_similarity > _MESSAGE_SIMILARITY_THRESHOLD:
            return StallDiagnosis(
                is_stalled=True,
                stall_type="message_repetition",
                confidence=0.8,
                advice=[
                    f"Agent '{role}' is repeating substantially similar "
                    f"messages (avg {avg_similarity:.0%} word overlap).",
                    "Scenario fix: Add more specific negotiation tactics "
                    "to the agent's persona_prompt.",
                    "Scenario fix: Give agents distinct fallback strategies "
                    "or walk-away conditions.",
                    "Scenario fix: Add toggles that inject new information "
                    "mid-negotiation to break patterns.",
                ],
                details={
                    "agent": role,
                    "avg_similarity": round(avg_similarity, 3),
                    "window": _MESSAGE_SIMILARITY_WINDOW,
                },
            )

    return StallDiagnosis()


def _check_instant_convergence(state: dict[str, Any]) -> StallDiagnosis:
    """Detect when agents converge too quickly (within first 2 full turns).

    This catches scenarios where budget ranges overlap so much that
    agents agree almost immediately — boring for viewers.
    """
    turn_count = state.get("turn_count", 0)
    if turn_count > 3:
        # Only relevant in early turns
        return StallDiagnosis()

    history = state.get("history", [])
    prices_by_role = _get_prices_by_role(history)

    if len(prices_by_role) < 2:
        return StallDiagnosis()

    # Check if all negotiators' FIRST prices are already within threshold
    first_prices = []
    for role, prices in prices_by_role.items():
        if prices:
            first_prices.append(prices[0])

    if len(first_prices) < 2:
        return StallDiagnosis()

    threshold = state.get("agreement_threshold", 1_000_000.0)
    price_gap = max(first_prices) - min(first_prices)

    if price_gap <= threshold * 2:
        return StallDiagnosis(
            is_stalled=True,
            stall_type="instant_convergence",
            confidence=0.75,
            advice=[
                "Agents' opening offers are already very close together. "
                "The negotiation will resolve trivially.",
                "Scenario fix: Increase the gap between agent target prices "
                "so there is genuine tension to resolve.",
                "Scenario fix: Lower the agreement_threshold to require "
                "agents to get closer before agreement is declared.",
                "Scenario fix: Add non-price dimensions (terms, conditions) "
                "that create friction even when prices are close.",
            ],
            details={
                "first_prices": {
                    role: prices[0]
                    for role, prices in prices_by_role.items()
                    if prices
                },
                "price_gap": round(price_gap, 2),
                "agreement_threshold": threshold,
            },
        )

    return StallDiagnosis()
