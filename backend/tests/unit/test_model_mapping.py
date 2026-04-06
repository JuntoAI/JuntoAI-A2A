"""Unit tests for resolve_model_id() — model mapping for local-mode LLM routing."""

import pytest

from app.orchestrator.model_mapping import resolve_model_id


pytestmark = pytest.mark.unit


# --- 1. model_override takes precedence over everything ---


def test_model_override_returns_override():
    result = resolve_model_id(
        model_id="gemini-2.5-flash",
        provider="openai",
        model_override="my-custom-model",
    )
    assert result == "my-custom-model"


def test_model_override_ignores_model_map_json():
    result = resolve_model_id(
        model_id="gemini-2.5-flash",
        provider="openai",
        model_override="forced-model",
        model_map_json='{"gemini-2.5-flash": "should-not-use-this"}',
    )
    assert result == "forced-model"


# --- 2. model_map_json with valid JSON ---


def test_model_map_json_valid_returns_mapped_value():
    result = resolve_model_id(
        model_id="gemini-2.5-flash",
        provider="openai",
        model_map_json='{"gemini-2.5-flash": "custom-mapped-model"}',
    )
    assert result == "custom-mapped-model"


def test_model_map_json_missing_key_falls_through():
    """JSON is valid but doesn't contain the model_id — falls to defaults."""
    result = resolve_model_id(
        model_id="gemini-2.5-flash",
        provider="openai",
        model_map_json='{"some-other-model": "irrelevant"}',
    )
    assert result == "gpt-4o-mini"


# --- 3. model_map_json with invalid JSON ---


def test_model_map_json_invalid_falls_through_to_defaults():
    result = resolve_model_id(
        model_id="gemini-2.5-flash",
        provider="openai",
        model_map_json="not-valid-json{{{",
    )
    assert result == "gpt-4o-mini"


# --- 4. Default mappings per provider ---


def test_default_openai_gemini_flash():
    result = resolve_model_id(model_id="gemini-2.5-flash", provider="openai")
    assert result == "gpt-4o-mini"


def test_default_openai_gemini_pro():
    result = resolve_model_id(model_id="gemini-2.5-pro", provider="openai")
    assert result == "gpt-4o"


def test_default_anthropic_gemini_flash():
    result = resolve_model_id(model_id="gemini-2.5-flash", provider="anthropic")
    assert result == "claude-3-5-haiku-20241022"


def test_default_anthropic_gemini_pro():
    result = resolve_model_id(model_id="gemini-2.5-pro", provider="anthropic")
    assert result == "claude-sonnet-4-20250514"


def test_default_ollama_gemini_flash():
    result = resolve_model_id(model_id="gemini-2.5-flash", provider="ollama")
    assert result.startswith("ollama/")


def test_default_ollama_gemini_pro():
    result = resolve_model_id(model_id="gemini-2.5-pro", provider="ollama")
    assert result.startswith("ollama/")


# --- 5. Unknown model_id → provider default fallback ---


def test_unknown_model_id_openai_falls_to_provider_default():
    result = resolve_model_id(model_id="nonexistent-model", provider="openai")
    assert result == "gpt-4o-mini"


def test_unknown_model_id_anthropic_falls_to_provider_default():
    result = resolve_model_id(model_id="nonexistent-model", provider="anthropic")
    assert result == "claude-3-5-haiku-20241022"


# --- 6. Unknown provider → returns model_id as-is ---


def test_unknown_provider_returns_model_id():
    result = resolve_model_id(model_id="some-model", provider="unknown-provider")
    assert result == "some-model"


# --- 7. ollama_model override → dynamic mapping ---


def test_ollama_model_override_known_model_id():
    result = resolve_model_id(
        model_id="gemini-2.5-flash",
        provider="ollama",
        ollama_model="mistral",
    )
    assert result == "ollama/mistral"


def test_ollama_model_override_unknown_model_id():
    """Unknown model_id with ollama_model override → provider default with override."""
    result = resolve_model_id(
        model_id="nonexistent-model",
        provider="ollama",
        ollama_model="phi3",
    )
    assert result == "ollama/phi3"
