"""Unit tests and property tests for the model router.

These tests exercise the **cloud-mode** Vertex AI routing logic.
They patch ``RUN_MODE`` to ``cloud`` so that the real GCP LangChain
classes are loaded into ``MODEL_FAMILIES``.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from langchain_core.language_models.chat_models import BaseChatModel

# Force cloud mode for these tests so MODEL_FAMILIES has real GCP classes.
# We need to patch settings *before* importing model_router.
# Since model_router is already imported at module level, we patch
# MODEL_FAMILIES directly with the real classes for cloud-mode tests.
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_google_vertexai.model_garden import ChatAnthropicVertex

from app.orchestrator.exceptions import ModelNotAvailableError
from app.orchestrator.model_router import (
    MODEL_FAMILIES,
    _resolve_family,
    get_model,
)

_FAMILIES_PATH = "app.orchestrator.model_router.MODEL_FAMILIES"

# Real cloud-mode families for patching
_CLOUD_FAMILIES: dict[str, type] = {
    "gemini": ChatGoogleGenerativeAI,
    "claude": ChatAnthropicVertex,
}


def _make_mock_model() -> MagicMock:
    """Return a MagicMock that passes ``isinstance(..., BaseChatModel)``."""
    return MagicMock(spec=BaseChatModel)


def _mock_families() -> dict[str, MagicMock]:
    """Create mock classes for both model families."""
    return {
        "gemini": MagicMock(return_value=_make_mock_model()),
        "claude": MagicMock(return_value=_make_mock_model()),
    }


_SETTINGS_PATH = "app.orchestrator.model_router.settings"


# -------------------------------------------------------------------
# 4.2  Model family detection
# -------------------------------------------------------------------
class TestResolveFamily:
    def test_gemini_prefix(self) -> None:
        with patch.dict(_FAMILIES_PATH, _CLOUD_FAMILIES):
            assert _resolve_family("gemini-3-flash-preview") is ChatGoogleGenerativeAI

    def test_claude_prefix(self) -> None:
        with patch.dict(_FAMILIES_PATH, _CLOUD_FAMILIES):
            assert _resolve_family("claude-3-5-sonnet-v2") is ChatAnthropicVertex

    def test_unknown_prefix_raises(self) -> None:
        with patch.dict(_FAMILIES_PATH, _CLOUD_FAMILIES):
            with pytest.raises(ModelNotAvailableError) as exc_info:
                _resolve_family("llama-3-70b")
            assert "llama" in str(exc_info.value)

    def test_no_dash_uses_whole_string(self) -> None:
        with patch.dict(_FAMILIES_PATH, _CLOUD_FAMILIES):
            with pytest.raises(ModelNotAvailableError):
                _resolve_family("unknownmodel")


# -------------------------------------------------------------------
# 4.1 / 4.5  get_model — valid model_ids
# -------------------------------------------------------------------
class TestGetModelValid:
    def test_gemini_flash(self) -> None:
        fam = _mock_families()
        with patch.dict(_FAMILIES_PATH, fam), \
             patch(f"{_SETTINGS_PATH}.RUN_MODE", "cloud"):
            model = get_model("gemini-3-flash-preview", project="proj", location="us-central1")
        fam["gemini"].assert_called_once()
        kw = fam["gemini"].call_args.kwargs
        assert kw["model"] == "gemini-3-flash-preview"
        assert kw["project"] == "proj"
        assert kw["location"] == "global"  # Gemini always uses global endpoint
        assert "timeout" in kw
        assert isinstance(model, BaseChatModel)

    def test_gemini_pro(self) -> None:
        fam = _mock_families()
        with patch.dict(_FAMILIES_PATH, fam), \
             patch(f"{_SETTINGS_PATH}.RUN_MODE", "cloud"):
            model = get_model("gemini-3.1-pro-preview", project="proj", location="eu")
        assert isinstance(model, BaseChatModel)

    def test_claude_sonnet_v2(self) -> None:
        fam = _mock_families()
        with patch.dict(_FAMILIES_PATH, fam), \
             patch(f"{_SETTINGS_PATH}.RUN_MODE", "cloud"):
            model = get_model("claude-3-5-sonnet-v2", project="proj", location="eu")
        fam["claude"].assert_called_once()
        kw = fam["claude"].call_args.kwargs
        assert kw["model_name"] == "claude-3-5-sonnet-v2"
        assert kw["max_output_tokens"] == 4096
        assert isinstance(model, BaseChatModel)

    def test_claude_sonnet_4(self) -> None:
        fam = _mock_families()
        with patch.dict(_FAMILIES_PATH, fam), \
             patch(f"{_SETTINGS_PATH}.RUN_MODE", "cloud"):
            model = get_model("claude-sonnet-4-6", project="proj", location="eu")
        assert isinstance(model, BaseChatModel)


# -------------------------------------------------------------------
# 4.5  Unknown model_id raises ModelNotAvailableError
# -------------------------------------------------------------------
class TestGetModelUnknown:
    def test_unknown_model_raises(self) -> None:
        with patch(f"{_SETTINGS_PATH}.RUN_MODE", "cloud"):
            with pytest.raises(ModelNotAvailableError) as exc_info:
                get_model("llama-3-70b")
            assert exc_info.value.model_id == "llama-3-70b"

    def test_empty_string_raises(self) -> None:
        with patch(f"{_SETTINGS_PATH}.RUN_MODE", "cloud"):
            with pytest.raises(ModelNotAvailableError):
                get_model("")


# -------------------------------------------------------------------
# 4.3  Fallback behaviour
# -------------------------------------------------------------------
class TestGetModelFallback:
    def test_fallback_on_primary_instantiation_failure(self) -> None:
        fam = _mock_families()
        fam["gemini"].side_effect = RuntimeError("endpoint down")
        with patch.dict(_FAMILIES_PATH, fam), \
             patch(f"{_SETTINGS_PATH}.RUN_MODE", "cloud"):
            model = get_model(
                "gemini-3-flash-preview",
                fallback_model_id="claude-sonnet-4-6",
                project="proj",
                location="eu",
            )
        assert isinstance(model, BaseChatModel)
        fam["claude"].assert_called_once()

    def test_both_fail_raises(self) -> None:
        fam = _mock_families()
        fam["gemini"].side_effect = RuntimeError("primary down")
        fam["claude"].side_effect = RuntimeError("fallback down")
        with patch.dict(_FAMILIES_PATH, fam), \
             patch(f"{_SETTINGS_PATH}.RUN_MODE", "cloud"):
            with pytest.raises(ModelNotAvailableError) as exc_info:
                get_model(
                    "gemini-3-flash-preview",
                    fallback_model_id="claude-sonnet-4-6",
                    project="proj",
                    location="eu",
                )
        assert "fallback" in str(exc_info.value).lower()

    def test_fallback_on_unknown_primary_with_valid_fallback(self) -> None:
        fam = _mock_families()
        with patch.dict(_FAMILIES_PATH, fam), \
             patch(f"{_SETTINGS_PATH}.RUN_MODE", "cloud"):
            model = get_model(
                "llama-3-70b",
                fallback_model_id="gemini-3-flash-preview",
                project="proj",
                location="eu",
            )
        assert isinstance(model, BaseChatModel)

    def test_fallback_both_unknown_raises(self) -> None:
        with patch(f"{_SETTINGS_PATH}.RUN_MODE", "cloud"):
            with pytest.raises(ModelNotAvailableError):
                get_model("llama-3-70b", fallback_model_id="mistral-7b")


# -------------------------------------------------------------------
# 4.4  Timeout configuration
# -------------------------------------------------------------------
class TestTimeoutConfig:
    def test_default_timeout_60s(self) -> None:
        fam = _mock_families()
        env = {"GOOGLE_CLOUD_PROJECT": "p", "VERTEX_AI_LOCATION": "eu"}
        with patch.dict(os.environ, env, clear=False), \
             patch(f"{_SETTINGS_PATH}.RUN_MODE", "cloud"):
            os.environ.pop("VERTEX_AI_REQUEST_TIMEOUT_SECONDS", None)
            with patch.dict(_FAMILIES_PATH, fam):
                get_model("gemini-3-flash-preview")
        assert fam["gemini"].call_args.kwargs["timeout"] == 60.0

    def test_custom_timeout_from_env(self) -> None:
        fam = _mock_families()
        env = {
            "GOOGLE_CLOUD_PROJECT": "p",
            "VERTEX_AI_LOCATION": "eu",
            "VERTEX_AI_REQUEST_TIMEOUT_SECONDS": "120",
        }
        with patch.dict(os.environ, env, clear=False), \
             patch(f"{_SETTINGS_PATH}.RUN_MODE", "cloud"):
            with patch.dict(_FAMILIES_PATH, fam):
                get_model("gemini-3-flash-preview")
        assert fam["gemini"].call_args.kwargs["timeout"] == 120.0

    def test_env_defaults_for_project_and_location(self) -> None:
        fam = _mock_families()
        env = {"GOOGLE_CLOUD_PROJECT": "my-proj", "VERTEX_AI_LOCATION": "asia-east1"}
        with patch.dict(os.environ, env, clear=False), \
             patch(f"{_SETTINGS_PATH}.RUN_MODE", "cloud"):
            os.environ.pop("VERTEX_AI_REQUEST_TIMEOUT_SECONDS", None)
            with patch.dict(_FAMILIES_PATH, fam):
                get_model("gemini-3-flash-preview")
        kw = fam["gemini"].call_args.kwargs
        assert kw["project"] == "my-proj"
        assert kw["location"] == "global"  # Gemini ignores env location, always global

    def test_location_defaults_to_us_east5(self) -> None:
        """Gemini uses global endpoint; Claude uses resolved location (us-east5 default)."""
        fam = _mock_families()
        env = {"GOOGLE_CLOUD_PROJECT": "p"}
        with patch.dict(os.environ, env, clear=False), \
             patch(f"{_SETTINGS_PATH}.RUN_MODE", "cloud"):
            os.environ.pop("VERTEX_AI_LOCATION", None)
            os.environ.pop("VERTEX_AI_REQUEST_TIMEOUT_SECONDS", None)
            with patch.dict(_FAMILIES_PATH, fam):
                get_model("gemini-3-flash-preview")
        assert fam["gemini"].call_args.kwargs["location"] == "global"

    def test_claude_uses_regional_endpoint(self) -> None:
        """Claude uses the resolved regional location, not global."""
        fam = _mock_families()
        env = {"GOOGLE_CLOUD_PROJECT": "p"}
        with patch.dict(os.environ, env, clear=False), \
             patch(f"{_SETTINGS_PATH}.RUN_MODE", "cloud"):
            os.environ.pop("VERTEX_AI_LOCATION", None)
            os.environ.pop("VERTEX_AI_REQUEST_TIMEOUT_SECONDS", None)
            with patch.dict(_FAMILIES_PATH, fam):
                get_model("claude-sonnet-4-6")
        assert fam["claude"].call_args.kwargs["location"] == "us-east5"


# -------------------------------------------------------------------
# 4.6  Property test P14: Model Router Returns or Raises
# -------------------------------------------------------------------
_VALID_MODEL_IDS = [
    "gemini-3-flash-preview",
    "gemini-3.1-pro-preview",
    "claude-3-5-sonnet-v2",
    "claude-sonnet-4-6",
]

_model_id_strategy = st.one_of(
    st.sampled_from(_VALID_MODEL_IDS),
    st.text(
        alphabet=st.characters(whitelist_categories=("L", "N", "Pd")),
        min_size=1,
        max_size=30,
    ),
)


class TestP14ModelRouterReturnsOrRaises:
    """**Validates: Requirements 6.1, 6.7**

    P14: get_model(model_id) either returns a BaseChatModel instance or
    raises ModelNotAvailableError.  It never returns None.
    """

    @given(model_id=_model_id_strategy)
    @settings(max_examples=100)
    def test_returns_model_or_raises(self, model_id: str) -> None:
        """**Validates: Requirements 6.1, 6.7**"""
        fam = _mock_families()
        with patch.dict(_FAMILIES_PATH, fam), \
             patch(f"{_SETTINGS_PATH}.RUN_MODE", "cloud"):
            try:
                result = get_model(model_id, project="test-proj", location="us-central1")
            except ModelNotAvailableError:
                return
        assert result is not None
        assert isinstance(result, BaseChatModel)
