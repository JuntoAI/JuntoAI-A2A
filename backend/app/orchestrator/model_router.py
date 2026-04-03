"""Configuration-driven model router with dual-mode support.

Maps ``model_id`` strings to initialised LangChain chat model instances.

- **Cloud mode** (``RUN_MODE=cloud``): Routes to Vertex AI classes
  (``ChatGoogleGenerativeAI``, ``ChatAnthropicVertex``) — existing behaviour.
- **Local mode** (``RUN_MODE=local``): Routes through LiteLLM via
  ``ChatLiteLLM`` with model IDs translated by the model mapping layer.
"""

from __future__ import annotations

import logging
import os

from langchain_core.language_models.chat_models import BaseChatModel

from app.config import settings
from app.orchestrator.exceptions import ModelNotAvailableError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# MODEL_FAMILIES — kept at module level for backward compatibility.
# In cloud mode the values are the real LangChain classes (populated lazily).
# In local mode the dict is a static placeholder so that code checking
# ``model_id.split("-")[0] in MODEL_FAMILIES`` still works.
# ---------------------------------------------------------------------------
if settings.RUN_MODE == "local":
    # No GCP imports needed — just expose the known prefixes.
    MODEL_FAMILIES: dict[str, type] = {
        "gemini": type("_GeminiPlaceholder", (), {}),
        "claude": type("_ClaudePlaceholder", (), {}),
    }
else:
    # Cloud mode — import the real classes at module level (original behaviour).
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_google_vertexai.model_garden import ChatAnthropicVertex

    MODEL_FAMILIES = {
        "gemini": ChatGoogleGenerativeAI,
        "claude": ChatAnthropicVertex,
    }

# Families that receive a ``timeout`` kwarg (Gemini).
# Claude/Anthropic models get ``max_output_tokens`` instead.
_GEMINI_FAMILY = "gemini"
_CLAUDE_FAMILY = "claude"

# Provider → required API key env var name
_PROVIDER_API_KEYS: dict[str, str] = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
}


def _get_family_prefix(model_id: str) -> str:
    """Return the family prefix for *model_id*."""
    return model_id.split("-", 1)[0] if "-" in model_id else model_id


def _resolve_family(model_id: str) -> type:
    """Return the LangChain class for *model_id* based on its prefix."""
    prefix = _get_family_prefix(model_id)
    cls = MODEL_FAMILIES.get(prefix)
    if cls is None:
        raise ModelNotAvailableError(
            model_id=model_id,
            message=f"Unknown model family prefix '{prefix}'. "
            f"Supported prefixes: {sorted(MODEL_FAMILIES)}",
        )
    return cls


# ---------------------------------------------------------------------------
# Cloud-mode instantiation (unchanged from original)
# ---------------------------------------------------------------------------

def _instantiate_model(
    model_id: str,
    project: str,
    location: str,
    timeout: float,
) -> BaseChatModel:
    """Create a LangChain chat model instance for *model_id* (cloud mode)."""
    cls = _resolve_family(model_id)
    prefix = _get_family_prefix(model_id)

    if prefix == _GEMINI_FAMILY:
        kwargs: dict = {
            "model": model_id,
            "project": project,
            "location": "global",
            "timeout": timeout,
        }
    elif prefix == _CLAUDE_FAMILY:
        kwargs = {
            "model_name": model_id,
            "project": project,
            "location": location,
            "max_output_tokens": 4096,
        }
    else:
        kwargs = {
            "model_name": model_id,
            "project": project,
            "location": location,
        }

    return cls(**kwargs)  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Local-mode instantiation
# ---------------------------------------------------------------------------

def _instantiate_local_model(model_id: str) -> BaseChatModel:
    """Create a ``ChatLiteLLM`` instance for local mode."""
    from langchain_community.chat_models import ChatLiteLLM

    from app.orchestrator.model_mapping import resolve_model_id

    provider = settings.LLM_PROVIDER

    # Check API key for non-Ollama providers
    if provider != "ollama":
        key_env = _PROVIDER_API_KEYS.get(provider)
        if key_env and not os.environ.get(key_env):
            raise ModelNotAvailableError(
                model_id=model_id,
                message=f"Missing {key_env} for provider '{provider}'",
            )

    resolved = resolve_model_id(
        model_id=model_id,
        provider=provider,
        model_override=settings.LLM_MODEL_OVERRIDE,
        model_map_json=settings.MODEL_MAP,
        ollama_model=settings.OLLAMA_MODEL if provider == "ollama" else None,
    )

    kwargs: dict = {"model": resolved}

    if provider == "ollama":
        kwargs["api_base"] = settings.OLLAMA_BASE_URL

    logger.info(
        "Local model router: %s → %s (provider=%s)",
        model_id,
        resolved,
        provider,
    )

    return ChatLiteLLM(**kwargs)  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Public API — signature unchanged
