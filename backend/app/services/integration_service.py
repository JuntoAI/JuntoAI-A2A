"""Integration service — orchestration and CRM context injection.

This module provides the IntegrationService class which handles:
- CRM context preamble building and parsing (round-trip safe)
- Context injection into agent persona prompts
- Simulation orchestration (create_simulation, get_session_status, list_scenarios)
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import BackgroundTasks

from app.config import settings
from app.models.integrations import (
    CRMContext,
    ScenarioAgent,
    ScenarioContextFields,
    ScenarioListItem,
    ScenarioToggle,
    SessionOutcome,
    SessionStatusResponse,
    SimulateRequest,
    SimulateResponse,
    EvaluationScores,
    ParticipantSummary,
)
from app.scenarios.models import ArenaScenario

logger = logging.getLogger(__name__)

# Simple email regex for triggered_by validation
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Mapping from CRMContext field names to display labels in the preamble
_FIELD_LABELS: dict[str, str] = {
    "contact_name": "Contact Name",
    "company": "Company",
    "role": "Role",
    "industry": "Industry",
    "deal_value": "Deal Value",
    "deal_stage": "Deal Stage",
    "pain_points": "Pain Points",
    "competing_vendors": "Competing Vendors",
    "budget_approved": "Budget Approved",
}

# Reverse mapping: display label → field name
_LABEL_TO_FIELD: dict[str, str] = {v: k for k, v in _FIELD_LABELS.items()}

# Fields that are lists
_LIST_FIELDS: set[str] = {"pain_points", "competing_vendors"}

# Fields that are booleans
_BOOL_FIELDS: set[str] = {"budget_approved"}

# Currency field
_CURRENCY_FIELD: str = "deal_value"

_PREAMBLE_START = "--- CRM Context ---"
_PREAMBLE_END = "--- End CRM Context ---"
_CUSTOM_FIELD_PREFIX = "Custom Field"

# Internal session fields that must NEVER be exposed via the integration API
_EXCLUDED_SESSION_FIELDS = frozenset({
    "history",
    "hidden_context",
    "custom_prompts",
    "model_overrides",
    "agent_states",
    "agent_memories",
})


def _is_valid_email(value: str | None) -> bool:
    """Check if a string looks like a valid email address."""
    if not value:
        return False
    return bool(_EMAIL_RE.match(value))


class IntegrationService:
    """Orchestrates CRM integration operations.

    Handles context injection, simulation creation, session status polling,
    and scenario listing for the Integration API.
    """

    def __init__(
        self,
        session_store=None,
        share_service=None,
        scenario_registry=None,
        api_key_service=None,
        custom_scenario_store=None,
        webhook_dispatcher=None,
    ) -> None:
        """Initialize with required dependencies.

        Args:
            session_store: SessionStore implementation for session persistence.
            share_service: Module/object with create_or_get_share function.
            scenario_registry: ScenarioRegistry for scenario lookup.
            api_key_service: ApiKeyService for key operations.
            custom_scenario_store: CustomScenarioStore for dynamic scenarios.
            webhook_dispatcher: WebhookDispatcher for callback delivery.
        """
        self._session_store = session_store
        self._share_service = share_service
        self._scenario_registry = scenario_registry
        self._api_key_service = api_key_service
        self._custom_scenario_store = custom_scenario_store
        self._webhook_dispatcher = webhook_dispatcher

    # ------------------------------------------------------------------
    # Simulation orchestration
    # ------------------------------------------------------------------

    async def create_simulation(
        self,
        request: SimulateRequest,
        key_record: dict,
        background_tasks: BackgroundTasks,
    ) -> SimulateResponse:
        """Create and start a new negotiation simulation.

        Flow:
        1. Resolve scenario (dynamic or registry lookup)
        2. Validate toggle IDs
        3. Inject CRM context into agent prompts
        4. Determine owner_email from triggered_by
        5. Create session
        6. Start negotiation as background task
        7. Create share record for viewer URL
        8. Schedule webhook callback if callback_url provided
        9. Return SimulateResponse

        Raises:
            IntegrationError: On validation failures or scenario issues.
        """
        org_name = key_record["org_name"]

        # 1. Resolve scenario
        scenario = await self._resolve_scenario(request, key_record)

        # 2. Validate toggle IDs
        if request.active_toggles:
            valid_toggle_ids = {t.id for t in scenario.toggles}
            invalid_toggles = [
                tid for tid in request.active_toggles if tid not in valid_toggle_ids
            ]
            if invalid_toggles:
                raise IntegrationError(
                    status_code=422,
                    error_code="validation_error",
                    message=f"Invalid toggle IDs: {', '.join(invalid_toggles)}",
                    details={"invalid_toggles": invalid_toggles},
                )

        # 3. Inject CRM context
        if request.context:
            scenario = self.inject_context_into_prompts(scenario, request.context)

        # 4. Determine owner_email
        owner_email, source, integration_org = self._resolve_owner(
            request.triggered_by, org_name
        )

        # 5. Build hidden context from active toggles
        hidden_context: dict[str, Any] = {}
        for toggle in scenario.toggles:
            if request.active_toggles and toggle.id in request.active_toggles:
                hidden_context[toggle.target_agent_role] = toggle.hidden_context_payload

        # 6. Create session
        session_id = uuid.uuid4().hex
        scenario_config = scenario.model_dump()
        now = datetime.now(timezone.utc)

        from app.orchestrator.state import create_initial_state

        initial_state = create_initial_state(
            session_id=session_id,
            scenario_config=scenario_config,
            active_toggles=request.active_toggles or [],
            hidden_context=hidden_context,
        )

        # Persist session
        from app.models.negotiation import NegotiationStateModel

        state_model = NegotiationStateModel(**initial_state)
        await self._session_store.create_session(state_model)

        # Add metadata fields
        metadata: dict[str, Any] = {
            "owner_email": owner_email,
            "created_at": now.isoformat(),
            "scenario_config": scenario_config,
        }
        if source:
            metadata["source"] = source
        if integration_org:
            metadata["integration_org"] = integration_org
        if request.triggered_by:
            metadata["triggered_by"] = request.triggered_by

        await self._session_store.update_session(session_id, metadata)

        # 7. Start negotiation as background task
        background_tasks.add_task(
            self._run_negotiation_background,
            session_id=session_id,
            initial_state=initial_state,
            scenario_config=scenario_config,
            callback_url=request.callback_url,
            api_key_raw=key_record.get("_raw_key"),
            scenario_id=scenario.id,
        )

        # 8. Create share record for viewer URL
        viewer_url = await self._create_viewer_url(session_id, owner_email)

        return SimulateResponse(
            session_id=session_id,
            status="running",
            viewer_url=viewer_url,
            estimated_duration_seconds=120,
            created_at=now.isoformat(),
        )

    async def get_session_status(
        self, session_id: str, key_record: dict
    ) -> SessionStatusResponse:
        """Get the status of a simulation session.

        Maps internal session data to SessionStatusResponse, excluding
        internal fields (history, hidden_context, custom_prompts,
        model_overrides, agent_states, agent_memories).

        Raises:
            IntegrationError: If session not found.
        """
        try:
            raw_doc = await self._session_store.get_session_doc(session_id)
        except Exception:
            raise IntegrationError(
                status_code=404,
                error_code="session_not_found",
                message=f"Session '{session_id}' not found",
            )

        # Map status
        deal_status = raw_doc.get("deal_status", "Negotiating")
        if deal_status in ("Agreed", "Blocked", "Failed"):
            status = "completed"
        else:
            status = "running"

        # Resolve scenario name
        scenario_id = raw_doc.get("scenario_id", "")
        scenario_name = scenario_id
        try:
            sc = self._scenario_registry.get_scenario(scenario_id)
            scenario_name = sc.name
        except Exception:
            # Try scenario_config stored on session
            sc_config = raw_doc.get("scenario_config", {})
            if sc_config:
                scenario_name = sc_config.get("name", scenario_id)

        # Build viewer URL from share record
        viewer_url = ""
        try:
            from app.db import get_share_store

            share_store = get_share_store()
            share = await share_store.get_share_by_session(session_id)
            if share:
                viewer_url = f"{settings.FRONTEND_URL.rstrip('/')}/share/{share.share_slug}"
        except Exception:
            viewer_url = f"{settings.FRONTEND_URL.rstrip('/')}/session/{session_id}"

        # Build outcome for completed sessions
        outcome = None
        if status == "completed":
            outcome = self._build_outcome(raw_doc)

        return SessionStatusResponse(
            session_id=session_id,
            scenario_id=scenario_id,
            scenario_name=scenario_name,
            status=status,
            viewer_url=viewer_url,
            turns_completed=raw_doc.get("turn_count", 0) or 0,
            current_offer=raw_doc.get("current_offer"),
            created_at=raw_doc.get("created_at", ""),
            completed_at=raw_doc.get("completed_at"),
            outcome=outcome,
        )

    def list_scenarios(self) -> list[ScenarioListItem]:
        """List available scenarios with filtered fields.

        Returns only public-facing fields: id, name, description, category,
        difficulty, agents (role/name/type), toggles (id/label/target_agent_role),
        and context_fields.

        Never exposes: model_id, persona_prompt, hidden_context_payload,
        budget, goals, output_fields.
        """
        # Get all scenarios from registry (internal method to access full objects)
        scenarios: list[ScenarioListItem] = []

        for scenario_id, scenario in self._scenario_registry._scenarios.items():
            # Filter agents to only public fields
            agents = [
                ScenarioAgent(
                    role=agent.role,
                    name=agent.name,
                    type=agent.type,
                )
                for agent in scenario.agents
            ]

            # Filter toggles to only public fields
            toggles = [
                ScenarioToggle(
                    id=toggle.id,
                    label=toggle.label,
                    target_agent_role=toggle.target_agent_role,
                )
                for toggle in scenario.toggles
            ]

            # Build context_fields from CRMContext standard fields
            # Required: contact_name, company (always useful for personalization)
            # Optional: everything else
            context_fields = ScenarioContextFields(
                required=["contact_name", "company"],
                optional=[
                    "role",
                    "industry",
                    "deal_value",
                    "deal_stage",
                    "pain_points",
                    "competing_vendors",
                    "budget_approved",
                ],
            )

            scenarios.append(
                ScenarioListItem(
                    id=scenario.id,
                    name=scenario.name,
                    description=scenario.description,
                    category=scenario.category,
                    difficulty=scenario.difficulty,
                    agents=agents,
                    toggles=toggles,
                    context_fields=context_fields,
                )
            )

        return scenarios


    # ------------------------------------------------------------------
    # Context injection methods
    # ------------------------------------------------------------------

    def build_context_preamble(self, context: CRMContext | dict | None) -> str:
        """Build a structured text preamble from CRM context fields.

        Lists are rendered as comma-separated strings.
        Booleans are rendered as "Yes" or "No".
        deal_value is rendered as a currency string (e.g., "$150,000.00").
        Custom fields are prefixed with "Custom Field (<key>): <value>".
        None/empty fields are skipped.

        Args:
            context: A CRMContext instance or dict with CRM fields.

        Returns:
            A structured preamble string, or empty string if context is empty/None.
        """
        if context is None:
            return ""

        # Normalize to dict
        if isinstance(context, CRMContext):
            data = context.model_dump(exclude_none=True)
        elif isinstance(context, dict):
            data = {k: v for k, v in context.items() if v is not None}
        else:
            return ""

        if not data:
            return ""

        # Extract custom_fields separately
        custom_fields: dict[str, Any] | None = data.pop("custom_fields", None)

        lines: list[str] = [_PREAMBLE_START]

        # Standard fields in defined order
        for field_name, label in _FIELD_LABELS.items():
            if field_name not in data:
                continue
            value = data[field_name]
            formatted = self._format_field_value(field_name, value)
            if formatted is not None:
                lines.append(f"{label}: {formatted}")

        # Custom fields
        if custom_fields:
            for key, value in custom_fields.items():
                if value is None:
                    continue
                formatted = self._format_custom_value(value)
                lines.append(f"{_CUSTOM_FIELD_PREFIX} ({key}): {formatted}")

        lines.append(_PREAMBLE_END)

        # If only start/end markers, context is effectively empty
        if len(lines) <= 2:
            return ""

        return "\n".join(lines)

    def parse_context_preamble(self, preamble: str) -> dict[str, Any]:
        """Parse a context preamble string back into field names and values.

        Recovers the original field names and values from the structured preamble.
        Lists are split on ", " (comma-space).
        Booleans are recovered from "Yes"/"No".
        deal_value is recovered from currency string.

        Args:
            preamble: The structured preamble string.

        Returns:
            A dict with recovered field names and values.
        """
        if not preamble or not preamble.strip():
            return {}

        result: dict[str, Any] = {}
        custom_fields: dict[str, Any] = {}

        lines = preamble.strip().split("\n")

        for line in lines:
            line = line.strip()
            # Skip markers
            if line == _PREAMBLE_START or line == _PREAMBLE_END:
                continue

            # Check for custom field pattern
            custom_match = re.match(
                rf"^{re.escape(_CUSTOM_FIELD_PREFIX)} \(([^)]+)\): (.+)$", line
            )
            if custom_match:
                key = custom_match.group(1)
                raw_value = custom_match.group(2)
                custom_fields[key] = self._parse_custom_value(raw_value)
                continue

            # Standard field: "Label: Value"
            colon_idx = line.find(": ")
            if colon_idx == -1:
                continue

            label = line[:colon_idx]
            raw_value = line[colon_idx + 2:]

            field_name = _LABEL_TO_FIELD.get(label)
            if field_name is None:
                continue

            result[field_name] = self._parse_field_value(field_name, raw_value)

        if custom_fields:
            result["custom_fields"] = custom_fields

        return result

    def inject_context_into_prompts(
        self,
        scenario: ArenaScenario,
        context: CRMContext | dict | None,
    ) -> ArenaScenario:
        """Prepend CRM context preamble to each agent's persona_prompt.

        Returns a modified copy of the scenario — the original is not mutated.
        If context is empty or None, returns the scenario unmodified.

        Args:
            scenario: The ArenaScenario to inject context into.
            context: A CRMContext instance or dict with CRM fields.

        Returns:
            A new ArenaScenario with context prepended to persona prompts,
            or the original scenario if context is empty/None.
        """
        preamble = self.build_context_preamble(context)

        if not preamble:
            return scenario

        # Deep copy to avoid mutating the original
        scenario_data = scenario.model_dump()
        for agent in scenario_data["agents"]:
            agent["persona_prompt"] = preamble + "\n\n" + agent["persona_prompt"]

        return ArenaScenario.model_validate(scenario_data)

    # ------------------------------------------------------------------
    # Private helpers — simulation
    # ------------------------------------------------------------------

    async def _resolve_scenario(
        self, request: SimulateRequest, key_record: dict
    ) -> ArenaScenario:
        """Resolve the scenario from registry or dynamic builder.

        For _dynamic: uses BuilderLLMAgent to generate scenario.
        For others: looks up in ScenarioRegistry.
        """
        if request.scenario_id == "_dynamic":
            return await self._build_dynamic_scenario(request, key_record)

        # Look up in registry
        try:
            scenario = self._scenario_registry.get_scenario(request.scenario_id)
        except Exception:
            raise IntegrationError(
                status_code=404,
                error_code="scenario_not_found",
                message=f"Scenario '{request.scenario_id}' not found",
            )

        return scenario

    async def _build_dynamic_scenario(
        self, request: SimulateRequest, key_record: dict
    ) -> ArenaScenario:
        """Build a dynamic scenario using BuilderLLMAgent.

        Converts ScenarioBuilderInput into a conversation for the builder,
        validates the generated ArenaScenario, and persists it.
        """
        from app.builder.llm_agent import BuilderLLMAgent

        builder_input = request.scenario_builder
        if builder_input is None:
            raise IntegrationError(
                status_code=422,
                error_code="validation_error",
                message="scenario_builder is required when scenario_id is '_dynamic'",
            )

        # Build a structured prompt from the scenario_builder input
        prompt = self._build_builder_prompt(builder_input)

        # Use BuilderLLMAgent to generate the scenario
        builder = BuilderLLMAgent()
        conversation_history = [{"role": "user", "content": prompt}]
        partial_scenario: dict[str, Any] = {}

        try:
            # Stream through the builder to collect JSON deltas
            accumulated_scenario: dict[str, Any] = {}
            async for event in builder.stream_response(
                conversation_history=conversation_history,
                partial_scenario=partial_scenario,
            ):
                if hasattr(event, "event_type"):
                    if event.event_type == "builder_json_delta":
                        section = event.section
                        data = event.data
                        if section in ("agents", "toggles"):
                            # These are lists — accumulate
                            if section not in accumulated_scenario:
                                accumulated_scenario[section] = []
                            if isinstance(data, list):
                                accumulated_scenario[section].extend(data)
                            else:
                                accumulated_scenario[section].append(data)
                        else:
                            accumulated_scenario[section] = data
                    elif event.event_type == "builder_error":
                        raise IntegrationError(
                            status_code=422,
                            error_code="scenario_generation_failed",
                            message=f"Scenario generation failed: {event.message}",
                        )

            # Validate the generated scenario
            scenario = ArenaScenario.model_validate(accumulated_scenario)

        except IntegrationError:
            raise
        except Exception as exc:
            logger.error("Dynamic scenario generation failed: %s", exc, exc_info=True)
            raise IntegrationError(
                status_code=422,
                error_code="scenario_generation_failed",
                message=f"Failed to generate valid scenario: {str(exc)}",
            )

        # Persist to custom scenario store
        org_name = key_record["org_name"]
        owner_email = self._get_persist_email(request.triggered_by, org_name)

        try:
            await self._custom_scenario_store.save(owner_email, scenario)
        except Exception as exc:
            logger.warning(
                "Failed to persist dynamic scenario: %s", exc, exc_info=True
            )
            # Non-fatal — continue with the generated scenario

        return scenario

    def _build_builder_prompt(self, builder_input) -> str:
        """Convert ScenarioBuilderInput into a natural language prompt for the builder."""
        parts = [
            f"Create a {builder_input.simulation_type} negotiation scenario.",
            f"\nMy profile:",
            f"- Name: {builder_input.my_profile.name}",
            f"- Role: {builder_input.my_profile.role}",
            f"- Company: {builder_input.my_profile.company}",
            f"- Goals: {', '.join(builder_input.my_profile.goals)}",
        ]
        if builder_input.my_profile.constraints:
            parts.append(
                f"- Constraints: {', '.join(builder_input.my_profile.constraints)}"
            )
        if builder_input.my_profile.tone:
            parts.append(f"- Tone: {builder_input.my_profile.tone}")

        parts.extend([
            f"\nTheir profile:",
            f"- Name: {builder_input.their_profile.name}",
            f"- Role: {builder_input.their_profile.role}",
            f"- Company: {builder_input.their_profile.company}",
            f"- Goals: {', '.join(builder_input.their_profile.goals)}",
        ])
        if builder_input.their_profile.industry:
            parts.append(f"- Industry: {builder_input.their_profile.industry}")
        if builder_input.their_profile.constraints:
            parts.append(
                f"- Constraints: {', '.join(builder_input.their_profile.constraints)}"
            )
        if builder_input.their_profile.tone:
            parts.append(f"- Tone: {builder_input.their_profile.tone}")

        if builder_input.deal_context:
            dc = builder_input.deal_context
            parts.append("\nDeal context:")
            if dc.value is not None:
                parts.append(f"- Value: ${dc.value:,.2f}")
            if dc.stage:
                parts.append(f"- Stage: {dc.stage}")
            if dc.competing_vendors:
                parts.append(
                    f"- Competing vendors: {', '.join(dc.competing_vendors)}"
                )
            if dc.deadline:
                parts.append(f"- Deadline: {dc.deadline}")
            if dc.key_terms:
                parts.append(f"- Key terms: {', '.join(dc.key_terms)}")

        if builder_input.regulator:
            reg = builder_input.regulator
            parts.extend([
                f"\nRegulator/Observer:",
                f"- Name: {reg.name}",
                f"- Role: {reg.role}",
                f"- Rules: {', '.join(reg.rules)}",
            ])

        if builder_input.additional_instructions:
            parts.append(
                f"\nAdditional instructions: {builder_input.additional_instructions}"
            )

        parts.append(
            "\nPlease generate the complete scenario JSON with all required fields "
            "including agents, toggles, negotiation_params, and outcome_receipt. "
            "Use the JSON delta format for each section."
        )

        return "\n".join(parts)

    def _resolve_owner(
        self, triggered_by: str | None, org_name: str
    ) -> tuple[str, str | None, str | None]:
        """Determine owner_email, source, and integration_org from triggered_by.

        Returns:
            (owner_email, source, integration_org)
        """
        if _is_valid_email(triggered_by):
            return triggered_by, "integration", org_name  # type: ignore[return-value]
        else:
            return f"integration:{org_name}", None, None

    def _get_persist_email(self, triggered_by: str | None, org_name: str) -> str:
        """Get the email to use for persisting custom scenarios."""
        if _is_valid_email(triggered_by):
            return triggered_by  # type: ignore[return-value]
        return f"integration:{org_name}"

    async def _run_negotiation_background(
        self,
        session_id: str,
        initial_state: dict,
        scenario_config: dict,
        callback_url: str | None,
        api_key_raw: str | None,
        scenario_id: str,
    ) -> None:
        """Run the negotiation in the background and handle completion.

        Updates the session store with results and dispatches webhook if configured.
        """
        from app.orchestrator.graph import run_negotiation

        try:
            final_state: dict[str, Any] = dict(initial_state)

            async for snapshot in run_negotiation(initial_state, scenario_config):
                # Each snapshot is a dict keyed by node name
                for _node_name, state_delta in snapshot.items():
                    if isinstance(state_delta, dict):
                        final_state.update(state_delta)

            # Persist final state
            completed_at = datetime.now(timezone.utc).isoformat()
            duration_seconds = 0
            created_at = final_state.get("created_at")
            if created_at:
                try:
                    start = datetime.fromisoformat(created_at)
                    if start.tzinfo is None:
                        start = start.replace(tzinfo=timezone.utc)
                    duration_seconds = int(
                        (datetime.now(timezone.utc) - start).total_seconds()
                    )
                except (ValueError, TypeError):
                    pass

            updates: dict[str, Any] = {
                "deal_status": final_state.get("deal_status", "Failed"),
                "current_offer": final_state.get("current_offer", 0),
                "turn_count": final_state.get("turn_count", 0),
                "warning_count": final_state.get("warning_count", 0),
                "total_tokens_used": final_state.get("total_tokens_used", 0),
                "history": final_state.get("history", []),
                "agent_states": final_state.get("agent_states", {}),
                "completed_at": completed_at,
                "duration_seconds": duration_seconds,
            }

            await self._session_store.update_session(session_id, updates)

            # Dispatch webhook if callback_url was provided
            if callback_url and api_key_raw and self._webhook_dispatcher:
                await self._dispatch_webhook(
                    session_id=session_id,
                    scenario_id=scenario_id,
                    deal_status=updates["deal_status"],
                    final_state=final_state,
                    callback_url=callback_url,
                    api_key_raw=api_key_raw,
                )

        except Exception as exc:
            logger.error(
                "Background negotiation failed for session %s: %s",
                session_id,
                exc,
                exc_info=True,
            )
            # Mark session as failed
            try:
                await self._session_store.update_session(
                    session_id,
                    {
                        "deal_status": "Failed",
                        "completed_at": datetime.now(timezone.utc).isoformat(),
                    },
                )
            except Exception:
                logger.error(
                    "Failed to mark session %s as failed", session_id, exc_info=True
                )

    async def _dispatch_webhook(
        self,
        session_id: str,
        scenario_id: str,
        deal_status: str,
        final_state: dict,
        callback_url: str,
        api_key_raw: str,
    ) -> None:
        """Dispatch webhook callback on simulation completion."""
        from app.models.integrations import WebhookPayload

        # Build viewer URL
        viewer_url = ""
        try:
            from app.db import get_share_store

            share_store = get_share_store()
            share = await share_store.get_share_by_session(session_id)
            if share:
                viewer_url = (
                    f"{settings.FRONTEND_URL.rstrip('/')}/share/{share.share_slug}"
                )
        except Exception:
            viewer_url = f"{settings.FRONTEND_URL.rstrip('/')}/session/{session_id}"

        outcome = {
            "deal_status": deal_status,
            "summary": self._build_outcome_summary(deal_status, final_state),
            "final_offer": final_state.get("current_offer", 0),
            "turns_completed": final_state.get("turn_count", 0),
        }

        payload = WebhookPayload(
            event="simulation.completed",
            session_id=session_id,
            scenario_id=scenario_id,
            status="completed",
            outcome=outcome,
            viewer_url=viewer_url,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        local_mode = settings.RUN_MODE == "local"
        await self._webhook_dispatcher.deliver(
            callback_url=callback_url,
            payload=payload.model_dump(),
            api_key_raw=api_key_raw,
            local_mode=local_mode,
        )

    async def _create_viewer_url(self, session_id: str, owner_email: str) -> str:
        """Create a share record and return the viewer URL."""
        try:
            from app.services.share_service import create_or_get_share

            share_response = await create_or_get_share(
                session_id=session_id,
                email=owner_email,
                registry=self._scenario_registry,
            )
            return share_response.share_url
        except Exception as exc:
            logger.warning(
                "Failed to create share record for session %s: %s",
                session_id,
                exc,
            )
            # Fallback to direct session URL
            return f"{settings.FRONTEND_URL.rstrip('/')}/session/{session_id}"

    def _build_outcome(self, raw_doc: dict) -> SessionOutcome | None:
        """Build SessionOutcome from raw session document."""
        deal_status = raw_doc.get("deal_status", "Failed")
        if deal_status not in ("Agreed", "Blocked", "Failed"):
            return None

        # Build summary
        summary = self._build_outcome_summary(deal_status, raw_doc)

        # Participant summaries
        participant_summaries: list[ParticipantSummary] = []
        raw_summaries = raw_doc.get("participant_summaries", [])
        if isinstance(raw_summaries, list):
            for ps in raw_summaries:
                if isinstance(ps, dict):
                    participant_summaries.append(
                        ParticipantSummary(
                            role=ps.get("role", "Unknown"),
                            name=ps.get("name", "Unknown"),
                            agent_type=ps.get("agent_type", "negotiator"),
                            summary=ps.get("summary", ""),
                        )
                    )

        # Evaluation scores
        evaluation_scores = self._extract_evaluation_scores(raw_doc)

        # Duration
        duration_seconds = raw_doc.get("duration_seconds", 0) or 0

        return SessionOutcome(
            deal_status=deal_status,
            summary=summary,
            final_offer=float(raw_doc.get("current_offer", 0) or 0),
            turns_completed=raw_doc.get("turn_count", 0) or 0,
            warning_count=raw_doc.get("warning_count", 0) or 0,
            duration_seconds=int(duration_seconds),
            participant_summaries=participant_summaries,
            evaluation_scores=evaluation_scores,
        )

    def _build_outcome_summary(self, deal_status: str, raw_doc: dict) -> str:
        """Build a human-readable outcome summary."""
        current_offer = raw_doc.get("current_offer", 0) or 0
        if deal_status == "Agreed":
            return f"Deal agreed at ${current_offer:,.2f}"
        elif deal_status == "Blocked":
            return "Negotiation blocked by regulator"
        else:
            max_turns = raw_doc.get("max_turns", 0)
            return f"Negotiation failed after {max_turns} turns without agreement"

    def _extract_evaluation_scores(self, raw_doc: dict) -> EvaluationScores | None:
        """Extract evaluation scores from session document."""
        evaluation = raw_doc.get("evaluation")
        if not isinstance(evaluation, dict):
            return None

        dimensions = evaluation.get("dimensions")
        if not isinstance(dimensions, dict):
            return None

        overall_score = evaluation.get("overall_score")
        if overall_score is None:
            return None

        try:
            return EvaluationScores(
                fairness=int(dimensions.get("fairness", 5)),
                mutual_respect=int(dimensions.get("mutual_respect", 5)),
                value_creation=int(dimensions.get("value_creation", 5)),
                satisfaction=int(dimensions.get("satisfaction", 5)),
                overall_score=int(overall_score),
            )
        except (ValueError, TypeError):
            return None

    # ------------------------------------------------------------------
    # Private helpers — context formatting
    # ------------------------------------------------------------------

    def _format_field_value(self, field_name: str, value: Any) -> str | None:
        """Format a standard field value for the preamble."""
        if value is None:
            return None

        if field_name == _CURRENCY_FIELD:
            return self._format_currency(value)

        if field_name in _BOOL_FIELDS:
            return "Yes" if value else "No"

        if field_name in _LIST_FIELDS:
            if isinstance(value, list):
                if not value:
                    return None
                return ", ".join(str(item) for item in value)
            return str(value)

        # String fields
        str_val = str(value)
        if not str_val:
            return None
        return str_val

    def _format_currency(self, value: float | int) -> str:
        """Format a numeric value as a currency string with $ prefix."""
        return f"${value:,.2f}"

    def _format_custom_value(self, value: Any) -> str:
        """Format a custom field value for the preamble."""
        if isinstance(value, bool):
            return "Yes" if value else "No"
        if isinstance(value, list):
            return ", ".join(str(item) for item in value)
        return str(value)

    def _parse_field_value(self, field_name: str, raw_value: str) -> Any:
        """Parse a raw string value back to the appropriate type."""
        if field_name == _CURRENCY_FIELD:
            return self._parse_currency(raw_value)

        if field_name in _BOOL_FIELDS:
            return raw_value == "Yes"

        if field_name in _LIST_FIELDS:
            return [item.strip() for item in raw_value.split(", ")]

        return raw_value

    def _parse_currency(self, value: str) -> float:
        """Parse a currency string like '$150,000.00' back to a float."""
        # Remove $ and commas
        cleaned = value.replace("$", "").replace(",", "")
        return float(cleaned)

    def _parse_custom_value(self, raw_value: str) -> Any:
        """Parse a custom field value back from its string representation.

        Attempts to recover booleans and lists. Falls back to string.
        """
        if raw_value == "Yes":
            return True
        if raw_value == "No":
            return False

        # Check if it looks like a comma-separated list (contains ", ")
        if ", " in raw_value:
            return [item.strip() for item in raw_value.split(", ")]

        return raw_value


class IntegrationError(Exception):
    """Custom exception for integration service errors.

    Carries HTTP status code, error code, message, and optional details
    for consistent error response formatting.
    """

    def __init__(
        self,
        status_code: int,
        error_code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.message = message
        self.details = details or {}
