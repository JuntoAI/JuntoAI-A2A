"""Post-negotiation AI analysis (standalone, outside LangGraph).

Generates:
1. Per-participant summaries (2-3 sentences each) via LLM
2. Tipping point analysis (max 3 sentences) identifying what changed
   the direction or led to success/failure

Called AFTER run_negotiation() completes, alongside the evaluator.
NOT a LangGraph node. Does NOT modify NegotiationState.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.orchestrator import model_router

logger = logging.getLogger(__name__)


def _extract_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
            elif isinstance(block, str):
                parts.append(block)
        if parts:
            return "\n".join(parts)
    return str(content)


def _strip_fences(text: str) -> str:
    s = text.strip()
    if s.startswith("```"):
        nl = s.find("\n")
        if nl != -1:
            s = s[nl + 1:]
        if s.rstrip().endswith("```"):
            s = s.rstrip()[:-3].rstrip()
    return s


def _format_history_for_prompt(history: list[dict]) -> str:
    lines = []
    for entry in history:
        role = entry.get("role", "Unknown")
        agent_type = entry.get("agent_type", "negotiator")
        content = entry.get("content", {})
        turn = entry.get("turn_number", 0)
        msg = content.get("public_message", "")
        if not msg:
            msg = content.get("final_statement", content.get("observation", ""))
        if msg:
            lines.append(f"[Turn {turn}] {role} ({agent_type}): {msg}")
    return "\n".join(lines)


def _resolve_model(scenario_config: dict[str, Any]):
    evaluator_config = scenario_config.get("evaluator_config")
    if evaluator_config and evaluator_config.get("model_id"):
        return model_router.get_model(
            evaluator_config["model_id"],
            fallback_model_id=evaluator_config.get("fallback_model_id"),
        )
    agents = scenario_config.get("agents", [])
    for agent in agents:
        if agent.get("type", "negotiator") == "negotiator":
            return model_router.get_model(
                agent["model_id"],
                fallback_model_id=agent.get("fallback_model_id"),
            )
    raise ValueError("No negotiator agent found in scenario config")


async def run_post_analysis(
    terminal_state: dict[str, Any],
    scenario_config: dict[str, Any],
) -> dict[str, Any]:
    """Generate AI-powered participant summaries and tipping point analysis.

    Returns a dict with:
      - participant_summaries: list of {role, name, agent_type, summary}
      - tipping_point: str (max 3 sentences)
    """
    history = terminal_state.get("history", [])
    deal_status = terminal_state.get("deal_status", "Unknown")
    transcript = _format_history_for_prompt(history)

    if not transcript:
        return {"participant_summaries": [], "tipping_point": ""}

    agents = scenario_config.get("agents", [])
    agent_info = []
    for a in agents:
        agent_info.append({
            "role": a.get("role", "Unknown"),
            "name": a.get("name", a.get("role", "Unknown")),
            "type": a.get("type", "negotiator"),
        })

    model = _resolve_model(scenario_config)

    system_prompt = (
        "You are an expert negotiation analyst. You will be given a full "
        "negotiation transcript and must produce a JSON analysis.\n\n"
        "Rules:\n"
        "- participant_summaries: For EACH participant, write exactly 2-3 "
        "sentences summarizing their strategy, key arguments, and final position. "
        "Be specific — reference actual proposals and reasoning from the transcript.\n"
        "- tipping_point: In exactly 2-3 sentences, identify the single most "
        "critical moment that changed the direction of the negotiation or "
        "determined the outcome. What specific move, argument, or concession "
        "led to the deal succeeding, failing, or being blocked?\n\n"
        "Respond with ONLY valid JSON, no markdown fences."
    )

    participants_schema = json.dumps(agent_info, indent=2)
    user_prompt = (
        f"Negotiation outcome: {deal_status}\n\n"
        f"Participants:\n{participants_schema}\n\n"
        f"Full transcript:\n{transcript}\n\n"
        f"Respond with this exact JSON structure:\n"
        f'{{\n'
        f'  "participant_summaries": [\n'
        f'    {{"role": "<role>", "name": "<name>", "agent_type": "<type>", '
        f'"summary": "<2-3 sentence summary>"}}\n'
        f'  ],\n'
        f'  "tipping_point": "<2-3 sentence analysis>"\n'
        f'}}'
    )

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]

    try:
        response = model.invoke(messages)
        text = _extract_text(response.content)
        cleaned = _strip_fences(text)
        result = json.loads(cleaned)

        # Validate structure
        if not isinstance(result.get("participant_summaries"), list):
            raise ValueError("Missing participant_summaries list")
        if not isinstance(result.get("tipping_point"), str):
            raise ValueError("Missing tipping_point string")

        return result

    except Exception:
        logger.warning("Post-analysis parse failed. Retrying.")
        try:
            from langchain_core.messages import AIMessage
            messages.append(AIMessage(content=text if 'text' in dir() else ""))
            messages.append(HumanMessage(
                content="Your response was not valid JSON. "
                "Respond with ONLY the JSON object, no extra text."
            ))
            response = model.invoke(messages)
            text = _extract_text(response.content)
            cleaned = _strip_fences(text)
            result = json.loads(cleaned)
            return result
        except Exception:
            logger.exception("Post-analysis retry failed. Using fallback.")
            return {
                "participant_summaries": [
                    {"role": a["role"], "name": a["name"], "agent_type": a["type"],
                     "summary": f"Participated as {a['name']}"}
                    for a in agent_info
                ],
                "tipping_point": "",
            }
