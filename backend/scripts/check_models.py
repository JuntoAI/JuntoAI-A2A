"""Standalone CLI script to check LLM model availability.

Reuses the same AvailabilityChecker probe logic as the FastAPI startup,
but runs independently — no server required.

Usage:
    python -m scripts.check_models
    python scripts/check_models.py
"""

from __future__ import annotations

import asyncio
import os
import sys

# Ensure the backend directory is on sys.path so `app` is importable
# regardless of how the script is invoked.
_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from app.config import Settings  # noqa: F401, E402 — triggers pydantic-settings .env load
from app.orchestrator.availability_checker import AllowedModels, ProbeResult
from app.orchestrator.available_models import AVAILABLE_MODELS
from app.orchestrator.availability_checker import AvailabilityChecker


# ---------------------------------------------------------------------------
# Pure helper functions (easily testable)
# ---------------------------------------------------------------------------


def format_table(probe_results: tuple[ProbeResult, ...]) -> str:
    """Format probe results as a human-readable table.

    Columns: MODEL_ID | FAMILY | STATUS | ERROR
    """
    if not probe_results:
        return "(no models registered)"

    # Column headers
    header = f"{'MODEL_ID':<40} {'FAMILY':<12} {'STATUS':<6} {'ERROR'}"
    separator = "-" * len(header)

    rows: list[str] = [header, separator]
    for r in probe_results:
        status = "PASS" if r.available else "FAIL"
        error = r.error or ""
        rows.append(f"{r.model_id:<40} {r.family:<12} {status:<6} {error}")

    return "\n".join(rows)


def get_exit_code(probe_results: tuple[ProbeResult, ...]) -> int:
    """Return 0 if all models passed, 1 if any failed or none registered."""
    if not probe_results:
        return 1
    return 0 if all(r.available for r in probe_results) else 1


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------


def main() -> None:
    """Run availability probes and print results."""
    try:
        allowed: AllowedModels = asyncio.run(_run_probes())
    except KeyboardInterrupt:
        sys.exit(1)

    results = allowed.probe_results

    print(format_table(results))
    print()

    total = len(results)
    available = sum(1 for r in results if r.available)
    print(f"{available}/{total} models available")

    sys.exit(get_exit_code(results))


async def _run_probes() -> AllowedModels:
    """Instantiate checker and probe all registered models."""
    checker = AvailabilityChecker()
    return await checker.probe_all(AVAILABLE_MODELS)


if __name__ == "__main__":
    main()
