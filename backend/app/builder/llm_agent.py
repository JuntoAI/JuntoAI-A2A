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
from app.orchestrator.available_models import MODELS_PROMPT_BLOCK, filter_models_prompt_block
from app.scenarios.models import ArenaScenario

logger = logging.getLogger(__name__)

# Type alias matching the design doc
BuilderSSEEvent = BuilderTokenEvent | BuilderJsonDeltaEvent | BuilderCompleteEvent | BuilderErrorEvent

# Regex to detect JSON delta markers emitted by the LLM
_JSON_DELTA_RE = re.compile(r"<<JSON_DELTA:(\w+):(.*?)>>", re.DOTALL)

# Auto-generate the JSON schema from the Pydantic model so the LLM always
# sees the exact field names, types, and constraints.
_ARENA_SCHEMA_JSON = json.dumps(ArenaScenario.model_json_schema(), indent=2)

# Sentinel placeholder for the models block — replaced at request time
# by ``build_system_prompt()`` with the filtered (allowed-only) model list.
_MODELS_PLACEHOLDER = "{{models_prompt_block}}"

BUILDER_SYSTEM_PROMPT = f"""\
You are an expert AI scenario builder for JuntoAI's negotiation arena. Your job \
is to guide the user through creating a complete ArenaScenario JSON configuration \
step by step.

## CRITICAL — Exact JSON Schema (you MUST follow this exactly)
The final scenario JSON is validated against this Pydantic-generated JSON Schema. \
Use ONLY the field names, types, and enum values shown here. Do NOT invent or \
rename any fields.

```json
{_ARENA_SCHEMA_JSON}
```

## Key field rules (common mistakes to avoid)
- **agents[].goals**: MUST be a list of strings, e.g. ["Goal 1", "Goal 2"]. Never a plain string.
- **toggles[].label**: The display name. There is NO "name" or "description" field on toggles.
- **toggles[].target_agent_role**: A single agent role string. There is NO "active_agents" field.
- **toggles[].hidden_context_payload**: A dict, e.g. {{"context": "..."}}. There is NO "prompt_injection" field.
- **negotiation_params.turn_order**: Must use agent **role** strings (not agent names).
- **negotiation_params.price_unit**: One of "total", "hourly", "monthly", "annual". Never "%".
- **negotiation_params.value_format**: One of "currency", "time_from_22", "percent", "number". Never "percentage".

## Collection Order (follow strictly)
1. **Metadata**: scenario id (slug), name, description, difficulty, category
2. **Agents**: collect each agent one at a time (role, name, type, persona_prompt, \
goals, budget min/max/target, tone, output_fields, model_id). Minimum 2 agents \
with at least 1 negotiator required before moving on.
3. **Toggles**: information toggles that inject hidden context into agents \
(id, label, target_agent_role, hidden_context_payload)
4. **Negotiation Parameters**: max_turns, agreement_threshold, turn_order, \
price_unit, value_label, value_format
5. **Outcome Receipt**: equivalent_human_time, process_label

## Available Models (use ONLY these for model_id and fallback_model_id)
{_MODELS_PLACEHOLDER}

When assigning model_id to agents, pick from the list above. Suggest \
a flash/smaller model for simpler roles and a pro/larger model for complex \
reasoning roles. NEVER invent model IDs — only use the exact IDs listed above.

## Rules
- Ask targeted follow-up questions for ambiguous or missing fields.
- When you have enough information to populate a section, emit a JSON delta \
using the marker format: <<JSON_DELTA:section_name:json_data>>
- Valid section names: id, name, description, agents, toggles, negotiation_params, \
outcome_receipt
- The json_data must be valid JSON that conforms EXACTLY to the schema above.
- If the user pastes a LinkedIn URL (https://www.linkedin.com/in/...), generate \
a persona based on the professional background implied by the URL.
- Do NOT proceed past the agents section until at least 2 agents are defined \
with at least 1 having type "negotiator".
- Be conversational and helpful. Explain what each field means when asked.
"""


def build_system_prompt(allowed_model_ids: frozenset[str] | None = None) -> str:
    """Return ``BUILDER_SYSTEM_PROMPT`` with the models block filtered to *allowed_model_ids*.

    When *allowed_model_ids* is ``None`` the full ``MODELS_PROMPT_BLOCK`` is used
    (backwards-compatible default for tests and local dev).
    """
    if allowed_model_ids is not None:
        block = filter_models_prompt_block(allowed_model_ids)
    else:
        block = MODELS_PROMPT_BLOCK
    return BUILDER_SYSTEM_PROMPT.replace(_MODELS_PLACEHOLDER, block)


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
        allowed_model_ids: frozenset[str] | None = None,
    ) -> AsyncIterator[BuilderSSEEvent]:
        """Stream LLM response as BuilderSSEEvents.

        Parameters
        ----------
        allowed_model_ids:
            When provided, the models block in the system prompt is filtered
            to only include these model IDs.  ``None`` keeps the full list
            (backwards-compatible default).

        Yields:
            BuilderTokenEvent for each streamed token,
            BuilderJsonDeltaEvent when a <<JSON_DELTA:...>> marker is parsed,
            BuilderCompleteEvent at the end,
            BuilderErrorEvent on failure.
        """
        # Resolve the system prompt — filter models block when allowed_model_ids
        # is provided and the caller hasn't overridden the prompt entirely.
        if system_prompt is BUILDER_SYSTEM_PROMPT:
            resolved_prompt = build_system_prompt(allowed_model_ids)
        else:
            resolved_prompt = system_prompt
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
            resolved_prompt
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
                    content = chunk.content
                    # Gemini 3.x may return content as a list of blocks
                    # (e.g. [{"type": "text", "text": "..."}, ...]).
                    # Extract only the text parts.
                    if isinstance(content, list):
                        token = "".join(
                            block.get("text", "") if isinstance(block, dict) else str(block)
                            for block in content
                            if not (isinstance(block, dict) and block.get("type") == "thinking")
                        )
                    else:
                        token = content if isinstance(content, str) else str(content)
                    if not token:
                        continue
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
