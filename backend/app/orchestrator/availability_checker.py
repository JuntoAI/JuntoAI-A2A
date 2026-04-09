"""LLM availability checker — startup-time probe layer.

Probes every registered model before the application accepts traffic,
producing a frozen "allowed models" list that gates all downstream
consumers.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone

from langchain_core.messages import HumanMessage

from app.orchestrator.available_models import ModelEntry
from app.orchestrator.model_router import get_model

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProbeResult:
    """Result of a single model availability probe."""

    model_id: str
    family: str
    available: bool
    error: str | None
    latency_ms: float


@dataclass(frozen=True)
class AllowedModels:
    """Immutable snapshot of models that passed the startup probe."""

    entries: tuple[ModelEntry, ...]
    model_ids: frozenset[str]
    probe_results: tuple[ProbeResult, ...]
    probed_at: str


class AvailabilityChecker:
    """Probes registered LLM models and builds an allowed-models snapshot."""

    PROBE_PROMPT: str = "Respond with OK"
    DEFAULT_TIMEOUT: float = 15.0

    async def probe_model(
        self, model_id: str, family: str, timeout: float
    ) -> ProbeResult:
        """Probe a single model. Never raises — returns ProbeResult with error on failure."""
        start = time.perf_counter()
        try:
            model = get_model(model_id)
            await asyncio.wait_for(
                model.ainvoke([HumanMessage(content=self.PROBE_PROMPT)]),
                timeout=timeout,
            )
            latency_ms = (time.perf_counter() - start) * 1000
            return ProbeResult(
                model_id=model_id,
                family=family,
                available=True,
                error=None,
                latency_ms=latency_ms,
            )
        except Exception as exc:
            latency_ms = (time.perf_counter() - start) * 1000
            error_msg = f"{type(exc).__name__}: {exc}" if str(exc) else type(exc).__name__
            logger.warning("Probe failed for model '%s': %s", model_id, error_msg)
            return ProbeResult(
                model_id=model_id,
                family=family,
                available=False,
                error=error_msg,
                latency_ms=latency_ms,
            )

    async def probe_all(
        self,
        models: tuple[ModelEntry, ...],
        timeout: float = DEFAULT_TIMEOUT,
    ) -> AllowedModels:
        """Probe all models concurrently. Returns AllowedModels."""
        tasks = [
            self.probe_model(entry.model_id, entry.family, timeout)
            for entry in models
        ]
        results: list[ProbeResult] = list(await asyncio.gather(*tasks))

        passing_ids = {r.model_id for r in results if r.available}
        # Preserve registry order — filter AVAILABLE_MODELS to only passing model_ids
        entries = tuple(e for e in models if e.model_id in passing_ids)

        available_count = len(entries)
        total_count = len(models)

        logger.info(
            "Model availability probe complete: %d/%d models available",
            available_count,
            total_count,
        )
        for r in results:
            if r.available:
                logger.info(
                    "  ✓ %s (%.0fms)", r.model_id, r.latency_ms
                )
            else:
                logger.warning(
                    "  ✗ %s — %s (%.0fms)", r.model_id, r.error, r.latency_ms
                )

        if available_count == 0:
            logger.error(
                "Zero models passed availability probe — app will run in degraded mode"
            )

        return AllowedModels(
            entries=entries,
            model_ids=frozenset(passing_ids),
            probe_results=tuple(results),
            probed_at=datetime.now(timezone.utc).isoformat(),
        )
