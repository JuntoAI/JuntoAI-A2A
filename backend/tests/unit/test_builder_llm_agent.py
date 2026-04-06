"""Unit tests for BuilderLLMAgent.

# Feature: ai-scenario-builder
# Requirements: 3.3, 3.4, 3.7, 8.1, 8.2
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.builder.events import (
    BuilderCompleteEvent,
    BuilderErrorEvent,
    BuilderJsonDeltaEvent,
    BuilderTokenEvent,
)
from app.builder.llm_agent import (
    BUILDER_SYSTEM_PROMPT,
    BuilderLLMAgent,
    validate_agents_section,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_chunk(content: str) -> MagicMock:
    """Create a mock AIMessageChunk with the given content."""
    from langchain_core.messages import AIMessageChunk

    return AIMessageChunk(content=content)


def _make_mock_model(chunks: list[str] | None = None) -> AsyncMock:
    """Create a mock LLM model that streams the given chunks.

    If chunks is None, streams a simple greeting.
    """
    if chunks is None:
        chunks = ["Hello", "! How ", "can I help?"]

    model = AsyncMock()

    async def fake_astream(messages):
        for text in chunks:
            yield _make_chunk(text)

    model.astream = MagicMock(side_effect=fake_astream)
    return model


def _make_error_model(error: Exception | None = None) -> AsyncMock:
    """Create a mock LLM model that raises an error during streaming."""
    if error is None:
        error = Exception("Vertex AI unavailable")

    model = AsyncMock()

    async def failing_astream(messages):
        raise error
        yield  # noqa: unreachable — makes this an async generator

    model.astream = MagicMock(side_effect=failing_astream)
    return model


# ---------------------------------------------------------------------------
# validate_agents_section tests
# ---------------------------------------------------------------------------


class TestValidateAgentsSection:
    """Tests for the validate_agents_section helper."""

    def test_empty_scenario(self):
        assert validate_agents_section({}) == (False, "At least 2 agents required, but only 0 defined.")

    def test_empty_agents_list(self):
        is_valid, error = validate_agents_section({"agents": []})
        assert is_valid is False
        assert "0 defined" in error

    def test_one_agent(self):
        partial = {"agents": [{"role": "buyer", "type": "negotiator"}]}
        is_valid, error = validate_agents_section(partial)
        assert is_valid is False
        assert "1 defined" in error

    def test_two_agents_no_negotiator(self):
        partial = {"agents": [
            {"role": "reg1", "type": "regulator"},
            {"role": "reg2", "type": "regulator"},
        ]}
        is_valid, error = validate_agents_section(partial)
        assert is_valid is False
        assert "negotiator" in error.lower()

    def test_two_agents_with_negotiator(self):
        partial = {"agents": [
            {"role": "buyer", "type": "negotiator"},
            {"role": "seller", "type": "negotiator"},
        ]}
        is_valid, error = validate_agents_section(partial)
        assert is_valid is True
        assert error == ""

    def test_agents_not_a_list(self):
        is_valid, error = validate_agents_section({"agents": "not a list"})
        assert is_valid is False
        assert "list" in error.lower()


# ---------------------------------------------------------------------------
# BuilderLLMAgent streaming tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_stream_response_produces_token_events():
    """Verify that streaming produces BuilderTokenEvent for each chunk."""
    model = _make_mock_model(["Hello", " world", "!"])
    agent = BuilderLLMAgent(model=model)

    history = [{"role": "user", "content": "Help me build a scenario"}]
    events = []
    async for event in agent.stream_response(history, {}):
        events.append(event)

    token_events = [e for e in events if isinstance(e, BuilderTokenEvent)]
    assert len(token_events) == 3
    assert token_events[0].token == "Hello"
    assert token_events[1].token == " world"
    assert token_events[2].token == "!"

    # Last event should be BuilderCompleteEvent
    assert isinstance(events[-1], BuilderCompleteEvent)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_stream_response_emits_complete_event():
    """Verify BuilderCompleteEvent is emitted at the end of streaming."""
    model = _make_mock_model(["Done"])
    agent = BuilderLLMAgent(model=model)

    events = []
    async for event in agent.stream_response([], {}):
        events.append(event)

    complete_events = [e for e in events if isinstance(e, BuilderCompleteEvent)]
    assert len(complete_events) == 1
    assert complete_events[0].event_type == "builder_complete"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_stream_response_parses_json_delta():
    """Verify JSON delta markers in LLM output produce BuilderJsonDeltaEvent."""
    json_data = '{"id": "my-scenario"}'
    chunks = [
        "Let me set the ID. ",
        f'<<JSON_DELTA:id:{json_data}>>',
        " Done!",
    ]
    model = _make_mock_model(chunks)
    agent = BuilderLLMAgent(model=model)

    events = []
    async for event in agent.stream_response(
        [{"role": "user", "content": "Set the ID to my-scenario"}], {}
    ):
        events.append(event)

    delta_events = [e for e in events if isinstance(e, BuilderJsonDeltaEvent)]
    assert len(delta_events) == 1
    assert delta_events[0].section == "id"
    assert delta_events[0].data == {"id": "my-scenario"}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_stream_response_multiple_json_deltas():
    """Verify multiple JSON delta markers are all parsed."""
    chunks = [
        '<<JSON_DELTA:name:{"name": "Test Scenario"}>>',
        " and ",
        '<<JSON_DELTA:description:{"description": "A test"}>>',
    ]
    model = _make_mock_model(chunks)
    agent = BuilderLLMAgent(model=model)

    events = []
    async for event in agent.stream_response([], {}):
        events.append(event)

    delta_events = [e for e in events if isinstance(e, BuilderJsonDeltaEvent)]
    assert len(delta_events) == 2
    assert delta_events[0].section == "name"
    assert delta_events[1].section == "description"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_stream_response_error_produces_error_event():
    """Verify LLM failure produces BuilderErrorEvent."""
    model = _make_error_model(Exception("Connection timeout"))
    agent = BuilderLLMAgent(model=model)

    events = []
    async for event in agent.stream_response(
        [{"role": "user", "content": "hello"}], {}
    ):
        events.append(event)

    assert len(events) == 1
    assert isinstance(events[0], BuilderErrorEvent)
    assert events[0].event_type == "builder_error"
    assert "Connection timeout" in events[0].message


@pytest.mark.unit
@pytest.mark.asyncio
async def test_linkedin_url_detection_triggers_persona_context():
    """Verify LinkedIn URL in user message adds persona generation context to LLM call."""
    model = _make_mock_model(["Generating persona..."])
    agent = BuilderLLMAgent(model=model)

    history = [
        {"role": "user", "content": "Use this profile: https://www.linkedin.com/in/johndoe"},
    ]

    events = []
    async for event in agent.stream_response(history, {}):
        events.append(event)

    # Verify the model was called
    model.astream.assert_called_once()
    # Check that the system message includes LinkedIn context
    call_args = model.astream.call_args[0][0]
    system_msg = call_args[0]  # First message is SystemMessage
    assert "LinkedIn" in system_msg.content
    assert "persona" in system_msg.content.lower()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_no_linkedin_context_for_regular_messages():
    """Verify no LinkedIn context is added for regular messages."""
    model = _make_mock_model(["Sure!"])
    agent = BuilderLLMAgent(model=model)

    history = [{"role": "user", "content": "I want to build a salary negotiation"}]

    events = []
    async for event in agent.stream_response(history, {}):
        events.append(event)

    call_args = model.astream.call_args[0][0]
    system_msg = call_args[0]
    assert "LinkedIn profile URL" not in system_msg.content


@pytest.mark.unit
@pytest.mark.asyncio
async def test_agent_validation_context_injected():
    """Verify agent validation warning is injected when agents are insufficient."""
    model = _make_mock_model(["You need more agents."])
    agent = BuilderLLMAgent(model=model)

    partial = {"agents": [{"role": "buyer", "type": "negotiator"}]}
    history = [{"role": "user", "content": "Let's move to toggles"}]

    events = []
    async for event in agent.stream_response(history, partial):
        events.append(event)

    call_args = model.astream.call_args[0][0]
    system_msg = call_args[0]
    assert "Agent validation" in system_msg.content
    assert "Do not proceed past the agents section" in system_msg.content


@pytest.mark.unit
@pytest.mark.asyncio
async def test_no_validation_context_when_agents_valid():
    """Verify no validation warning when agents section is valid."""
    model = _make_mock_model(["Great, let's do toggles!"])
    agent = BuilderLLMAgent(model=model)

    partial = {"agents": [
        {"role": "buyer", "type": "negotiator"},
        {"role": "seller", "type": "negotiator"},
    ]}
    history = [{"role": "user", "content": "Let's move to toggles"}]

    events = []
    async for event in agent.stream_response(history, partial):
        events.append(event)

    call_args = model.astream.call_args[0][0]
    system_msg = call_args[0]
    assert "Agent validation" not in system_msg.content


@pytest.mark.unit
@pytest.mark.asyncio
async def test_conversation_history_passed_to_model():
    """Verify conversation history is correctly converted to LLM messages."""
    model = _make_mock_model(["Response"])
    agent = BuilderLLMAgent(model=model)

    history = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there!"},
        {"role": "user", "content": "Build me a scenario"},
    ]

    events = []
    async for event in agent.stream_response(history, {}):
        events.append(event)

    call_args = model.astream.call_args[0][0]
    # SystemMessage + 3 history messages = 4 total
    assert len(call_args) == 4
    assert call_args[1].content == "Hello"
    assert call_args[2].content == "Hi there!"
    assert call_args[3].content == "Build me a scenario"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_partial_scenario_included_in_system_prompt():
    """Verify the partial scenario JSON is included in the system prompt."""
    model = _make_mock_model(["OK"])
    agent = BuilderLLMAgent(model=model)

    partial = {"name": "My Scenario", "description": "A test"}
    events = []
    async for event in agent.stream_response([], partial):
        events.append(event)

    call_args = model.astream.call_args[0][0]
    system_msg = call_args[0]
    assert "My Scenario" in system_msg.content
    assert "A test" in system_msg.content


@pytest.mark.unit
@pytest.mark.asyncio
async def test_invalid_json_delta_is_skipped():
    """Verify malformed JSON in delta markers is skipped gracefully."""
    chunks = [
        '<<JSON_DELTA:name:{invalid json}>>',
        " continuing...",
    ]
    model = _make_mock_model(chunks)
    agent = BuilderLLMAgent(model=model)

    events = []
    async for event in agent.stream_response([], {}):
        events.append(event)

    delta_events = [e for e in events if isinstance(e, BuilderJsonDeltaEvent)]
    assert len(delta_events) == 0

    # Should still complete successfully
    assert isinstance(events[-1], BuilderCompleteEvent)
