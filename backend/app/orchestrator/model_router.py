"""Configuration-driven Vertex AI model router.

Maps ``model_id`` strings to initialised LangChain chat model instances,
selecting the correct class based on the model-family prefix (the part
before the first ``-``).
"""

from __future__ import annotations

import logging
import os

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_google_vertexai import ChatVertexAI
from langchain_google_vertexai.model_garden import ChatAnthropicVertex

from app.orchestrator.exceptions import ModelNotAvailableError

logger = logging.getLogger(__name__)

# Prefix before the first '-' → LangChain class
MODEL_FAMILIES: dict[str, type] = {
    "gemini": ChatVertexAI,
    "claude": ChatAnthropicVertex,
}

# Families that receive a ``timeout`` kwarg (Gemini).
# Claude/Anthropic models get ``max_output_tokens`` instead.
_GEMINI_FAMILY = "gemini"
_CLAUDE_FAMILY = "claude"


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


def _instantiate_model(
    model_id: str,
    project: str,
    location: str,
    timeout: float,
) -> BaseChatModel:
    """Create a LangChain chat model instance for *model_id*."""
    cls = _resolve_family(model_id)
    prefix = _get_family_prefix(model_id)

    kwargs: dict = {
        "model_name": model_id,
        "project": project,
        "location": location,
    }

    if prefix == _GEMINI_FAMILY:
        kwargs["timeout"] = timeout
    elif prefix == _CLAUDE_FAMILY:
        kwargs["max_output_tokens"] = 4096

    return cls(**kwargs)  # type: ignore[return-value]


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
        Model identifier whose prefix (before the first ``-``) determines
        the LangChain class (``gemini`` → ``ChatVertexAI``,
        ``claude`` → ``ChatAnthropicVertex``).
    fallback_model_id:
        Optional fallback.  If the primary model cannot be instantiated,
        the router tries this model before raising.
    project:
        GCP project.  Defaults to ``GOOGLE_CLOUD_PROJECT`` env var.
    location:
        Vertex AI region.  Defaults to ``VERTEX_AI_LOCATION`` env var
        (or ``us-central1``). Claude models use ``VERTEX_AI_CLAUDE_LOCATION``
        (or ``us-east5``) since Anthropic models have different region support.

    Returns
    -------
    BaseChatModel
        A ready-to-use LangChain chat model instance.

    Raises
    ------
    ModelNotAvailableError
        If neither the primary nor the fallback model can be created.
    """
    resolved_project = project or os.environ.get("GOOGLE_CLOUD_PROJECT", "")
    resolved_location = location or os.environ.get("VERTEX_AI_LOCATION", "us-central1")
    claude_location = os.environ.get("VERTEX_AI_CLAUDE_LOCATION", "us-east5")
    timeout = float(os.environ.get("VERTEX_AI_REQUEST_TIMEOUT_SECONDS", "60"))

    # Log a note about slow-request warning threshold (actual monitoring
    # happens at invocation time, but we configure the timeout here).
    if timeout > 30:
        logger.debug(
            "Model router: timeout=%.0fs for '%s'. "
            "Requests exceeding 30s will be flagged as slow.",
            timeout,
            model_id,
        )

    try:
        # Use Claude-specific region for Anthropic models
        effective_location = claude_location if _get_family_prefix(model_id) == _CLAUDE_FAMILY else resolved_location
        return _instantiate_model(model_id, resolved_project, effective_location, timeout)
    except ModelNotAvailableError:
        if fallback_model_id is not None:
            logger.warning(
                "Primary model '%s' not available, trying fallback '%s'",
                model_id,
                fallback_model_id,
            )
            try:
                fb_location = claude_location if _get_family_prefix(fallback_model_id) == _CLAUDE_FAMILY else resolved_location
                return _instantiate_model(
                    fallback_model_id, resolved_project, fb_location, timeout
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
                fb_location = claude_location if _get_family_prefix(fallback_model_id) == _CLAUDE_FAMILY else resolved_location
                return _instantiate_model(
                    fallback_model_id, resolved_project, fb_location, timeout
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
