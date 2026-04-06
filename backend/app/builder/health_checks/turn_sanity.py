"""Turn order and turn limit validation.

# Feature: ai-scenario-builder
# Requirements: 19.1, 19.2, 19.3, 19.4, 19.5
"""

from __future__ import annotations

from app.builder.events import HealthCheckFindingEvent


def check_turn_sanity(
    agents: list[dict],
    negotiation_params: dict,
) -> tuple[int, list[HealthCheckFindingEvent]]:
    """Validate turn order completeness and turn limit adequacy.

    Parameters
    ----------
    agents:
        List of dicts with at least ``"role"`` and ``"type"`` keys.
    negotiation_params:
        Dict with ``"turn_order"`` (list[str]) and ``"max_turns"`` (int).

    Returns
    -------
    tuple of (turn_sanity_score 0-100, list of findings)
    """
    findings: list[HealthCheckFindingEvent] = []
    turn_order: list[str] = negotiation_params.get("turn_order", [])
    max_turns: int = negotiation_params.get("max_turns", 0)

    agent_roles = {a["role"] for a in agents}
    negotiator_roles = {a["role"] for a in agents if a["type"] == "negotiator"}
    regulator_roles = {a["role"] for a in agents if a["type"] == "regulator"}

    score = 100
    penalty = 0

    # Check 1: every agent role appears in turn_order
    for role in agent_roles:
        if role not in turn_order:
            severity = "critical" if role in negotiator_roles else "warning"
            findings.append(
                HealthCheckFindingEvent(
                    event_type="builder_health_check_finding",
                    check_name="turn_sanity",
                    severity=severity,
                    agent_role=role,
                    message=f"Agent '{role}' is missing from turn_order",
                )
            )
            penalty += 30 if severity == "critical" else 10

    # Check 2: max_turns >= 2 * unique roles in turn_order
    unique_roles_in_order = len(set(turn_order))
    min_turns = 2 * unique_roles_in_order
    if unique_roles_in_order > 0 and max_turns < min_turns:
        findings.append(
            HealthCheckFindingEvent(
                event_type="builder_health_check_finding",
                check_name="turn_sanity",
                severity="warning",
                message=(
                    f"max_turns ({max_turns}) is less than 2x unique roles "
                    f"in turn_order ({min_turns}). Agents may not get enough speaking time."
                ),
            )
        )
        penalty += 15

    # Check 3: regulator agents appear at least once per cycle in turn_order
    turn_order_set = set(turn_order)
    for role in regulator_roles:
        if role not in turn_order_set:
            findings.append(
                HealthCheckFindingEvent(
                    event_type="builder_health_check_finding",
                    check_name="turn_sanity",
                    severity="warning",
                    agent_role=role,
                    message=(
                        f"Regulator '{role}' does not appear in turn_order. "
                        "Regulators should appear at least once per cycle."
                    ),
                )
            )
            penalty += 10

    score = max(0, score - penalty)
    return score, findings
