# Implementation Plan: LLM Availability Checker

## Overview

Implement a startup-time probe layer that tests every registered LLM model before the app accepts traffic. The result is a frozen "allowed models" list stored in `app.state` that gates all downstream consumers: `/models` endpoint, scenario validation, builder prompt injection, health reporting, and admin visibility. Includes a standalone CLI script for developer use.

## Tasks

- [x] 1. Extend model registry and model mapping
  - [x] 1.1 Add new model entries to `AVAILABLE_MODELS` in `backend/app/orchestrator/available_models.py`
    - Add `ModelEntry("gemini-3.1-pro-preview", "gemini", "Gemini 3.1 Pro (Preview)")`
    - Add `ModelEntry("gemini-3.1-flash-lite-preview", "gemini", "Gemini 3.1 Flash Lite (Preview)")`
    - Keep sorted by family then capability tier
    - `VALID_MODEL_IDS` and `MODELS_PROMPT_BLOCK` derive automatically
    - _Requirements: 1.1, 1.2_

  - [x] 1.2 Add `DEFAULT_MODEL_MAP` entries in `backend/app/orchestrator/model_mapping.py`
    - Add mappings for `gemini-3.1-pro-preview` and `gemini-3.1-flash-lite-preview` across all three providers (openai, anthropic, ollama)
    - _Requirements: 1.2_

  - [x] 1.3 Write property test for registry derivation consistency
    - **Property 1: Registry derivation consistency**
    - Verify every `AVAILABLE_MODELS` entry's `model_id` appears in `VALID_MODEL_IDS` and `MODELS_PROMPT_BLOCK`, and `VALID_MODEL_IDS` contains no IDs absent from `AVAILABLE_MODELS`
    - **Validates: Requirements 1.2**

- [x] 2. Implement core availability checker
  - [x] 2.1 Create `ProbeResult` and `AllowedModels` dataclasses in `backend/app/orchestrator/availability_checker.py`
    - `ProbeResult`: frozen dataclass with `model_id`, `family`, `available`, `error`, `latency_ms`
    - `AllowedModels`: frozen dataclass with `entries` (tuple), `model_ids` (frozenset), `probe_results` (tuple), `probed_at` (str)
    - _Requirements: 3.1, 3.3_

  - [x] 2.2 Implement `AvailabilityChecker` class in `backend/app/orchestrator/availability_checker.py`
    - `probe_model(model_id, family, timeout)` — wraps `get_model()` + `model.ainvoke()` in `asyncio.wait_for(timeout)`, catches all exceptions, returns `ProbeResult`
    - `probe_all(models, timeout)` — runs all probes concurrently via `asyncio.gather`, builds `AllowedModels` from passing probes
    - Log per-model results at WARNING (failures) and INFO (summary)
    - Log ERROR if zero models pass
    - _Requirements: 2.1, 2.4, 2.5, 2.6, 2.7, 3.1, 8.1, 8.2_

  - [x] 2.3 Write property test for probe exception safety
    - **Property 2: Probe exception safety**
    - Mock model to raise various exception types, verify `ProbeResult` has `available=False` and non-empty `error`, exception never propagates
    - **Validates: Requirements 2.5, 8.2**

  - [x] 2.4 Write property test for allowed list correctness
    - **Property 3: Allowed list contains exactly passing models**
    - Generate random pass/fail subsets, verify `AllowedModels.model_ids` equals exactly the passing set and `entries` preserves registry order
    - **Validates: Requirements 3.1**

  - [x] 2.5 Write property test for AllowedModels immutability
    - **Property 4: AllowedModels immutability**
    - Construct `AllowedModels` with random data, attempt attribute assignment, verify `FrozenInstanceError` is raised
    - **Validates: Requirements 3.3**

  - [x] 2.6 Write property test for probe idempotence
    - **Property 9: Probe idempotence**
    - Generate random mock model configs, run `probe_all` twice, verify identical `model_ids`, `entries`, and `available` flags
    - **Validates: Requirements 8.3**

- [x] 3. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Integrate checker into FastAPI lifespan and update endpoints
  - [x] 4.1 Integrate `AvailabilityChecker` into lifespan in `backend/app/main.py`
    - Instantiate `AvailabilityChecker`, call `probe_all(AVAILABLE_MODELS)`, store result in `app.state.allowed_models`
    - Run before existing startup logic, before `yield`
    - _Requirements: 2.1, 3.2_

  - [x] 4.2 Update `/models` endpoint in `backend/app/routers/models.py`
    - Read from `request.app.state.allowed_models.entries` instead of `AVAILABLE_MODELS`
    - Fall back to empty list if `allowed_models` not yet set
    - _Requirements: 4.1, 4.2_

  - [x] 4.3 Write property test for models endpoint filtering
    - **Property 5: Models endpoint returns exactly allowed models**
    - Mock `app.state.allowed_models`, verify `/models` returns exactly `AllowedModels.model_ids`
    - **Validates: Requirements 4.1**

