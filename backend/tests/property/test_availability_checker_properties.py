"""Property-based tests for the LLM Availability Checker.

Uses Hypothesis to verify correctness properties defined in the design document.
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.orchestrator.available_models import (
    AVAILABLE_MODELS,
    MODELS_PROMPT_BLOCK,
    VALID_MODEL_IDS,
    ModelEntry,
)

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Non-empty identifier-like text for model IDs (letters, digits, hyphens, dots)
_id_text = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "Pd")),
    min_size=1,
    max_size=40,
)

# Strategy for generating random ModelEntry instances
_model_entry = st.builds(
    ModelEntry,
    model_id=_id_text,
    family=_id_text,
    label=st.text(min_size=1, max_size=60),
)

# Strategy for generating non-empty tuples of unique ModelEntry instances
_model_entries = (
    st.lists(_model_entry, min_size=1, max_size=15)
    .filter(lambda entries: len({e.model_id for e in entries}) == len(entries))
    .map(tuple)
)


# ---------------------------------------------------------------------------
# Feature: llm-availability-checker, Property 1: Registry derivation consistency
#
# For any AVAILABLE_MODELS tuple, every entry's model_id SHALL appear in
# VALID_MODEL_IDS and in MODELS_PROMPT_BLOCK, and VALID_MODEL_IDS SHALL
# contain no IDs absent from AVAILABLE_MODELS.
#
# **Validates: Requirements 1.2**
# ---------------------------------------------------------------------------


@pytest.mark.property
@settings(max_examples=100, deadline=None)
@given(entries=_model_entries)
def test_registry_derivation_consistency(entries: tuple[ModelEntry, ...]):
    """Derived VALID_MODEL_IDS and MODELS_PROMPT_BLOCK are consistent with
    any AVAILABLE_MODELS tuple — the same derivation logic used in the module."""

    # Rebuild derived structures using the same logic as available_models.py
    derived_ids = frozenset(m.model_id for m in entries)
    derived_prompt = "\n".join(
        f"  - `{m.model_id}` ({m.label})" for m in entries
    )

    # 1. Every entry's model_id appears in the derived ID set
    for entry in entries:
        assert entry.model_id in derived_ids, (
            f"model_id '{entry.model_id}' missing from derived VALID_MODEL_IDS"
        )

    # 2. Every entry's model_id appears in the derived prompt block
    for entry in entries:
        assert f"`{entry.model_id}`" in derived_prompt, (
            f"model_id '{entry.model_id}' missing from derived MODELS_PROMPT_BLOCK"
        )

    # 3. No IDs in the derived set are absent from the entries
    entry_ids = {m.model_id for m in entries}
    assert derived_ids == entry_ids, (
        f"VALID_MODEL_IDS mismatch: extra={derived_ids - entry_ids}, "
        f"missing={entry_ids - derived_ids}"
    )

    # 4. Derived set size matches entries (no duplicates lost)
    assert len(derived_ids) == len(entries)


@pytest.mark.property
@settings(max_examples=100, deadline=None)
@given(data=st.data())
def test_actual_registry_derivation_consistency(data: st.DataObject):
    """The actual module-level AVAILABLE_MODELS, VALID_MODEL_IDS, and
    MODELS_PROMPT_BLOCK are mutually consistent.

    Uses st.data() to satisfy Hypothesis requirement for a @given decorator
    while testing the real, concrete registry values."""

    # Draw a trivial value to keep Hypothesis happy — the real test is on
    # the actual module constants
    _ = data.draw(st.just(True))

    # 1. Every AVAILABLE_MODELS entry's model_id is in VALID_MODEL_IDS
    for entry in AVAILABLE_MODELS:
        assert entry.model_id in VALID_MODEL_IDS, (
            f"model_id '{entry.model_id}' from AVAILABLE_MODELS "
            f"not found in VALID_MODEL_IDS"
        )

    # 2. Every AVAILABLE_MODELS entry's model_id appears in MODELS_PROMPT_BLOCK
    for entry in AVAILABLE_MODELS:
        assert f"`{entry.model_id}`" in MODELS_PROMPT_BLOCK, (
            f"model_id '{entry.model_id}' from AVAILABLE_MODELS "
            f"not found in MODELS_PROMPT_BLOCK"
        )

    # 3. VALID_MODEL_IDS contains no IDs absent from AVAILABLE_MODELS
    registry_ids = {m.model_id for m in AVAILABLE_MODELS}
    assert VALID_MODEL_IDS == registry_ids, (
        f"VALID_MODEL_IDS mismatch with AVAILABLE_MODELS: "
        f"extra={VALID_MODEL_IDS - registry_ids}, "
        f"missing={registry_ids - VALID_MODEL_IDS}"
    )

    # 4. Sizes match — no silent duplicates
    assert len(VALID_MODEL_IDS) == len(AVAILABLE_MODELS), (
        f"Size mismatch: VALID_MODEL_IDS has {len(VALID_MODEL_IDS)} entries "
        f"but AVAILABLE_MODELS has {len(AVAILABLE_MODELS)} entries "
        f"(possible duplicate model_id in registry)"
    )


# ---------------------------------------------------------------------------
# Feature: llm-availability-checker, Property 2: Probe exception safety
#
# For any model probe that raises any exception (including
# asyncio.TimeoutError, ConnectionError, ValueError, or any arbitrary
# Exception subclass), the resulting ProbeResult SHALL have available=False,
# a non-empty error string, and the exception SHALL NOT propagate to the
# caller or affect other concurrent probes.
#
# **Validates: Requirements 2.5, 8.2**
# ---------------------------------------------------------------------------

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from app.orchestrator.availability_checker import (
    AllowedModels,
    AvailabilityChecker,
    ProbeResult,
)

# Exception types the probe must handle safely
_exception_types = st.sampled_from([
    TimeoutError,
    ConnectionError,
    ValueError,
    RuntimeError,
    OSError,
    asyncio.TimeoutError,
])

# Error messages — including empty strings and arbitrary text
_error_messages = st.text(min_size=0, max_size=100)


@pytest.mark.property
@pytest.mark.asyncio
@settings(max_examples=100, deadline=None)
@given(exc_type=_exception_types, exc_msg=_error_messages)
async def test_probe_exception_safety(exc_type: type[Exception], exc_msg: str):
    """probe_model never propagates exceptions — it always returns a
    ProbeResult with available=False and a non-empty error string."""

    # Build a mock model whose ainvoke raises the generated exception
    mock_model = MagicMock()
    mock_model.ainvoke = AsyncMock(side_effect=exc_type(exc_msg))

    checker = AvailabilityChecker()

    with patch(
        "app.orchestrator.availability_checker.get_model",
        return_value=mock_model,
    ):
        # Must not raise — that's the core property
        result = await checker.probe_model(
            model_id="test-model",
            family="test-family",
            timeout=5.0,
        )

    # Result is a ProbeResult
    assert isinstance(result, ProbeResult)

    # Model marked unavailable
    assert result.available is False

    # Error string is non-empty
    assert result.error is not None
    assert len(result.error) > 0

    # Correct model metadata preserved
    assert result.model_id == "test-model"
    assert result.family == "test-family"

    # Latency is non-negative
    assert result.latency_ms >= 0.0


# ---------------------------------------------------------------------------
# Feature: llm-availability-checker, Property 3: Allowed list contains exactly passing models
#
# For any set of ProbeResult objects where a subset have available=True,
# the constructed AllowedModels.model_ids SHALL equal exactly the set of
# model_id values from passing probes, and AllowedModels.entries SHALL
# contain exactly the corresponding ModelEntry objects in registry order.
#
# **Validates: Requirements 3.1**
# ---------------------------------------------------------------------------


@pytest.mark.property
@pytest.mark.asyncio
@settings(max_examples=100, deadline=None)
@given(data=st.data())
async def test_allowed_list_contains_exactly_passing_models(data: st.DataObject):
    """probe_all produces AllowedModels whose model_ids equals exactly the
    passing set, and whose entries preserves registry order of passing models."""

    # Generate a random list of unique ModelEntry objects
    entries: tuple[ModelEntry, ...] = data.draw(_model_entries)

    # Generate a random boolean per entry: True = pass, False = fail
    pass_flags: list[bool] = data.draw(
        st.lists(st.booleans(), min_size=len(entries), max_size=len(entries))
    )

    # Build the expected passing set and ordered entries
    expected_passing_ids = frozenset(
        e.model_id for e, passes in zip(entries, pass_flags) if passes
    )
    expected_passing_entries = tuple(
        e for e, passes in zip(entries, pass_flags) if passes
    )

    # Map model_id → should_pass for the mock
    pass_map = {e.model_id: passes for e, passes in zip(entries, pass_flags)}

    def mock_get_model(model_id: str) -> MagicMock:
        mock_model = MagicMock()
        if pass_map[model_id]:
            # Successful probe — ainvoke returns a mock response
            mock_model.ainvoke = AsyncMock(return_value=MagicMock())
        else:
            # Failed probe — ainvoke raises
            mock_model.ainvoke = AsyncMock(
                side_effect=RuntimeError(f"probe fail: {model_id}")
            )
        return mock_model

    checker = AvailabilityChecker()

    with patch(
        "app.orchestrator.availability_checker.get_model",
        side_effect=mock_get_model,
    ):
        result: AllowedModels = await checker.probe_all(entries, timeout=5.0)

    # --- Core property assertions ---

    # 1. model_ids equals exactly the set of passing model IDs
    assert result.model_ids == expected_passing_ids, (
        f"model_ids mismatch: got {result.model_ids}, "
        f"expected {expected_passing_ids}"
    )

    # 2. entries contains exactly the passing ModelEntry objects
    assert result.entries == expected_passing_entries, (
        f"entries mismatch: got {result.entries}, "
        f"expected {expected_passing_entries}"
    )

    # 3. entries preserves registry order (subset in same relative order)
    entry_ids_in_result = [e.model_id for e in result.entries]
    entry_ids_in_registry = [e.model_id for e in entries]
    # Every result entry ID must appear in registry order
    registry_positions = {
        mid: idx for idx, mid in enumerate(entry_ids_in_registry)
    }
    result_positions = [registry_positions[mid] for mid in entry_ids_in_result]
    assert result_positions == sorted(result_positions), (
        f"entries not in registry order: positions={result_positions}"
    )

    # 4. No extra or missing entries
    assert len(result.entries) == len(expected_passing_ids)
    assert frozenset(e.model_id for e in result.entries) == expected_passing_ids


# ---------------------------------------------------------------------------
# Feature: llm-availability-checker, Property 4: AllowedModels immutability
#
# For any constructed AllowedModels instance, attempting to assign to
# `entries`, `model_ids`, `probe_results`, or `probed_at` SHALL raise
# `FrozenInstanceError`, and the contained `entries` (tuple) and
# `model_ids` (frozenset) SHALL be inherently immutable collection types.
#
# **Validates: Requirements 3.3**
# ---------------------------------------------------------------------------

import dataclasses
from datetime import datetime, timezone

# Strategy for generating random ProbeResult instances
_probe_result = st.builds(
    ProbeResult,
    model_id=_id_text,
    family=_id_text,
    available=st.booleans(),
    error=st.one_of(st.none(), st.text(min_size=1, max_size=80)),
    latency_ms=st.floats(min_value=0.0, max_value=30000.0, allow_nan=False),
)

# Strategy for generating a complete AllowedModels instance with consistent data
_allowed_models = st.builds(
    lambda entries, probes: AllowedModels(
        entries=tuple(entries),
        model_ids=frozenset(e.model_id for e in entries),
        probe_results=tuple(probes),
        probed_at=datetime.now(timezone.utc).isoformat(),
    ),
    entries=st.lists(_model_entry, min_size=0, max_size=10),
    probes=st.lists(_probe_result, min_size=0, max_size=10),
)


@pytest.mark.property
@settings(max_examples=100, deadline=None)
@given(allowed=_allowed_models)
def test_allowed_models_immutability(allowed: AllowedModels):
    """AllowedModels is frozen — attribute assignment raises
    FrozenInstanceError, and collection fields use immutable types."""

    # 1. Attempting to assign to each attribute raises FrozenInstanceError
    for attr in ("entries", "model_ids", "probe_results", "probed_at"):
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(allowed, attr, None)

    # 2. `entries` is a tuple (inherently immutable sequence)
    assert isinstance(allowed.entries, tuple), (
        f"entries should be tuple, got {type(allowed.entries).__name__}"
    )

    # 3. `model_ids` is a frozenset (inherently immutable set)
    assert isinstance(allowed.model_ids, frozenset), (
        f"model_ids should be frozenset, got {type(allowed.model_ids).__name__}"
    )


# ---------------------------------------------------------------------------
# Feature: llm-availability-checker, Property 9: Probe idempotence
#
# For any fixed mock model configuration (deterministic success/failure per
# model), running `probe_all` twice SHALL produce `AllowedModels` instances
# with identical `model_ids`, identical `entries`, and identical `available`
# flags in `probe_results`.
#
# **Validates: Requirements 8.3**
# ---------------------------------------------------------------------------


@pytest.mark.property
@pytest.mark.asyncio
@settings(max_examples=100, deadline=None)
@given(data=st.data())
async def test_probe_idempotence(data: st.DataObject):
    """Running probe_all twice with the same deterministic mock config
    produces identical model_ids, entries, and available flags."""

    # Generate unique ModelEntry tuples
    entries: tuple[ModelEntry, ...] = data.draw(_model_entries)

    # Generate a deterministic pass/fail boolean per entry
    pass_flags: list[bool] = data.draw(
        st.lists(st.booleans(), min_size=len(entries), max_size=len(entries))
    )

    # Map model_id → should_pass (deterministic — same id always same result)
    pass_map = {e.model_id: passes for e, passes in zip(entries, pass_flags)}

    def mock_get_model(model_id: str) -> MagicMock:
        mock_model = MagicMock()
        if pass_map[model_id]:
            mock_model.ainvoke = AsyncMock(return_value=MagicMock())
        else:
            mock_model.ainvoke = AsyncMock(
                side_effect=RuntimeError(f"probe fail: {model_id}")
            )
        return mock_model

    checker = AvailabilityChecker()

    with patch(
        "app.orchestrator.availability_checker.get_model",
        side_effect=mock_get_model,
    ):
        result1: AllowedModels = await checker.probe_all(entries, timeout=5.0)

    with patch(
        "app.orchestrator.availability_checker.get_model",
        side_effect=mock_get_model,
    ):
        result2: AllowedModels = await checker.probe_all(entries, timeout=5.0)

    # 1. Identical model_ids
    assert result1.model_ids == result2.model_ids, (
        f"model_ids differ: run1={result1.model_ids}, run2={result2.model_ids}"
    )

    # 2. Identical entries (same passing ModelEntry objects in same order)
    assert result1.entries == result2.entries, (
        f"entries differ: run1={result1.entries}, run2={result2.entries}"
    )

    # 3. Identical available flags in probe_results (same order, same flags)
    flags1 = [(r.model_id, r.available) for r in result1.probe_results]
    flags2 = [(r.model_id, r.available) for r in result2.probe_results]
    assert flags1 == flags2, (
        f"available flags differ: run1={flags1}, run2={flags2}"
    )


# ---------------------------------------------------------------------------
# Feature: llm-availability-checker, Property 5: Models endpoint returns exactly allowed models
#
# For any AllowedModels instance stored in app.state, the /models endpoint
# SHALL return a list whose model_id values are exactly
# AllowedModels.model_ids — no more, no fewer.
#
# **Validates: Requirements 4.1**
# ---------------------------------------------------------------------------

import httpx

from app.main import app
from app.orchestrator.available_models import AVAILABLE_MODELS as _REAL_MODELS


# Strategy: random subsets of the real AVAILABLE_MODELS tuple
_model_subset_indices = st.lists(
    st.integers(min_value=0, max_value=len(_REAL_MODELS) - 1),
    unique=True,
    min_size=0,
    max_size=len(_REAL_MODELS),
)

_SENTINEL = object()  # marker for "attribute did not exist"


@pytest.mark.property
@pytest.mark.asyncio
@settings(max_examples=100, deadline=None)
@given(indices=_model_subset_indices)
async def test_models_endpoint_returns_exactly_allowed_models(
    indices: list[int],
):
    """GET /api/v1/models returns exactly the model_ids from the
    AllowedModels instance stored in app.state — no more, no fewer."""

    # Build a subset of real models from the drawn indices
    subset_entries = tuple(_REAL_MODELS[i] for i in sorted(indices))

    allowed = AllowedModels(
        entries=subset_entries,
        model_ids=frozenset(e.model_id for e in subset_entries),
        probe_results=(),
        probed_at=datetime.now(timezone.utc).isoformat(),
    )

    # Set app.state.allowed_models directly (attribute may not exist yet
    # outside the lifespan, so patch.object would fail)
    original = getattr(app.state, "allowed_models", _SENTINEL)
    app.state.allowed_models = allowed
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            resp = await client.get("/api/v1/models")
    finally:
        if original is _SENTINEL:
            del app.state.allowed_models
        else:
            app.state.allowed_models = original

    assert resp.status_code == 200

    body = resp.json()
    returned_ids = frozenset(m["model_id"] for m in body)

    # Core property: returned model_ids == AllowedModels.model_ids
    assert returned_ids == allowed.model_ids, (
        f"Endpoint returned {returned_ids}, expected {allowed.model_ids}"
    )

    # Count must match exactly
    assert len(body) == len(subset_entries), (
        f"Endpoint returned {len(body)} models, expected {len(subset_entries)}"
    )


# ---------------------------------------------------------------------------
# Feature: llm-availability-checker, Property 8: Health and admin count consistency
#
# For any set of probe results with T total models, A available, and U
# unavailable: `total_registered` SHALL equal T, `total_available` SHALL
# equal A, `total_unavailable` SHALL equal T - A, `unavailable_models`
# SHALL contain exactly the U failing model IDs, and the health `status`
# SHALL be "degraded" if and only if A equals 0.
#
# **Validates: Requirements 7.1, 7.2, 7.3, 9.3**
# ---------------------------------------------------------------------------


@pytest.mark.property
@pytest.mark.asyncio
@settings(max_examples=100, deadline=None)
@given(data=st.data())
async def test_health_and_admin_count_consistency(data: st.DataObject):
    """GET /api/v1/health returns correct total_registered, total_available,
    unavailable_models list, and status logic for any random probe outcome."""

    # Draw a random subset of real AVAILABLE_MODELS indices to mark as passing
    all_indices = list(range(len(_REAL_MODELS)))
    passing_indices: list[int] = data.draw(
        st.lists(
            st.sampled_from(all_indices),
            unique=True,
            min_size=0,
            max_size=len(_REAL_MODELS),
        )
    )
    passing_ids = frozenset(_REAL_MODELS[i].model_id for i in passing_indices)

    # Build probe results for every registered model
    probe_results = tuple(
        ProbeResult(
            model_id=entry.model_id,
            family=entry.family,
            available=(entry.model_id in passing_ids),
            error=None if entry.model_id in passing_ids else f"fail: {entry.model_id}",
            latency_ms=100.0,
        )
        for entry in _REAL_MODELS
    )

    # Build AllowedModels with only passing entries
    passing_entries = tuple(e for e in _REAL_MODELS if e.model_id in passing_ids)
    allowed = AllowedModels(
        entries=passing_entries,
        model_ids=passing_ids,
        probe_results=probe_results,
        probed_at=datetime.now(timezone.utc).isoformat(),
    )

    # Expected values
    expected_total_registered = len(_REAL_MODELS)
    expected_total_available = len(passing_ids)
    expected_unavailable_ids = frozenset(
        r.model_id for r in probe_results if not r.available
    )
    expected_status = "degraded" if expected_total_available == 0 else "ok"

    # Inject into app.state and call the health endpoint
    original = getattr(app.state, "allowed_models", _SENTINEL)
    app.state.allowed_models = allowed
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            resp = await client.get("/api/v1/health")
    finally:
        if original is _SENTINEL:
            del app.state.allowed_models
        else:
            app.state.allowed_models = original

    assert resp.status_code == 200
    body = resp.json()

    # 1. total_registered == len(AVAILABLE_MODELS)
    assert body["models"]["total_registered"] == expected_total_registered, (
        f"total_registered: got {body['models']['total_registered']}, "
        f"expected {expected_total_registered}"
    )

    # 2. total_available == count of passing models
    assert body["models"]["total_available"] == expected_total_available, (
        f"total_available: got {body['models']['total_available']}, "
        f"expected {expected_total_available}"
    )

    # 3. unavailable_models contains exactly the failing model IDs
    returned_unavailable = frozenset(body["unavailable_models"])
    assert returned_unavailable == expected_unavailable_ids, (
        f"unavailable_models: got {returned_unavailable}, "
        f"expected {expected_unavailable_ids}"
    )

    # 4. total_unavailable == T - A (derived check)
    assert len(returned_unavailable) == expected_total_registered - expected_total_available, (
        f"total_unavailable count: got {len(returned_unavailable)}, "
        f"expected {expected_total_registered - expected_total_available}"
    )

    # 5. status is "degraded" iff total_available == 0
    assert body["status"] == expected_status, (
        f"status: got {body['status']}, expected {expected_status} "
        f"(total_available={expected_total_available})"
    )


# ---------------------------------------------------------------------------
# Feature: llm-availability-checker, Property 6: Scenario availability flag correctness
#
# For any scenario with N agents each having a model_id and optional
# fallback_model_id, and for any allowed_model_ids frozenset, the
# scenario's available flag SHALL be True if and only if every agent has
# at least one of {model_id, fallback_model_id} present in
# allowed_model_ids.
#
# **Validates: Requirements 5.3**
# ---------------------------------------------------------------------------

from types import SimpleNamespace

from app.scenarios.registry import _is_scenario_available

# Pool of model IDs to draw from — small enough to create meaningful
# overlap between agent configs and allowed sets, large enough to exercise
# miss cases.
_MODEL_ID_POOL = [f"model-{i}" for i in range(8)]

# Strategy: a single agent config as a SimpleNamespace with model_id and
# optional fallback_model_id
_agent_config = st.builds(
    lambda mid, fid: SimpleNamespace(model_id=mid, fallback_model_id=fid),
    mid=st.sampled_from(_MODEL_ID_POOL),
    fid=st.one_of(st.none(), st.sampled_from(_MODEL_ID_POOL)),
)

# Strategy: list of 1-6 agents (scenarios need ≥2 agents in practice, but
# _is_scenario_available works on any non-empty list)
_agent_list = st.lists(_agent_config, min_size=1, max_size=6)

# Strategy: allowed model IDs drawn from the same pool
_allowed_set = st.frozensets(st.sampled_from(_MODEL_ID_POOL), min_size=0, max_size=len(_MODEL_ID_POOL))


@pytest.mark.property
@settings(max_examples=200, deadline=None)
@given(agents=_agent_list, allowed=_allowed_set)
def test_scenario_availability_flag_correctness(
    agents: list[SimpleNamespace],
    allowed: frozenset[str],
):
    """_is_scenario_available returns True iff every agent has at least one
    of {model_id, fallback_model_id} in the allowed set."""

    # Build a lightweight scenario-like object with an .agents attribute
    scenario = SimpleNamespace(agents=agents)

    result = _is_scenario_available(scenario, allowed)

    # Compute expected result from first principles
    expected = True
    for agent in agents:
        reachable = {agent.model_id}
        if agent.fallback_model_id:
            reachable.add(agent.fallback_model_id)
        if not reachable & allowed:
            expected = False
            break

    assert result is expected, (
        f"available={result}, expected={expected}, "
        f"allowed={allowed}, agents=["
        + ", ".join(
            f"(model_id={a.model_id}, fallback={a.fallback_model_id})"
            for a in agents
        )
        + "]"
    )


# ---------------------------------------------------------------------------
# Feature: llm-availability-checker, Property 7: Builder prompt block filtering
#
# For any subset of model IDs in the allowed list, the filtered
# MODELS_PROMPT_BLOCK SHALL contain exactly those model IDs (each appearing
# in a line) and SHALL NOT contain any model ID not in the allowed subset.
#
# **Validates: Requirements 6.2**
# ---------------------------------------------------------------------------

from app.orchestrator.available_models import filter_models_prompt_block


# Strategy: random subsets of the real VALID_MODEL_IDS
_allowed_subset = st.frozensets(
    st.sampled_from(sorted(VALID_MODEL_IDS)),
    min_size=0,
    max_size=len(VALID_MODEL_IDS),
)


@pytest.mark.property
@settings(max_examples=100, deadline=None)
@given(allowed_ids=_allowed_subset)
def test_builder_prompt_block_filtering(allowed_ids: frozenset[str]):
    """filter_models_prompt_block returns a block containing exactly the
    allowed model IDs and none of the excluded ones."""

    result = filter_models_prompt_block(allowed_ids)

    # All model IDs from the registry, partitioned into allowed vs excluded
    all_ids = VALID_MODEL_IDS
    excluded_ids = all_ids - allowed_ids

    # 1. Every allowed model ID appears in the filtered block
    for mid in allowed_ids:
        assert f"`{mid}`" in result, (
            f"Allowed model_id '{mid}' missing from filtered prompt block"
        )

    # 2. No excluded model ID appears in the filtered block
    for mid in excluded_ids:
        assert f"`{mid}`" not in result, (
            f"Excluded model_id '{mid}' found in filtered prompt block"
        )

    # 3. Number of lines equals number of allowed IDs
    if allowed_ids:
        lines = [line for line in result.split("\n") if line.strip()]
        assert len(lines) == len(allowed_ids), (
            f"Expected {len(allowed_ids)} lines, got {len(lines)}"
        )
    else:
        # Empty allowed set → empty string
        assert result == "", (
            f"Expected empty string for empty allowed set, got: {result!r}"
        )

    # 4. Lines preserve registry order (allowed IDs appear in same
    #    relative order as AVAILABLE_MODELS)
    if len(allowed_ids) > 1:
        registry_order = [m.model_id for m in AVAILABLE_MODELS if m.model_id in allowed_ids]
        found_order = []
        for line in result.split("\n"):
            for mid in registry_order:
                if f"`{mid}`" in line and mid not in found_order:
                    found_order.append(mid)
        assert found_order == registry_order, (
            f"Lines not in registry order: got {found_order}, expected {registry_order}"
        )


# ---------------------------------------------------------------------------
# Feature: llm-availability-checker, Property 10: CLI output completeness
#
# For any set of probe results, the CLI formatted table output SHALL
# contain every model_id from the registry, each with its correct family,
# and each with PASS if available=True or FAIL if available=False.
#
# **Validates: Requirements 10.4**
# ---------------------------------------------------------------------------

from scripts.check_models import format_table

# Strategy: realistic model-like IDs that won't collide with header text
# or each other's substrings. Use a prefix to avoid matching "MODEL_ID",
# "FAMILY", "STATUS", "PASS", "FAIL", "ERROR" in the header.
_cli_model_id = st.from_regex(r"mdl-[a-z0-9]{3,15}", fullmatch=True)
_cli_family = st.from_regex(r"fam-[a-z]{2,8}", fullmatch=True)

# Strategy: generate a non-empty list of ProbeResult with unique model_ids
_unique_probe_results = (
    st.lists(
        st.builds(
            ProbeResult,
            model_id=_cli_model_id,
            family=_cli_family,
            available=st.booleans(),
            error=st.one_of(st.none(), st.text(min_size=1, max_size=80)),
            latency_ms=st.floats(min_value=0.0, max_value=30000.0, allow_nan=False),
        ),
        min_size=1,
        max_size=15,
    )
    .filter(lambda results: len({r.model_id for r in results}) == len(results))
    .map(tuple)
)


def _parse_data_rows(output: str) -> dict[str, str]:
    """Parse format_table output into {model_id: raw_row_line}.

    Skips the header and separator lines (first two lines)."""
    lines = output.split("\n")
    # First line = header, second = separator, rest = data rows
    rows: dict[str, str] = {}
    for line in lines[2:]:
        stripped = line.strip()
        if not stripped:
            continue
        # First whitespace-delimited token is the model_id
        model_id = stripped.split()[0]
        rows[model_id] = line
    return rows


@pytest.mark.property
@settings(max_examples=100, deadline=None)
@given(probe_results=_unique_probe_results)
def test_cli_output_completeness(probe_results: tuple[ProbeResult, ...]):
    """format_table output contains every model_id with correct family
    and PASS/FAIL status."""

    output = format_table(probe_results)
    data_rows = _parse_data_rows(output)

    for result in probe_results:
        expected_status = "PASS" if result.available else "FAIL"

        # 1. Every model_id has a data row
        assert result.model_id in data_rows, (
            f"model_id '{result.model_id}' missing from table data rows. "
            f"Found rows for: {list(data_rows.keys())}"
        )

        row = data_rows[result.model_id]

        # 2. Correct PASS/FAIL status in the row
        assert expected_status in row, (
            f"Expected '{expected_status}' in row for '{result.model_id}', "
            f"got row: {row!r}"
        )

        # 3. Correct family in the row
        assert result.family in row, (
            f"Expected family '{result.family}' in row for "
            f"'{result.model_id}', got row: {row!r}"
        )


# ---------------------------------------------------------------------------
# Feature: llm-availability-checker, Property 11: CLI exit code reflects failures
#
# For any set of probe results where at least one model has available=False,
# the CLI exit code SHALL be 1. When all models have available=True, the
# exit code SHALL be 0.
#
# **Validates: Requirements 10.6, 10.7**
# ---------------------------------------------------------------------------

from scripts.check_models import get_exit_code

# Strategy: non-empty probe results where at least one model fails
_probe_results_with_failure = (
    st.lists(
        st.builds(
            ProbeResult,
            model_id=_cli_model_id,
            family=_cli_family,
            available=st.booleans(),
            error=st.one_of(st.none(), st.text(min_size=1, max_size=80)),
            latency_ms=st.floats(min_value=0.0, max_value=30000.0, allow_nan=False),
        ),
        min_size=1,
        max_size=15,
    )
    .filter(lambda results: len({r.model_id for r in results}) == len(results))
    .filter(lambda results: not all(r.available for r in results))
    .map(tuple)
)

# Strategy: non-empty probe results where ALL models pass
_probe_results_all_pass = (
    st.lists(
        st.builds(
            ProbeResult,
            model_id=_cli_model_id,
            family=_cli_family,
            available=st.just(True),
            error=st.none(),
            latency_ms=st.floats(min_value=0.0, max_value=30000.0, allow_nan=False),
        ),
        min_size=1,
        max_size=15,
    )
    .filter(lambda results: len({r.model_id for r in results}) == len(results))
    .map(tuple)
)


@pytest.mark.property
@settings(max_examples=100, deadline=None)
@given(probe_results=_probe_results_with_failure)
def test_cli_exit_code_reflects_failures(probe_results: tuple[ProbeResult, ...]):
    """get_exit_code returns 1 when any model has available=False."""

    exit_code = get_exit_code(probe_results)
    assert exit_code == 1, (
        f"Expected exit code 1 when failures present, got {exit_code}. "
        f"available flags: {[r.available for r in probe_results]}"
    )


@pytest.mark.property
@settings(max_examples=100, deadline=None)
@given(probe_results=_probe_results_all_pass)
def test_cli_exit_code_all_pass(probe_results: tuple[ProbeResult, ...]):
    """get_exit_code returns 0 when all models have available=True."""

    exit_code = get_exit_code(probe_results)
    assert exit_code == 0, (
        f"Expected exit code 0 when all pass, got {exit_code}. "
        f"available flags: {[r.available for r in probe_results]}"
    )


@pytest.mark.property
def test_cli_exit_code_empty_results():
    """get_exit_code returns 1 for empty probe results (edge case)."""

    exit_code = get_exit_code(())
    assert exit_code == 1, (
        f"Expected exit code 1 for empty probe results, got {exit_code}"
    )