# ---------------------------------------------------------------------------

def get_model(
    model_id: str,
    fallback_model_id: str | None = None,
    project: str | None = None,
    location: str | None = None,
) -> BaseChatModel:
    """Return an initialised LangChain chat model for *model_id*.

    Parameters
    ----------
    model_id:
        Model identifier.  In cloud mode the prefix determines the
        LangChain class.  In local mode it is translated via the model
        mapping layer.
    fallback_model_id:
        Optional fallback.  If the primary model cannot be instantiated,
        the router tries this model before raising.
    project:
        GCP project (cloud mode only).  Defaults to ``GOOGLE_CLOUD_PROJECT``.
    location:
        Vertex AI region (cloud mode only).  Defaults to
        ``VERTEX_AI_LOCATION`` or ``us-east5``.

    Returns
    -------
    BaseChatModel

    Raises
    ------
    ModelNotAvailableError
        If neither the primary nor the fallback model can be created.
    """
    if settings.RUN_MODE == "local":
        return _get_model_local(model_id, fallback_model_id)
    return _get_model_cloud(model_id, fallback_model_id, project, location)


def _get_model_local(
    model_id: str,
    fallback_model_id: str | None = None,
) -> BaseChatModel:
    """Local-mode model instantiation via LiteLLM."""
    try:
        return _instantiate_local_model(model_id)
    except ModelNotAvailableError:
        if fallback_model_id is not None:
            logger.warning(
                "Primary model '%s' not available, trying fallback '%s'",
                model_id,
                fallback_model_id,
            )
            try:
                return _instantiate_local_model(fallback_model_id)
            except Exception as fallback_exc:
                raise ModelNotAvailableError(
                    model_id=model_id,
                    message=(
                        f"Primary model failed and fallback '{fallback_model_id}' "
                        f"also failed: {fallback_exc}"
                    ),
                ) from fallback_exc
        raise
    except Exception as exc:
        if fallback_model_id is not None:
            logger.warning(
                "Primary model '%s' instantiation failed (%s), trying fallback '%s'",
                model_id,
                exc,
                fallback_model_id,
            )
            try:
                return _instantiate_local_model(fallback_model_id)
            except Exception as fallback_exc:
                raise ModelNotAvailableError(
                    model_id=model_id,
                    message=(
                        f"Primary model failed ({exc}) and fallback "
                        f"'{fallback_model_id}' also failed: {fallback_exc}"
                    ),
                ) from fallback_exc
        raise ModelNotAvailableError(
            model_id=model_id,
            message=f"Failed to instantiate model: {exc}",
        ) from exc


def _get_model_cloud(
    model_id: str,
    fallback_model_id: str | None = None,
    project: str | None = None,
    location: str | None = None,
) -> BaseChatModel:
    """Cloud-mode model instantiation via Vertex AI (original logic)."""
    resolved_project = project or os.environ.get("GOOGLE_CLOUD_PROJECT", "")
    resolved_location = location or os.environ.get("VERTEX_AI_LOCATION", "us-east5")
    timeout = float(os.environ.get("VERTEX_AI_REQUEST_TIMEOUT_SECONDS", "60"))

    if timeout > 30:
        logger.debug(
            "Model router: timeout=%.0fs for '%s'. "
            "Requests exceeding 30s will be flagged as slow.",
            timeout,
            model_id,
        )

    try:
        return _instantiate_model(model_id, resolved_project, resolved_location, timeout)
    except ModelNotAvailableError:
        if fallback_model_id is not None:
            logger.warning(
                "Primary model '%s' not available, trying fallback '%s'",
                model_id,
                fallback_model_id,
            )
            try:
                return _instantiate_model(
                    fallback_model_id, resolved_project, resolved_location, timeout
                )
            except Exception as fallback_exc:
                raise ModelNotAvailableError(
                    model_id=model_id,
                    message=(
                        f"Primary model failed and fallback '{fallback_model_id}' "
                        f"also failed: {fallback_exc}"
                    ),
                ) from fallback_exc
        raise
    except Exception as exc:
        if fallback_model_id is not None:
            logger.warning(
                "Primary model '%s' instantiation failed (%s), trying fallback '%s'",
                model_id,
                exc,
                fallback_model_id,
            )
            try:
                return _instantiate_model(
                    fallback_model_id, resolved_project, resolved_location, timeout
                )
            except Exception as fallback_exc:
                raise ModelNotAvailableError(
                    model_id=model_id,
                    message=(
                        f"Primary model failed ({exc}) and fallback "
                        f"'{fallback_model_id}' also failed: {fallback_exc}"
                    ),
                ) from fallback_exc
        raise ModelNotAvailableError(
            model_id=model_id,
            message=f"Failed to instantiate model: {exc}",
        ) from exc