- [x] 5. Enhance health endpoint with model availability info
  - [x] 5.1 Extend `HealthResponse` in `backend/app/models/health.py`
    - Add `models: dict | None` field (`{total_registered: int, total_available: int}`)
    - Add `unavailable_models: list[str] | None` field
    - Make status `"degraded"` when `total_available == 0`
    - _Requirements: 7.1, 7.2, 7.3_

  - [x] 5.2 Update health endpoint in `backend/app/routers/health.py`
    - Read `app.state.allowed_models` to populate new fields
    - If `allowed_models` not set, omit model info (return `None` for optional fields)
    - Set status to `"degraded"` when total_available is 0
    - _Requirements: 7.1, 7.2, 7.3_

  - [x] 5.3 Write property test for health and admin count consistency
    - **Property 8: Health and admin count consistency**
    - Generate random probe results, verify `total_registered`, `total_available`, `total_unavailable`, `unavailable_models`, and `status` logic
    - **Validates: Requirements 7.1, 7.2, 7.3, 9.3**

- [x] 6. Scenario registry and builder integration
  - [x] 6.1 Enhance `ScenarioRegistry` in `backend/app/scenarios/registry.py`
    - Accept `allowed_model_ids: frozenset[str] | None` in constructor or via setter
    - `list_scenarios()` adds `available: bool` to each scenario dict
    - A scenario is `available` if every agent has at least one of `{model_id, fallback_model_id}` in the allowed set
    - Log WARNING for scenarios with unavailable models during `_discover()`
    - _Requirements: 5.1, 5.2, 5.3_

  - [x] 6.2 Write property test for scenario availability flag
    - **Property 6: Scenario availability flag correctness**
    - Generate random agent configs with `model_id`/`fallback_model_id`, random allowed sets, verify `available` flag logic
    - **Validates: Requirements 5.3**

  - [x] 6.3 Filter `MODELS_PROMPT_BLOCK` in `backend/app/routers/builder.py`
    - Read `request.app.state.allowed_models` to filter the prompt block to only allowed model IDs before injection into LLM prompts
    - _Requirements: 6.1, 6.2_

  - [x] 6.4 Write property test for builder prompt block filtering
    - **Property 7: Builder prompt block filtering**
    - Generate random allowed model ID subsets, verify filtered `MODELS_PROMPT_BLOCK` contains exactly those IDs
    - **Validates: Requirements 6.2**

- [x] 7. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Admin model availability endpoint
  - [x] 8.1 Add `GET /admin/models` endpoint in `backend/app/routers/admin.py`
    - Gated behind `verify_admin_session` dependency
    - Return list of all registry entries with probe status, error, latency_ms
    - Include summary counts: `total_registered`, `total_available`, `total_unavailable`, `probed_at`
    - Return 503 if `app.state.allowed_models` not yet set
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6_

  - [x] 8.2 Write unit tests for admin models endpoint
    - Test 401 without auth cookie, 200 with valid cookie
    - Test 503 when `allowed_models` not set
    - Test correct response shape with mock probe results
    - _Requirements: 9.4, 9.5_

- [x] 9. CLI model availability script
  - [x] 9.1 Create `backend/scripts/check_models.py`
    - Load settings from `.env` via `pydantic-settings` (same `Settings` class)
    - Instantiate `AvailabilityChecker` and call `probe_all()`
    - Print formatted table to stdout (model_id, family, PASS/FAIL, error)
    - Print summary line: `X/Y models available`
    - Exit code 0 (all pass) or 1 (any fail)
    - Runnable as `python -m scripts.check_models` or `python scripts/check_models.py`
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7, 10.8, 10.9_

  - [x] 9.2 Write property test for CLI output completeness
    - **Property 10: CLI output completeness**
    - Generate random probe results, verify table output contains every `model_id` with correct family and PASS/FAIL
    - **Validates: Requirements 10.4**

  - [x] 9.3 Write property test for CLI exit code
    - **Property 11: CLI exit code reflects failures**
    - Generate random probe results, verify exit code 1 when any fail, 0 when all pass
    - **Validates: Requirements 10.6, 10.7**

- [x] 10. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate the 11 correctness properties from the design document using Hypothesis
- Unit tests validate specific examples and edge cases
- All property tests go in `backend/tests/property/test_availability_checker_properties.py`
- Unit/integration tests go in `backend/tests/unit/orchestrator/test_availability_checker.py` and `backend/tests/integration/test_availability_endpoints.py`
