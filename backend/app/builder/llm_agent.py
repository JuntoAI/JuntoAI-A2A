"""Builder LLM Agent — guided conversation for scenario construction.

# Feature: ai-scenario-builder
# Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 8.1, 8.2, 8.3, 8.4
"""

from __future__ import annotations

import json
import logging
import os
import re
from collections.abc import AsyncIterator
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessageChunk, HumanMessage, SystemMessage, AIMessage

from app.builder.events import (
    BuilderCompleteEvent,
    BuilderErrorEvent,
    BuilderJsonDeltaEvent,
    BuilderTokenEvent,
)
from app.builder.linkedin import is_linkedin_url
from app.config import settings

logger = logging.getLogger(__name__)

# Type alias matching the design doc
BuilderSSEEvent = BuilderTokenEvent | BuilderJsonDeltaEvent | BuilderCompleteEvent | BuilderErrorEvent

# Regex to detect JSON delta markers emitted by the LLM
_JSON_DELTA_RE = re.compile(r"<<JSON_DELTA:(\w+):(.*?)>>", re.DOTALL)

BUILDER_SYSTEM_PROMPT = """\
You are an expert AI scenario builder for JuntoAI's negotiation arena. Your job \
is to guide the user through creating a complete ArenaScenario JSON configuration \
step by step.

## Collection Order (follow strictly)
1. **Metadata**: scenario id (slug), name, description
2. **Agents**: collect each agent one at a time (role, name, type, persona_prompt, \
goals, budget min/max/target, tone, output_fields, model_id). Minimum 2 agents \
with at least 1 negotiator required before moving on.
3. **Toggles**: information toggles that inject hidden context into agents
4. **Negotiation Parameters**: max_turns, agreement_threshold, turn_order, \
price_unit, value_label, value_format
5. **Outcome Receipt**: equivalent_human_time, process_label

## Rules
- Ask targeted follow-up questions for ambiguous or missing fields.
- When you have enough information to populate a section, emit a JSON delta \
using the marker format: <<JSON_DELTA:section_name:json_data>>
- Valid section names: id, name, description, agents, toggles, negotiation_params, \
outcome_receipt
- The json_data must be valid JSON.
- If the user pastes a LinkedIn URL (https://www.linkedin.com/in/...), generate \
a persona based on the professional background implied by the URL.
- Do NOT proceed past the agents section until at least 2 agents are defined \
with at least 1 having type "negotiator".
- Be conversational and helpful. Explain what each field means when asked.
"""


def _build_default_model() -> BaseChatModel:
    """Create the default Gemini model via Vertex AI for the builder agent."""
    from langchain_google_vertexai import ChatVertexAI

    return ChatVertexAI(
        model_name="gemini-3.1-pro-preview",
        project=settings.GOOGLE_CLOUD_PROJECT,
        location="global",
        max_output_tokens=4096,
    )


def validate_agents_section(partial_scenario: dict) -> tuple[bool, str]:
    """Check that the agents section has minimum 2 agents with at least 1 negotiator.

    Returns (is_valid, error_message). If valid, error_message is empty.
    """
    agents = partial_scenario.get("agents", [])
    if not isinstance(agents, list):
        return False, "Agents must be a list."

    if len(agents) < 2:
        return False, f"At least 2 agents required, but only {len(agents)} defined."

    has_negotiator = any(
        isinstance(a, dict) and a.get("type") == "negotiator" for a in agents
    )
    if not has_negotiator:
        return False, "At least 1 agent must have type 'negotiator'."

    return True, ""


class BuilderLLMAgent:
    """Wraps Claude via Vertex AI for the guided scenario-building conversation."""

    def __init__(self, model: BaseChatModel | None = None) -> None:
        self._model = model

    @property
    def model(self) -> BaseChatModel:
        if self._model is None:
            self._model = _build_default_model()
        return self._model

    async def stream_response(
        self,
        conversation_history: list[dict],
        partial_scenario: dict,
        system_prompt: str = BUILDER_SYSTEM_PROMPT,
    ) -> AsyncIterator[BuilderSSEEvent]:
        """Stream LLM response as BuilderSSEEvents.

        Yields:
            BuilderTokenEvent for each streamed token,
            BuilderJsonDeltaEvent when a <<JSON_DELTA:...>> marker is parsed,
            BuilderCompleteEvent at the end,
            BuilderErrorEvent on failure.
        """
        # Check for LinkedIn URLs in the latest user message
        linkedin_context = ""
        if conversation_history:
            last_msg = conversation_history[-1]
            if last_msg.get("role") == "user" and is_linkedin_url(last_msg.get("content", "")):
                linkedin_context = (
                    "\n\n[SYSTEM NOTE: The user pasted a LinkedIn profile URL. "
                    "Generate a detailed agent persona based on the professional "
                    "background implied by this LinkedIn profile. Include suggested "
                    "role, name, persona_prompt, goals, and tone.]"
                )

        # Build agent validation context
        validation_context = ""
        agents_valid, agents_error = validate_agents_section(partial_scenario)
        if not agents_valid and partial_scenario.get("agents"):
            validation_context = (
                f"\n\n[SYSTEM NOTE: Agent validation: {agents_error} "
                "Do not proceed past the agents section until this is resolved.]"
            )

        # Construct messages for the LLM
        full_system = (
            system_prompt
            + f"\n\nCurrent partial scenario JSON:\n```json\n{json.dumps(partial_scenario, indent=2)}\n```"
            + linkedin_context
            + validation_context
        )

        messages: list[Any] = [SystemMessage(content=full_system)]
        for entry in conversation_history:
            role = entry.get("role", "user")
            content = entry.get("content", "")
            if role == "user":
                messages.append(HumanMessage(content=content))
            else:
                messages.append(AIMessage(content=content))

        try:
            accumulated_text = ""
            async for chunk in self.model.astream(messages):
                if isinstance(chunk, AIMessageChunk) and chunk.content:
                    token = chunk.content if isinstance(chunk.content, str) else str(chunk.content)
                    accumulated_text += token
                    yield BuilderTokenEvent(event_type="builder_token", token=token)

            # Parse any JSON delta markers from the full response
            for match in _JSON_DELTA_RE.finditer(accumulated_text):
                section_name = match.group(1)
                json_str = match.group(2)
                try:
                    data = json.loads(json_str)
                    yield BuilderJsonDeltaEvent(
                        event_type="builder_json_delta",
                        section=section_name,
                        data=data if isinstance(data, dict) else {"value": data},
                    )
                except json.JSONDecodeError:
                    logger.warning("Failed to parse JSON delta for section %s", section_name)

            yield BuilderCompleteEvent(event_type="builder_complete")

        except Exception as exc:
            logger.exception("LLM streaming failed")
            yield BuilderErrorEvent(
                event_type="builder_error",
                message=f"LLM call failed: {exc}",
            )
