"""Property-based tests for model mapping and model router (local mode).

# Feature: 080_a2a-local-battle-arena
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from langchain_core.language_models.chat_models import BaseChatModel

from app.orchestrator.exceptions import ModelNotAvailableError
from app.orchestrator.model_mapping import DEFAULT_MODEL_MAP, resolve_model_id

# Known scenario model_ids used in shipped configs
_SCENARIO_MODEL_IDS = ["gemini-2.5-flash", "gemini-2.5-pro"]

# Supported providers
_SUPPORTED_PROVIDERS = ["openai", "anthropic", "ollama"]

_SETTINGS_PATH = "app.orchestrator.model_router.settings"


# -------------------------------------------------------------------
# Property 4: Model mapping produces valid provider model strings
# -------------------------------------------------------------------
# Feature: 080_a2a-local-battle-arena, Property 4: Model mapping produces valid provider model strings
class TestProperty4ModelMappingValidity:
    """**Validates: Requirements 3.4, 4.1, 9.3**

    For any supported provider and any scenario model_id in the default
    mapping, resolve_model_id() returns a non-empty string.
    """

    @given(
        provider=st.sampled_from(_SUPPORTED_PROVIDERS),
        model_id=st.sampled_from(_SCENARIO_MODEL_IDS),
    )
    @settings(max_examples=100)
    def test_mapping_produces_valid_strings(
        self, provider: str, model_id: str
    ) -> None:
        # Feature: 080_a2a-local-battle-arena, Property 4: Model mapping produces valid provider model strings
        result = resolve_model_id(
            model_id=model_id,
            provider=provider,
            model_override="",
            model_map_json="",
        )
        assert isinstance(result, str)
        assert len(result) > 0


# -------------------------------------------------------------------
# Property 5: Model override takes precedence over mapping
# -------------------------------------------------------------------
# Feature: 080_a2a-local-battle-arena, Property 5: Model override takes precedence over mapping
class TestProperty5OverridePrecedence:
    """**Validates: Requirements 4.2, 4.3**

    For any model_id and non-empty override, resolved model equals
    override regardless of provider/MODEL_MAP. When override is empty
    but MODEL_MAP has an entry, MODEL_MAP takes precedence over default.
    """

    @given(
        model_id=st.sampled_from(_SCENARIO_MODEL_IDS),
        provider=st.sampled_from(_SUPPORTED_PROVIDERS),
        override=st.text(min_size=1, max_size=50).filter(lambda s: s.strip()),
    )
    @settings(max_examples=100)
    def test_override_always_wins(
        self, model_id: str, provider: str, override: str
    ) -> None:
        # Feature: 080_a2a-local-battle-arena, Property 5: Model override takes precedence over mapping
        result = resolve_model_id(
            model_id=model_id,
            provider=provider,
            model_override=override,
            model_map_json='{"gemini-2.5-flash": "should-not-use"}',
        )
        assert result == override

    @given(
        model_id=st.sampled_from(_SCENARIO_MODEL_IDS),
        provider=st.sampled_from(_SUPPORTED_PROVIDERS),
        custom_model=st.text(min_size=1, max_size=50).filter(lambda s: s.strip()),
    )
    @settings(max_examples=100)
    def test_model_map_beats_default(
        self, model_id: str, provider: str, custom_model: str
    ) -> None:
        # Feature: 080_a2a-local-battle-arena, Property 5: Model override takes precedence over mapping
        import json

        model_map = json.dumps({model_id: custom_model})
        result = resolve_model_id(
            model_id=model_id,
            provider=provider,
            model_override="",
            model_map_json=model_map,
        )
        assert result == custom_model


# -------------------------------------------------------------------
# Property 10: Ollama mapping uses OLLAMA_MODEL for all scenario model_ids
# -------------------------------------------------------------------
# Feature: 080_a2a-local-battle-arena, Property 10: Ollama mapping uses OLLAMA_MODEL for all scenario model_ids
class TestProperty10OllamaMapping:
    """**Validates: Requirements 4.2, 15.1, 15.5**

    For any OLLAMA_MODEL value and any scenario model_id in the default
    mapping, when LLM_PROVIDER=ollama, resolve_model_id() returns
    ollama/{OLLAMA_MODEL}.
    """

    @given(
        ollama_model=st.text(
            alphabet=st.characters(whitelist_categories=("L", "N", "Pd")),
            min_size=1,
            max_size=30,
        ),
        model_id=st.sampled_from(_SCENARIO_MODEL_IDS),
    )
    @settings(max_examples=100)
    def test_ollama_uses_ollama_model(
        self, ollama_model: str, model_id: str
    ) -> None:
        # Feature: 080_a2a-local-battle-arena, Property 10: Ollama mapping uses OLLAMA_MODEL for all scenario model_ids
        result = resolve_model_id(
            model_id=model_id,
            provider="ollama",
            model_override="",
            model_map_json="",
            ollama_model=ollama_model,
        )
        assert result == f"ollama/{ollama_model}"


# -------------------------------------------------------------------
# Property 11: Ollama provider requires no API keys
# -------------------------------------------------------------------
# Feature: 080_a2a-local-battle-arena, Property 11: Ollama provider requires no API keys
class TestProperty11OllamaNoApiKeys:
    """**Validates: Requirements 15.3**

    For any configuration where LLM_PROVIDER=ollama, the model router
    does not raise ModelNotAvailableError due to missing API key env vars.
    """

    @given(
        model_id=st.sampled_from(_SCENARIO_MODEL_IDS),
    )
    @settings(max_examples=100)
    def test_ollama_no_api_key_required(self, model_id: str) -> None:
        # Feature: 080_a2a-local-battle-arena, Property 11: Ollama provider requires no API keys
        from app.orchestrator.model_router import get_model

        mock_litellm = MagicMock(spec=BaseChatModel)

        # Ensure no API keys are set
        env_clean = {
            k: v
            for k, v in os.environ.items()
            if k not in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY")
        }

        mock_settings = MagicMock()
        mock_settings.RUN_MODE = "local"
        mock_settings.LLM_PROVIDER = "ollama"
        mock_settings.LLM_MODEL_OVERRIDE = ""
        mock_settings.MODEL_MAP = ""
        mock_settings.OLLAMA_BASE_URL = "http://localhost:11434"
        mock_settings.OLLAMA_MODEL = "llama3.1"

        with patch.dict(os.environ, env_clean, clear=True), \
             patch(_SETTINGS_PATH, mock_settings), \
             patch(
                 "langchain_community.chat_models.ChatLiteLLM",
                 return_value=mock_litellm,
             ):
            # Should NOT raise ModelNotAvailableError
            result = get_model(model_id)
            assert result is mock_litellm
