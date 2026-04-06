"""Property-based tests for model mapping resolution determinism.

Uses Hypothesis to verify that resolve_model_id() always returns a non-empty
string and that model_override always takes precedence.
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.orchestrator.model_mapping import resolve_model_id

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Printable, non-empty text for model identifiers
_model_text = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "Pd")),
    min_size=1,
    max_size=60,
)

# Provider strategy: mix of known providers and arbitrary strings
_provider = st.one_of(
    st.sampled_from(["openai", "anthropic", "ollama"]),
    _model_text,
)

# model_override: either empty (no override) or a non-empty string
_model_override = st.one_of(st.just(""), _model_text)

# model_map_json: empty, valid JSON map, or garbage
_model_map_json = st.one_of(
    st.just(""),
    st.just("not-valid-json{{{"),
    st.dictionaries(
        keys=_model_text,
        values=_model_text,
        min_size=0,
        max_size=5,
    ).map(lambda d: __import__("json").dumps(d)),
)

# ollama_model: None or a non-empty string
_ollama_model = st.one_of(st.none(), _model_text)


# ---------------------------------------------------------------------------
# Feature: 155_test-coverage-hardening
# Property 2: Model mapping resolution determinism
# **Validates: Requirements 4.1, 4.3**
#
# For any combination of model_id, provider, model_override, model_map_json,
# and ollama_model, resolve_model_id() SHALL always return a non-empty string.
# If model_override is non-empty, the return value SHALL equal model_override
# regardless of other parameters.
# ---------------------------------------------------------------------------


@pytest.mark.property
@settings(max_examples=50, deadline=None)
@given(
    model_id=_model_text,
    provider=_provider,
    model_override=_model_override,
    model_map_json=_model_map_json,
    ollama_model=_ollama_model,
)
def test_resolve_model_id_always_returns_nonempty_string(
    model_id: str,
    provider: str,
    model_override: str,
    model_map_json: str,
    ollama_model: str | None,
):
    """resolve_model_id() never returns an empty string for any input combo."""
    result = resolve_model_id(
        model_id=model_id,
        provider=provider,
        model_override=model_override,
        model_map_json=model_map_json,
        ollama_model=ollama_model,
    )
    assert isinstance(result, str), f"Expected str, got {type(result)}"
    assert len(result) > 0, "resolve_model_id() returned an empty string"


@pytest.mark.property
@settings(max_examples=50, deadline=None)
@given(
    model_id=_model_text,
    provider=_provider,
    model_override=_model_text,  # always non-empty
    model_map_json=_model_map_json,
    ollama_model=_ollama_model,
)
def test_model_override_always_wins(
    model_id: str,
    provider: str,
    model_override: str,
    model_map_json: str,
    ollama_model: str | None,
):
    """When model_override is non-empty, it is returned regardless of other params."""
    result = resolve_model_id(
        model_id=model_id,
        provider=provider,
        model_override=model_override,
        model_map_json=model_map_json,
        ollama_model=ollama_model,
    )
    assert result == model_override, (
        f"Expected override '{model_override}', got '{result}'"
    )
