"""Prompt templates for the post-negotiation evaluator agent.

Separated from evaluator.py for testability. Contains:
- Interview prompts (per-participant honest reflection)
- Scoring prompts (adversarial anti-rubber-stamp evaluation)
"""

from __future__ import annotations

import json
from typing import Any


def build_interview_system_prompt(agent_config: dict[str, Any]) -> str:
    """Build the system prompt for a participant interview.

    Instructs the LLM to answer honestly from the participant's perspective.
    """
    role = agent_config.get("role", "Participant")
    persona = agent_config.get("persona_prompt", "")
    tone = agent_config.get("tone", "")

    parts: list[str] = [
        f"You are {role}, reflecting honestly on a negotiation you just completed.",
    ]
    if persona:
        parts.append(f"Your persona: {persona}")
    if tone:
        parts.append(f"Your tone: {tone}")

    parts.append(
        "\nAnswer the following questions honestly from your perspective. "
        "If you are unhappy, say so. If you feel you lost, say so. "
        "Do not be diplomatic — be truthful about your experience."
    )

    parts.append(
        "\nYou MUST respond with valid JSON matching this schema:\n"
        + json.dumps(
            {
                "feels_served": "<bool: do you feel the outcome serves your interests?>",
                "felt_respected": "<bool: did you feel respected during the negotiation?>",
                "is_win_win": "<bool: do you believe this is a win-win outcome?>",
                "criticism": "<string: your honest criticism of the process or outcome>",
                "satisfaction_rating": "<int 1-10: your overall satisfaction>",
            },
            indent=2,
        )
    )

    return "\n".join(parts)


def build_interview_user_prompt(
    agent_config: dict[str, Any],
    history: list[dict[str, Any]],
    terminal_state: dict[str, Any],
) -> str:
    """Build the user prompt for a participant interview.

    Provides full history, persona, goals, final terms, and the 5 interview questions.
    """
    role = agent_config.get("role", "")
    goals = agent_config.get("goals", [])
    budget = agent_config.get("budget", {})
    current_offer = terminal_state.get("current_offer", 0.0)
    deal_status = terminal_state.get("deal_status", "")

    parts: list[str] = []

    # Goals
    if goals:
        parts.append("Your goals were:")
        for goal in goals:
            parts.append(f"- {goal}")

    # Budget
    if budget:
        budget_str = ", ".join(f"{k}={v}" for k, v in budget.items())
        parts.append(f"\nYour budget constraints: {budget_str}")

    # Final terms
    parts.append(f"\nFinal offer on the table: {current_offer}")
    parts.append(f"Deal status: {deal_status}")

    # History summary
    parts.append("\nNegotiation transcript:")
    for entry in history:
        entry_role = entry.get("role", "unknown")
        content = entry.get("content", {})
        if isinstance(content, dict):
            msg = (
                content.get("public_message")
                or content.get("final_statement")
                or content.get("reasoning")
                or content.get("observation")
                or str(content)
            )
        else:
            msg = str(content)
        parts.append(f"  [{entry_role}]: {msg}")

    # Interview questions
    parts.append(
        "\nReflect on this negotiation and answer honestly:"
        "\n1. Do you feel the outcome serves your interests? (feels_served)"
        "\n2. Did you feel respected throughout the process? (felt_respected)"
        "\n3. Do you believe this is a win-win outcome? (is_win_win)"
        "\n4. What is your honest criticism of the process or outcome? (criticism)"
        "\n5. Rate your overall satisfaction from 1 (terrible) to 10 (excellent). (satisfaction_rating)"
    )
    parts.append("\nRespond with JSON only.")

    return "\n".join(parts)


def build_scoring_system_prompt() -> str:
    """Build the anti-rubber-stamp scoring system prompt.

    Instructs the evaluator to be adversarial — default to 5, require
    evidence to score higher, penalize simple splits, cap at 6 if
    dissatisfaction detected.
    """
    return (
        "You are an expert negotiation evaluator. Your job is to produce an "
        "objective, adversarial quality assessment of a completed negotiation.\n\n"
        "SCORING RULES — follow these strictly:\n"
        "- Default to 5/10. Require concrete evidence to score higher.\n"
        "- If ANY participant expresses dissatisfaction (satisfaction_rating <= 4 "
        "or feels_served=false), cap the overall score at 6.\n"
        "- Penalize simple price splits (meeting in the middle) by at least 2 points. "
        "Simple splits show no creativity or value creation.\n"
        "- Reserve 9-10 for negotiations with genuine enthusiasm from ALL parties "
        "AND novel value creation (new terms, creative packages, mutual gains "
        "beyond price).\n"
        "- Cross-reference self-reported satisfaction against objective metrics. "
        "If a participant says they're satisfied but got a deal far from their "
        "target, note the discrepancy.\n"
        "- For negotiations with 3+ participants, also evaluate multi-party "
        "fairness: did any participant get sidelined or steamrolled?\n\n"
        "Score these four dimensions (each 1-10):\n"
        "- fairness: Was the outcome fair relative to each party's constraints?\n"
        "- mutual_respect: Did parties treat each other respectfully?\n"
        "- value_creation: Did the negotiation create value beyond simple compromise?\n"
        "- satisfaction: How satisfied are the participants overall?\n\n"
        "You MUST respond with valid JSON matching this schema:\n"
        + json.dumps(
            {
                "participant_interviews": "<list: the interview data you received>",
                "dimensions": {
                    "fairness": "<int 1-10>",
                    "mutual_respect": "<int 1-10>",
                    "value_creation": "<int 1-10>",
                    "satisfaction": "<int 1-10>",
                },
                "overall_score": "<int 1-10>",
                "verdict": "<string: 2-3 sentence summary of the negotiation quality>",
                "deal_status": "<string: the deal status>",
            },
            indent=2,
        )
    )


def build_scoring_user_prompt(
    interviews: list[dict[str, Any]],
    history: list[dict[str, Any]],
    terminal_state: dict[str, Any],
    scenario_config: dict[str, Any],
) -> str:
    """Build the scoring user prompt with all interviews, history, and deal metrics."""
    current_offer = terminal_state.get("current_offer", 0.0)
    deal_status = terminal_state.get("deal_status", "")
    turn_count = terminal_state.get("turn_count", 0)

    parts: list[str] = []

    # Deal metrics
    parts.append(f"Final deal: {deal_status} at {current_offer} after {turn_count} turns.")

    # Per-agent budget data for cross-referencing
    agents = scenario_config.get("agents", [])
    parts.append("\nAgent budget data:")
    for agent in agents:
        if agent.get("type", "negotiator") == "negotiator":
            budget = agent.get("budget", {})
            parts.append(
                f"  {agent.get('role', '?')}: "
                f"target={budget.get('target', '?')}, "
                f"min={budget.get('min', '?')}, "
                f"max={budget.get('max', '?')}"
            )

    # Interview results
    parts.append("\nParticipant interviews:")
    parts.append(json.dumps(interviews, indent=2))

    # Negotiation transcript summary
    parts.append("\nNegotiation transcript:")
    for entry in history:
        entry_role = entry.get("role", "unknown")
        content = entry.get("content", {})
        if isinstance(content, dict):
            msg = (
                content.get("public_message")
                or content.get("final_statement")
                or content.get("reasoning")
                or content.get("observation")
                or str(content)
            )
        else:
            msg = str(content)
        parts.append(f"  [{entry_role}]: {msg}")

    parts.append("\nProduce your evaluation. Respond with JSON only.")

    return "\n".join(parts)
