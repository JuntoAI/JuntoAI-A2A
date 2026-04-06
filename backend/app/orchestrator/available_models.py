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
    ModelEntry("gemini-2.5-flash", "gemini", "Gemini 2.5 Flash"),
    ModelEntry("gemini-2.5-pro", "gemini", "Gemini 2.5 Pro"),
    ModelEntry("gemini-3-flash-preview", "gemini", "Gemini 3 Flash (Preview)"),
    ModelEntry("claude-3-5-sonnet", "claude", "Claude 3.5 Sonnet"),
    ModelEntry("claude-sonnet-4", "claude", "Claude Sonnet 4"),
)

# Fast lookup set for validators
VALID_MODEL_IDS: frozenset[str] = frozenset(m.model_id for m in AVAILABLE_MODELS)

# Formatted string for injection into LLM prompts
MODELS_PROMPT_BLOCK: str = "\n".join(
    f"  - `{m.model_id}` ({m.label})" for m in AVAILABLE_MODELS
)
