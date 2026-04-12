"""Model mapping for local-mode LLM routing.

Translates scenario ``model_id`` values (e.g. ``gemini-3-flash-preview``) to
provider-specific model strings based on the active ``LLM_PROVIDER``.
"""

from __future__ import annotations

import json
import logging
import os

logger = logging.getLogger(__name__)

_ollama_model = os.environ.get("OLLAMA_MODEL", "llama3.1")

# Scenario model_id → provider model string
DEFAULT_MODEL_MAP: dict[str, dict[str, str]] = {
    "openai": {
        "gemini-3-flash-preview": "gpt-4o-mini",
        "gemini-3.1-flash-lite-preview": "gpt-4o-mini",
        "gemini-3.1-pro-preview": "gpt-4o",
        "claude-3-5-sonnet": "gpt-4o",
        "claude-sonnet-4": "gpt-4o",
    },
    "anthropic": {
        "gemini-3-flash-preview": "claude-3-5-haiku-20241022",
        "gemini-3.1-flash-lite-preview": "claude-3-5-haiku-20241022",
        "gemini-3.1-pro-preview": "claude-sonnet-4-20250514",
        "claude-3-5-sonnet": "claude-3-5-sonnet-20241022",
        "claude-sonnet-4": "claude-sonnet-4-20250514",
    },
    "ollama": {
        "gemini-3-flash-preview": f"ollama/{_ollama_model}",
        "gemini-3.1-flash-lite-preview": f"ollama/{_ollama_model}",
        "gemini-3.1-pro-preview": f"ollama/{_ollama_model}",
        "claude-3-5-sonnet": f"ollama/{_ollama_model}",
        "claude-sonnet-4": f"ollama/{_ollama_model}",
    },
}

# Provider default models used as last-resort fallback
_PROVIDER_DEFAULTS: dict[str, str] = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-3-5-haiku-20241022",
    "ollama": f"ollama/{_ollama_model}",
}


def resolve_model_id(
    model_id: str,
    provider: str,
    model_override: str = "",
    model_map_json: str = "",
    ollama_model: str | None = None,
) -> str:
    """Resolve a scenario *model_id* to a provider-specific model string.

    Resolution order:
    1. *model_override* (``LLM_MODEL_OVERRIDE``) — single model for all agents
    2. *model_map_json* (``MODEL_MAP``) — per-model-id JSON overrides
    3. ``DEFAULT_MODEL_MAP[provider][model_id]`` — built-in defaults
    4. Provider default model + warning log

    Parameters
    ----------
    model_id:
        The scenario model identifier (e.g. ``gemini-3-flash-preview``).
    provider:
        The LLM provider name (e.g. ``ollama``, ``openai``, ``anthropic``).
    model_override:
        If non-empty, returned directly (overrides everything).
    model_map_json:
        JSON string with per-model-id overrides.
    ollama_model:
        Ollama model name override. When provided and *provider* is
        ``ollama``, the default map entries are dynamically replaced
        with ``ollama/{ollama_model}``.
    """
    # 1. Global override
    if model_override:
        return model_override

    # 2. MODEL_MAP JSON override
    if model_map_json:
        try:
            custom_map: dict[str, str] = json.loads(model_map_json)
            if model_id in custom_map:
                return custom_map[model_id]
        except (json.JSONDecodeError, TypeError):
            logger.warning("Invalid MODEL_MAP JSON, ignoring: %s", model_map_json)

    # 3. Default mapping (with dynamic ollama_model support)
    provider_map = DEFAULT_MODEL_MAP.get(provider, {})
    if provider == "ollama" and ollama_model is not None:
        # Build dynamic map for the given ollama_model
        if model_id in provider_map:
            return f"ollama/{ollama_model}"
    elif model_id in provider_map:
        return provider_map[model_id]

    # 4. Provider default + warning
    default = _PROVIDER_DEFAULTS.get(provider)
    if provider == "ollama" and ollama_model is not None:
        default = f"ollama/{ollama_model}"

    if default:
        logger.warning(
            "No mapping for model_id '%s' with provider '%s'. "
            "Falling back to provider default: %s",
            model_id,
            provider,
            default,
        )
        return default

    # Truly unknown provider — still return something reasonable
    logger.warning(
        "Unknown provider '%s' and no mapping for model_id '%s'. "
        "Using model_id as-is.",
        provider,
        model_id,
    )
    return model_id
