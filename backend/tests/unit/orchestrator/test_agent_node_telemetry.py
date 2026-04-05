"""Unit tests for agent node telemetry instrumentation.

Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 5.1, 5.2, 5.3
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage

from app.orchestrator.agent_node import create_agent_node
from app.orchestrator.state import NegotiationState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_agent_config(
    role: str = "Buyer",
    name: str = "Alice",
    agent_type: str = "negotiator",
    model_id: str = "gemini-3-flash-preview",
    persona_prompt: str = "You are a savvy buyer.",
) -> dict[str, Any]:
    return {
        "role": role,
        "name": name,
        "type": agent_type,
        "model_id": model_id,
        "persona_prompt": persona_prompt,
    }


def _make_state(
    turn_order: list[str] | None = None,
    turn_order_index: int = 0,
    turn_count: int = 0,
    max_turns: int = 10,
    current_offer: float = 0.0,
    deal_status: str = "Negotiating",
    agents: list[dict] | None = None,
    agent_states: dict | None = None,
    model_overrides: dict[str, str] | None = None,
    history: list | None = None,
) -> NegotiationState:
    if turn_order is None:
        turn_order = ["Buyer", "Seller"]
    if agents is None:
        agents = [
            _make_agent_config("Buyer", "Alice"),
            _make_agent_config("Seller", "Bob"),
        ]
    if agent_states is None:
        agent_states = {
            "Buyer": {"role": "Buyer", "name": "Alice", "agent_type": "negotiator", "model_id": "gemini-3-flash-preview", "last_proposed_price": 0.0, "warning_count": 0},
            "Seller": {"role": "Seller", "name": "Bob", "agent_type": "negotiator", "model_id": "gemini-3-flash-preview", "last_proposed_price": 0.0, "warning_count": 0},
        }
    return NegotiationState(
        session_id="test-sess",
        scenario_id="test-scenario",
        turn_count=turn_count,
        max_turns=max_turns,
        current_speaker=turn_order[turn_order_index],
        deal_status=deal_status,
        current_offer=current_offer,
        history=history or [],
        hidden_context={},
        warning_count=0,
        agreement_threshold=5000.0,
        scenario_config={"id": "test-scenario", "agents": agents, "negotiation_params": {"max_turns": max_turns}},
        turn_order=turn_order,
        turn_order_index=turn_order_index,
        agent_states=agent_states,
        active_toggles=[],
        total_tokens_used=0,
        stall_diagnosis=None,
        custom_prompts={},
        model_overrides=model_overrides or {},
        structured_memory_enabled=False,
        structured_memory_roles=[],
        agent_memories={},
        milestone_summaries_enabled=False,
        milestone_summaries={},
        sliding_window_size=3,
        milestone_interval=4,
        no_memory_roles=[],
        agent_calls=[],
    )


def _mock_response(content: str, input_tokens: int = 100, output_tokens: int = 50) -> AIMessage:
    """Create an AIMessage with usage_metadata attached."""
    msg = AIMessage(content=content)
    msg.usage_metadata = {"input_tokens": input_tokens, "output_tokens": output_tokens}
    return msg


VALID_NEGOTIATOR_JSON = '{"inner_thought": "lowball", "public_message": "I offer 300k", "proposed_price": 300000.0}'
INVALID_JSON = "not valid json at all"


# ===========================================================================
# Req 3.1, 3.2, 3.5: Successful LLM call produces exactly 1 AgentCallRecord
# ===========================================================================


class TestSuccessfulCallTelemetry:
    """A single successful LLM call produces exactly 1 AgentCallRecord."""

    @patch("app.orchestrator.agent_node.model_router")
    def test_single_call_produces_one_record(self, mock_router):
        mock_model = MagicMock()
        mock_model.invoke.return_value = _mock_response(VALID_NEGOTIATOR_JSON)
        mock_router.get_model.return_value = mock_model

        state = _make_state(turn_order=["Buyer"], agents=[_make_agent_config("Buyer", "Alice")])
        node_fn = create_agent_node("Buyer")
        result = node_fn(state)

        assert "agent_calls" in result
        assert len(result["agent_calls"]) == 1

    @patch("app.orchestrator.agent_node.model_router")
    def test_record_has_correct_agent_role(self, mock_router):
        mock_model = MagicMock()
        mock_model.invoke.return_value = _mock_response(VALID_NEGOTIATOR_JSON)
        mock_router.get_model.return_value = mock_model

        state = _make_state(turn_order=["Buyer"], agents=[_make_agent_config("Buyer", "Alice")])
        node_fn = create_agent_node("Buyer")
        result = node_fn(state)

        record = result["agent_calls"][0]
        assert record["agent_role"] == "Buyer"
        assert record["agent_type"] == "negotiator"

    @patch("app.orchestrator.agent_node.model_router")
    def test_record_has_correct_model_id(self, mock_router):
        mock_model = MagicMock()
        mock_model.invoke.return_value = _mock_response(VALID_NEGOTIATOR_JSON)
        mock_router.get_model.return_value = mock_model

        state = _make_state(turn_order=["Buyer"], agents=[_make_agent_config("Buyer", "Alice")])
        node_fn = create_agent_node("Buyer")
        result = node_fn(state)

        record = result["agent_calls"][0]
        assert record["model_id"] == "gemini-3-flash-preview"

    @patch("app.orchestrator.agent_node.model_router")
    def test_record_has_nonnegative_latency(self, mock_router):
        mock_model = MagicMock()
        mock_model.invoke.return_value = _mock_response(VALID_NEGOTIATOR_JSON)
        mock_router.get_model.return_value = mock_model

        state = _make_state(turn_order=["Buyer"], agents=[_make_agent_config("Buyer", "Alice")])
        node_fn = create_agent_node("Buyer")
        result = node_fn(state)

        record = result["agent_calls"][0]
        assert record["latency_ms"] >= 0

    @patch("app.orchestrator.agent_node.model_router")
    def test_record_captures_tokens(self, mock_router):
        mock_model = MagicMock()
        mock_model.invoke.return_value = _mock_response(VALID_NEGOTIATOR_JSON, input_tokens=200, output_tokens=75)
        mock_router.get_model.return_value = mock_model

        state = _make_state(turn_order=["Buyer"], agents=[_make_agent_config("Buyer", "Alice")])
        node_fn = create_agent_node("Buyer")
        result = node_fn(state)

        record = result["agent_calls"][0]
        assert record["input_tokens"] == 200
        assert record["output_tokens"] == 75

    @patch("app.orchestrator.agent_node.model_router")
    def test_record_error_is_false_on_success(self, mock_router):
        mock_model = MagicMock()
        mock_model.invoke.return_value = _mock_response(VALID_NEGOTIATOR_JSON)
        mock_router.get_model.return_value = mock_model

        state = _make_state(turn_order=["Buyer"], agents=[_make_agent_config("Buyer", "Alice")])
        node_fn = create_agent_node("Buyer")
        result = node_fn(state)

        record = result["agent_calls"][0]
        assert record["error"] is False

    @patch("app.orchestrator.agent_node.model_router")
    def test_record_turn_number_matches_state(self, mock_router):
        """Negotiator increments turn_count before speaking, so turn_number = turn_count + 1."""
        mock_model = MagicMock()
        mock_model.invoke.return_value = _mock_response(VALID_NEGOTIATOR_JSON)
        mock_router.get_model.return_value = mock_model

        state = _make_state(turn_order=["Buyer"], turn_count=3, agents=[_make_agent_config("Buyer", "Alice")])
        node_fn = create_agent_node("Buyer")
        result = node_fn(state)

        record = result["agent_calls"][0]
        # Negotiator increments turn_count before recording, so effective turn = 3 + 1 = 4
        assert record["turn_number"] == 4


# ===========================================================================
# Req 3.3: Retry produces 2 AgentCallRecords
# ===========================================================================


class TestRetryTelemetry:
    """First parse fails, retry succeeds → 2 records."""

    @patch("app.orchestrator.agent_node.model_router")
    def test_retry_produces_two_records(self, mock_router):
        mock_model = MagicMock()
        mock_model.invoke.side_effect = [
            _mock_response(INVALID_JSON, input_tokens=80, output_tokens=20),
            _mock_response(VALID_NEGOTIATOR_JSON, input_tokens=120, output_tokens=60),
        ]
        mock_router.get_model.return_value = mock_model

        state = _make_state(turn_order=["Buyer"], agents=[_make_agent_config("Buyer", "Alice")])
        node_fn = create_agent_node("Buyer")
        result = node_fn(state)

        assert len(result["agent_calls"]) == 2

    @patch("app.orchestrator.agent_node.model_router")
    def test_first_record_error_false(self, mock_router):
        """First call succeeded (LLM responded), error=False even though parse failed."""
        mock_model = MagicMock()
        mock_model.invoke.side_effect = [
            _mock_response(INVALID_JSON),
            _mock_response(VALID_NEGOTIATOR_JSON),
        ]
        mock_router.get_model.return_value = mock_model

        state = _make_state(turn_order=["Buyer"], agents=[_make_agent_config("Buyer", "Alice")])
        node_fn = create_agent_node("Buyer")
        result = node_fn(state)

        assert result["agent_calls"][0]["error"] is False

    @patch("app.orchestrator.agent_node.model_router")
    def test_retry_record_error_false_on_successful_parse(self, mock_router):
        """Retry call parsed successfully → error=False on retry record."""
        mock_model = MagicMock()
        mock_model.invoke.side_effect = [
            _mock_response(INVALID_JSON),
            _mock_response(VALID_NEGOTIATOR_JSON),
        ]
        mock_router.get_model.return_value = mock_model

        state = _make_state(turn_order=["Buyer"], agents=[_make_agent_config("Buyer", "Alice")])
        node_fn = create_agent_node("Buyer")
        result = node_fn(state)

        assert result["agent_calls"][1]["error"] is False

    @patch("app.orchestrator.agent_node.model_router")
    def test_retry_record_has_own_tokens(self, mock_router):
        mock_model = MagicMock()
        mock_model.invoke.side_effect = [
            _mock_response(INVALID_JSON, input_tokens=80, output_tokens=20),
            _mock_response(VALID_NEGOTIATOR_JSON, input_tokens=150, output_tokens=70),
        ]
        mock_router.get_model.return_value = mock_model

        state = _make_state(turn_order=["Buyer"], agents=[_make_agent_config("Buyer", "Alice")])
        node_fn = create_agent_node("Buyer")
        result = node_fn(state)

        first, second = result["agent_calls"]
        assert first["input_tokens"] == 80
        assert first["output_tokens"] == 20
        assert second["input_tokens"] == 150
        assert second["output_tokens"] == 70


# ===========================================================================
# Req 3.4: Fallback sets error=True on retry record
# ===========================================================================


class TestFallbackTelemetry:
    """Both calls fail to parse → fallback used, retry record has error=True."""

    @patch("app.orchestrator.agent_node.model_router")
    def test_fallback_sets_error_true_on_retry(self, mock_router):
        mock_model = MagicMock()
        mock_model.invoke.return_value = _mock_response(INVALID_JSON)
        mock_router.get_model.return_value = mock_model

        state = _make_state(turn_order=["Buyer"], agents=[_make_agent_config("Buyer", "Alice")])
        node_fn = create_agent_node("Buyer")
        result = node_fn(state)

        assert len(result["agent_calls"]) == 2
        assert result["agent_calls"][0]["error"] is False
        assert result["agent_calls"][1]["error"] is True


# ===========================================================================
# Req 3.6: Timestamp is valid UTC ISO 8601
# ===========================================================================


class TestTimestampValidity:
    """Timestamp on each record is a valid UTC ISO 8601 string."""

    @patch("app.orchestrator.agent_node.model_router")
    def test_timestamp_is_valid_iso8601(self, mock_router):
        mock_model = MagicMock()
        mock_model.invoke.return_value = _mock_response(VALID_NEGOTIATOR_JSON)
        mock_router.get_model.return_value = mock_model

        state = _make_state(turn_order=["Buyer"], agents=[_make_agent_config("Buyer", "Alice")])
        node_fn = create_agent_node("Buyer")
        result = node_fn(state)

        record = result["agent_calls"][0]
        ts = record["timestamp"]
        # Must parse without error
        parsed = datetime.fromisoformat(ts)
        # Must be UTC (offset-aware with UTC offset)
        assert parsed.tzinfo is not None
        assert parsed.utcoffset().total_seconds() == 0

    @patch("app.orchestrator.agent_node.model_router")
    def test_timestamp_is_recent(self, mock_router):
        """Timestamp should be close to 'now' — not some stale value."""
        mock_model = MagicMock()
        mock_model.invoke.return_value = _mock_response(VALID_NEGOTIATOR_JSON)
        mock_router.get_model.return_value = mock_model

        before = datetime.now(timezone.utc)
        state = _make_state(turn_order=["Buyer"], agents=[_make_agent_config("Buyer", "Alice")])
        node_fn = create_agent_node("Buyer")
        result = node_fn(state)
        after = datetime.now(timezone.utc)

        ts = datetime.fromisoformat(result["agent_calls"][0]["timestamp"])
        assert before <= ts <= after


# ===========================================================================
# Req 3.7: model_id reflects model_overrides
# ===========================================================================


class TestModelOverrides:
    """model_id in the record uses the overridden model when present."""

    @patch("app.orchestrator.agent_node.model_router")
    def test_model_id_uses_override(self, mock_router):
        mock_model = MagicMock()
        mock_model.invoke.return_value = _mock_response(VALID_NEGOTIATOR_JSON)
        mock_router.get_model.return_value = mock_model

        state = _make_state(
            turn_order=["Buyer"],
            agents=[_make_agent_config("Buyer", "Alice")],
            model_overrides={"Buyer": "custom-model-id"},
        )
        node_fn = create_agent_node("Buyer")
        result = node_fn(state)

        record = result["agent_calls"][0]
        assert record["model_id"] == "custom-model-id"

    @patch("app.orchestrator.agent_node.model_router")
    def test_model_id_uses_config_when_no_override(self, mock_router):
        mock_model = MagicMock()
        mock_model.invoke.return_value = _mock_response(VALID_NEGOTIATOR_JSON)
        mock_router.get_model.return_value = mock_model

        state = _make_state(
            turn_order=["Buyer"],
            agents=[_make_agent_config("Buyer", "Alice")],
            model_overrides={},
        )
        node_fn = create_agent_node("Buyer")
        result = node_fn(state)

        record = result["agent_calls"][0]
        assert record["model_id"] == "gemini-3-flash-preview"


# ===========================================================================
# Req 5.1: Telemetry failure does not break _node()
# ===========================================================================


class TestTelemetryFailureResilience:
    """AgentCallRecord validation error must not break the node."""

    @patch("app.orchestrator.agent_node.AgentCallRecord")
    @patch("app.orchestrator.agent_node.model_router")
    def test_node_returns_valid_delta_when_telemetry_fails(self, mock_router, mock_record_cls):
        """Patch AgentCallRecord to raise on construction — node still works."""
        mock_record_cls.side_effect = ValueError("telemetry boom")

        mock_model = MagicMock()
        mock_model.invoke.return_value = _mock_response(VALID_NEGOTIATOR_JSON)
        mock_router.get_model.return_value = mock_model

        state = _make_state(turn_order=["Buyer"], agents=[_make_agent_config("Buyer", "Alice")])
        node_fn = create_agent_node("Buyer")
        result = node_fn(state)

        # Core state delta must still be present
        assert "history" in result
        assert len(result["history"]) == 1
        assert result["history"][0]["role"] == "Buyer"
        assert "turn_count" in result
        assert result["current_offer"] == 300000.0
        # agent_calls should be empty since telemetry failed
        assert result["agent_calls"] == []

    @patch("app.orchestrator.agent_node.AgentCallRecord")
    @patch("app.orchestrator.agent_node.model_router")
    def test_node_returns_turn_count_when_telemetry_fails(self, mock_router, mock_record_cls):
        mock_record_cls.side_effect = RuntimeError("broken telemetry")

        mock_model = MagicMock()
        mock_model.invoke.return_value = _mock_response(VALID_NEGOTIATOR_JSON)
        mock_router.get_model.return_value = mock_model

        state = _make_state(turn_order=["Buyer"], turn_count=5, agents=[_make_agent_config("Buyer", "Alice")])
        node_fn = create_agent_node("Buyer")
        result = node_fn(state)

        # Negotiator increments turn_count: 5 → 6
        assert result["turn_count"] == 6


# ===========================================================================
# Req 5.2: Non-telemetry state fields unchanged by telemetry
# ===========================================================================


class TestNonTelemetryFieldsUnchanged:
    """Telemetry must not alter history, turn_count, deal_status, current_offer, agent_states."""

    @patch("app.orchestrator.agent_node.model_router")
    def test_history_content_unaffected(self, mock_router):
        mock_model = MagicMock()
        mock_model.invoke.return_value = _mock_response(VALID_NEGOTIATOR_JSON)
        mock_router.get_model.return_value = mock_model

        state = _make_state(turn_order=["Buyer"], agents=[_make_agent_config("Buyer", "Alice")])
        node_fn = create_agent_node("Buyer")
        result = node_fn(state)

        entry = result["history"][0]
        assert entry["role"] == "Buyer"
        assert entry["agent_type"] == "negotiator"
        assert entry["content"]["proposed_price"] == 300000.0
        assert entry["content"]["public_message"] == "I offer 300k"

    @patch("app.orchestrator.agent_node.model_router")
    def test_current_offer_set_correctly(self, mock_router):
        mock_model = MagicMock()
        mock_model.invoke.return_value = _mock_response(VALID_NEGOTIATOR_JSON)
        mock_router.get_model.return_value = mock_model

        state = _make_state(turn_order=["Buyer"], agents=[_make_agent_config("Buyer", "Alice")])
        node_fn = create_agent_node("Buyer")
        result = node_fn(state)

        assert result["current_offer"] == 300000.0

    @patch("app.orchestrator.agent_node.model_router")
    def test_agent_states_updated_correctly(self, mock_router):
        mock_model = MagicMock()
        mock_model.invoke.return_value = _mock_response(VALID_NEGOTIATOR_JSON)
        mock_router.get_model.return_value = mock_model

        state = _make_state(turn_order=["Buyer"], agents=[_make_agent_config("Buyer", "Alice")])
        node_fn = create_agent_node("Buyer")
        result = node_fn(state)

        assert result["agent_states"]["Buyer"]["last_proposed_price"] == 300000.0

    @patch("app.orchestrator.agent_node.model_router")
    def test_turn_count_incremented_for_negotiator(self, mock_router):
        mock_model = MagicMock()
        mock_model.invoke.return_value = _mock_response(VALID_NEGOTIATOR_JSON)
        mock_router.get_model.return_value = mock_model

        state = _make_state(turn_order=["Buyer"], turn_count=2, agents=[_make_agent_config("Buyer", "Alice")])
        node_fn = create_agent_node("Buyer")
        result = node_fn(state)

        assert result["turn_count"] == 3

    @patch("app.orchestrator.agent_node.model_router")
    def test_deal_status_not_set_by_negotiator(self, mock_router):
        """Negotiator node does not set deal_status (only regulator does)."""
        mock_model = MagicMock()
        mock_model.invoke.return_value = _mock_response(VALID_NEGOTIATOR_JSON)
        mock_router.get_model.return_value = mock_model

        state = _make_state(turn_order=["Buyer"], agents=[_make_agent_config("Buyer", "Alice")])
        node_fn = create_agent_node("Buyer")
        result = node_fn(state)

        assert "deal_status" not in result

    @patch("app.orchestrator.agent_node.model_router")
    def test_total_tokens_used_accumulated(self, mock_router):
        """total_tokens_used should include tokens from this call."""
        mock_model = MagicMock()
        mock_model.invoke.return_value = _mock_response(VALID_NEGOTIATOR_JSON, input_tokens=100, output_tokens=50)
        mock_router.get_model.return_value = mock_model

        state = _make_state(turn_order=["Buyer"], agents=[_make_agent_config("Buyer", "Alice")])
        node_fn = create_agent_node("Buyer")
        result = node_fn(state)

        assert result["total_tokens_used"] == 150


# ===========================================================================
# Coverage boost: _extract_text_from_content edge cases
# ===========================================================================

from app.orchestrator.agent_node import _extract_text_from_content, _fallback_output


class TestExtractTextFromContent:
    """Cover the list-of-blocks and fallback branches."""

    def test_plain_string(self):
        assert _extract_text_from_content("hello") == "hello"

    def test_list_of_text_blocks(self):
        """Anthropic/Claude via Vertex returns list of dicts."""
        content = [
            {"type": "text", "text": "first part"},
            {"type": "text", "text": "second part"},
        ]
        assert _extract_text_from_content(content) == "first part\nsecond part"

    def test_list_of_plain_strings(self):
        content = ["hello", "world"]
        assert _extract_text_from_content(content) == "hello\nworld"

    def test_list_mixed_blocks_and_strings(self):
        content = [{"type": "text", "text": "block"}, "plain"]
        assert _extract_text_from_content(content) == "block\nplain"

    def test_list_with_non_text_block_ignored(self):
        """Non-text blocks (e.g. tool_use) should be skipped."""
        content = [{"type": "tool_use", "id": "123"}, {"type": "text", "text": "real"}]
        assert _extract_text_from_content(content) == "real"

    def test_empty_list_falls_through(self):
        """Empty list → str() fallback."""
        assert _extract_text_from_content([]) == "[]"

    def test_non_string_non_list_falls_through(self):
        """Integer or other type → str() fallback."""
        assert _extract_text_from_content(42) == "42"


# ===========================================================================
# Coverage boost: _fallback_output for regulator and observer
# ===========================================================================


class TestFallbackOutput:
    """Cover regulator and observer fallback branches."""

    def test_regulator_fallback(self):
        result = _fallback_output("regulator", "Carol")
        assert result.status == "CLEAR"
        assert "Carol" in result.reasoning

    def test_observer_fallback(self):
        result = _fallback_output("observer", "Dave")
        assert result.observation is not None
        assert "Dave" in result.observation

    def test_negotiator_fallback_recovers_last_price(self):
        from app.orchestrator.state import NegotiationState

        state = _make_state(
            turn_order=["Buyer"],
            agents=[_make_agent_config("Buyer", "Alice")],
            agent_states={
                "Buyer": {
                    "role": "Buyer", "name": "Alice", "agent_type": "negotiator",
                    "model_id": "m", "last_proposed_price": 50000.0, "warning_count": 0,
                },
            },
        )
        result = _fallback_output("negotiator", "Alice", state, "Buyer")
        assert result.proposed_price == 50000.0

    def test_negotiator_fallback_no_state(self):
        result = _fallback_output("negotiator", "Alice")
        assert result.proposed_price == 0.0


# ===========================================================================
# Coverage boost: retry invoke itself throws (exception path)
# ===========================================================================


class TestRetryInvokeException:
    """When model.invoke() itself throws on retry, fallback + error record."""

    @patch("app.orchestrator.agent_node.model_router")
    def test_retry_invoke_exception_produces_error_record(self, mock_router):
        """First call returns bad JSON, retry invoke raises → fallback + error=True record."""
        mock_model = MagicMock()
        mock_model.invoke.side_effect = [
            _mock_response(INVALID_JSON),  # first call: bad JSON
            RuntimeError("LLM service unavailable"),  # retry invoke throws
        ]
        mock_router.get_model.return_value = mock_model

        state = _make_state(turn_order=["Buyer"], agents=[_make_agent_config("Buyer", "Alice")])
        node_fn = create_agent_node("Buyer")
        result = node_fn(state)

        # Should still return a valid state delta with fallback
        assert "history" in result
        assert "gathering their thoughts" in result["history"][0]["content"]["inner_thought"]
        # Should have 2 records: first call + failed retry
        assert len(result["agent_calls"]) == 2
        assert result["agent_calls"][0]["error"] is False
        assert result["agent_calls"][1]["error"] is True
        assert result["agent_calls"][1]["latency_ms"] == 0
        assert result["agent_calls"][1]["input_tokens"] == 0

    @patch("app.orchestrator.agent_node.model_router")
    def test_regulator_telemetry_records_correct_type(self, mock_router):
        """Regulator node produces agent_calls with agent_type='regulator'."""
        mock_model = MagicMock()
        mock_model.invoke.return_value = _mock_response(
            '{"status": "CLEAR", "reasoning": "all good"}'
        )
        mock_router.get_model.return_value = mock_model

        agents = [
            _make_agent_config("Buyer", "Alice"),
            _make_agent_config("Regulator", "Carol", "regulator", "claude-sonnet-4-6"),
        ]
        agent_states = {
            "Buyer": {"role": "Buyer", "name": "Alice", "agent_type": "negotiator", "model_id": "gemini-3-flash-preview", "last_proposed_price": 0.0, "warning_count": 0},
            "Regulator": {"role": "Regulator", "name": "Carol", "agent_type": "regulator", "model_id": "claude-sonnet-4-6", "last_proposed_price": 0.0, "warning_count": 0},
        }
        state = _make_state(
            turn_order=["Buyer", "Regulator"],
            turn_order_index=1,
            agents=agents,
            agent_states=agent_states,
        )
        node_fn = create_agent_node("Regulator")
        result = node_fn(state)

        assert len(result["agent_calls"]) == 1
        record = result["agent_calls"][0]
        assert record["agent_type"] == "regulator"
        assert record["agent_role"] == "Regulator"
        assert record["model_id"] == "claude-sonnet-4-6"
