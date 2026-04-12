"""Canonical registry of available model IDs.

Single source of truth for which ``model_id`` values are valid in scenario
JSON files.  Both cloud mode (Vertex AI) and local mode (LiteLLM mapping)
reference this list.

Add new models here when they become available — the builder prompt,
Pydantic validators, ``/models`` endpoint, and health checks all derive
from this module automatically.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelEntry:
    """A supported model with its family prefix and human-readable label."""

    model_id: str
    family: str
    label: str


# ── Canonical model list ────────────────────────────────────────────────────
# Keep sorted by family then capability tier (flash < pro).

AVAILABLE_MODELS: tuple[ModelEntry, ...] = (
    ModelEntry("gemini-3-flash-preview", "gemini", "Gemini 3 Flash (Preview)"),
    ModelEntry("gemini-3.1-flash-lite-preview", "gemini", "Gemini 3.1 Flash Lite (Preview)"),
    ModelEntry("gemini-3.1-pro-preview", "gemini", "Gemini 3.1 Pro (Preview)"),
    ModelEntry("claude-3-5-sonnet", "claude", "Claude 3.5 Sonnet"),
    ModelEntry("claude-sonnet-4", "claude", "Claude Sonnet 4"),
)

# Fast lookup set for validators
VALID_MODEL_IDS: frozenset[str] = frozenset(m.model_id for m in AVAILABLE_MODELS)

# Formatted string for injection into LLM prompts
MODELS_PROMPT_BLOCK: str = "\n".join(
    f"  - `{m.model_id}` ({m.label})" for m in AVAILABLE_MODELS
)


def filter_models_prompt_block(allowed_model_ids: frozenset[str]) -> str:
    """Return a MODELS_PROMPT_BLOCK filtered to only allowed model IDs.

    Lines are kept in registry order. If ``allowed_model_ids`` is empty the
    result is an empty string.
    """
    return "\n".join(
        f"  - `{m.model_id}` ({m.label})"
        for m in AVAILABLE_MODELS
        if m.model_id in allowed_model_ids
    )
