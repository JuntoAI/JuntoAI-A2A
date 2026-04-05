# Implementation Plan: Developer Agent SDK & Documentation

## Overview

Build `juntoai-agent-sdk` as a standalone Python package in `sdk/` at the monorepo root. Tasks are ordered by dependency: package scaffold → types → base agent → server → test harness → CLI → template agents → OpenAPI spec → docs → CI sync script. Each task builds on the previous so there's no orphaned code.

## Tasks

- [ ] 1. Scaffold SDK package structure
  - [ ] 1.1 Create `sdk/` directory with `pyproject.toml`, `README.md`, `LICENSE`, `py.typed` marker
    - Create `sdk/pyproject.toml` with hatchling build system, package metadata, dependencies (`pydantic>=2.0`, `fastapi>=0.100`, `uvicorn>=0.20`, `httpx>=0.24`), optional dev deps (`pytest`, `pytest-asyncio`, `hypothesis`, `mypy`, `httpx`), and `juntoai-test` script entry point
    - Create `sdk/src/juntoai_agent_sdk/__init__.py` that re-exports `BaseAgent` and `AgentServer`
    - Create `sdk/src/juntoai_agent_sdk/py.typed` (empty PEP 561 marker)
    - Create `sdk/tests/__init__.py`, `sdk/tests/conftest.py`, `sdk/tests/property/__init__.py`
    - Create `sdk/README.md` with condensed quickstart (install + 10-line example + run)
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 8.4_

- [ ] 2. Implement type definitions
  - [ ] 2.1 Create `sdk/src/juntoai_agent_sdk/types.py` with all Pydantic V2 models
    - Implement `Budget`, `AgentConfig`, `HistoryEntry`, `NegotiationParams`, `TurnPayload`
    - Implement `NegotiatorResponse`, `RegulatorResponse`, `ObserverResponse` matching fields exactly from `backend/app/orchestrator/outputs.py` (`NegotiatorOutput`, `RegulatorOutput`, `ObserverOutput`)
    - Define `AgentResponse` union type
    - Export all types via `__all__`
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

  - [ ]* 2.2 Write property test for SDK type serialization round-trip
    - **Property 1: SDK Type Serialization Round-Trip**
    - **Validates: Requirements 2.1, 2.2, 2.3**
    - In `sdk/tests/property/test_sdk_properties.py`, use Hypothesis `st.builds()` to generate random instances of each Pydantic model, serialize via `model_dump_json()`, deserialize via `model_validate_json()`, assert equality

  - [ ]* 2.3 Write property test for SDK-backend response model field sync
    - **Property 2: SDK-Backend Response Model Field Sync**
    - **Validates: Requirements 2.5**
    - In `sdk/tests/property/test_sdk_properties.py`, parametrize over model pairs (`NegotiatorResponse`/`NegotiatorOutput`, `RegulatorResponse`/`RegulatorOutput`, `ObserverResponse`/`ObserverOutput`), compare `model_fields` names, annotation types, and defaults

  - [ ]* 2.4 Write unit tests for type definitions
    - In `sdk/tests/test_types.py`, test all public types importable from `juntoai_agent_sdk.types`
    - Test TurnPayload validation with valid and invalid data
    - Test response model field defaults
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

- [ ] 3. Implement BaseAgent abstract class
  - [ ] 3.1 Create `sdk/src/juntoai_agent_sdk/base.py` with `BaseAgent` ABC
    - Implement `__init__(self, name: str, supported_types: list[str])`
    - Implement abstract `async def on_turn(self, payload: TurnPayload) -> AgentResponse`
    - Implement `run(host, port)` method that delegates to `AgentServer`
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

  - [ ]* 3.2 Write unit tests for BaseAgent
    - In `sdk/tests/test_base.py`, test that subclassing without `on_turn` raises `TypeError`
    - Test that constructor stores `name` and `supported_types`
    - _Requirements: 3.1, 3.2, 3.3_

- [ ] 4. Implement AgentServer
  - [ ] 4.1 Create `sdk/src/juntoai_agent_sdk/server.py` with `AgentServer` class
    - FastAPI app with CORS middleware (allow all origins)
    - Request logging middleware (timestamp, method, path, status code, response time)
    - `GET /` health check returning `{"status": "ok", "name": ..., "supported_types": ...}`
    - `GET /health` alias returning `{"status": "ok"}`
    - `POST /` turn endpoint: deserialize `TurnPayload`, call `on_turn`, return response; on exception return HTTP 500 with `{"error": "<message>"}`
    - Environment variable config: `AGENT_HOST`, `AGENT_PORT`, `AGENT_LOG_LEVEL`
    - _Requirements: 3.4, 3.5, 3.6, 4.1, 4.2, 4.3, 4.4, 4.5_

  - [ ]* 4.2 Write property test for health check identity
    - **Property 3: Health Check Returns Agent Identity**
    - **Validates: Requirements 3.5**
    - In `sdk/tests/property/test_sdk_properties.py`, generate random agent names via `st.text(min_size=1)` and type lists via `st.lists(st.sampled_from(["negotiator", "regulator", "observer"]), min_size=1)`, create `TestClient`, GET `/`, assert fields match

  - [ ]* 4.3 Write property test for server turn endpoint round-trip
    - **Property 4: Server Turn Endpoint Round-Trip**
    - **Validates: Requirements 3.6**
    - In `sdk/tests/property/test_sdk_properties.py`, generate random valid `TurnPayload`s, POST to TestClient wrapping a deterministic stub agent, compare HTTP response body to direct `on_turn(payload).model_dump()`

  - [ ]* 4.4 Write unit tests for AgentServer
    - In `sdk/tests/test_server.py`, test CORS headers on OPTIONS request
    - Test `GET /health` returns `{"status": "ok"}`
    - Test `POST /` with invalid JSON returns 422
    - Test `POST /` when `on_turn` raises `ValueError` returns HTTP 500 with error message
    - Test environment variable overrides for host/port/log_level
    - _Requirements: 3.5, 3.6, 4.1, 4.2, 4.3, 4.4, 4.5_

- [ ] 5. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 6. Implement TestHarness
  - [ ] 6.1 Create `sdk/src/juntoai_agent_sdk/testing.py` with `TestHarness`, `TurnResult`, `HarnessReport`
    - `TestHarness.__init__` accepts `agent`, `agent_type`, `num_turns`, `initial_offer`, `history_seed`
    - `async def run()` simulates multi-turn negotiation: builds synthetic `TurnPayload` per turn, calls `on_turn`, validates response type, tracks `proposed_price` for movement detection, appends to history
    - `TurnResult` dataclass with `turn_number`, `response`, `validation_error`
    - `HarnessReport` dataclass with `turns_executed`, `results`, `validation_failures`, `price_movement`
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

  - [ ]* 6.2 Write property test for harness turn count
    - **Property 5: TestHarness Executes Requested Turn Count**
    - **Validates: Requirements 5.2**
    - In `sdk/tests/property/test_sdk_properties.py`, generate random turn counts via `st.integers(1, 50)`, run harness with a stub agent, assert `turns_executed == N` and `len(results) == N`

  - [ ]* 6.3 Write property test for harness config propagation
    - **Property 6: TestHarness Propagates Configuration to Payloads**
    - **Validates: Requirements 5.4**
    - In `sdk/tests/property/test_sdk_properties.py`, generate random configs (agent_type, initial_offer, num_turns), instrument stub agent to capture payloads, verify `agent_type`, `turn_number` increments, `max_turns`, and first `current_offer`

  - [ ]* 6.4 Write property test for price movement detection
    - **Property 7: Price Movement Detection**
    - **Validates: Requirements 5.5**
    - In `sdk/tests/property/test_sdk_properties.py`, generate random price sequences via `st.lists(st.floats(min_value=0, max_value=1e9, allow_nan=False), min_size=2)`, mock agent to return them in order, verify `price_movement` flag is `True` iff sequence has ≥2 distinct values

  - [ ]* 6.5 Write unit tests for TestHarness
    - In `sdk/tests/test_testing.py`, test harness with a simple stub negotiator agent
    - Test validation error recorded when `on_turn` raises exception
    - Test validation error when agent returns wrong response type for agent_type
    - Test `price_movement=False` when agent returns same price every turn
    - _Requirements: 5.2, 5.3, 5.4, 5.5_

- [ ] 7. Implement CLI entry point
  - [ ] 7.1 Create `sdk/src/juntoai_agent_sdk/cli.py` with `main()` function
    - argparse-based CLI with `--agent module:ClassName`, `--type`, `--turns`, `--initial-offer`
    - Dynamic module import and class instantiation
    - Run `TestHarness` and print summary report
    - _Requirements: 5.6_

  - [ ]* 7.2 Write unit tests for CLI
    - In `sdk/tests/test_cli.py`, test argument parsing for `--agent`, `--type`, `--turns`, `--initial-offer`
    - Test `module:ClassName` format resolves to correct class
    - _Requirements: 5.6_

- [ ] 8. Implement template agent examples
  - [ ] 8.1 Create `sdk/examples/simple_negotiator.py`
    - Complete runnable file (<100 lines) subclassing `BaseAgent`
    - Negotiator that makes incremental concessions toward target price
    - Inline comments explaining key decisions and customization points
    - _Requirements: 6.1, 6.2, 6.3_

  - [ ] 8.2 Create `sdk/examples/simple_regulator.py`
    - Regulator that issues warnings when offers exceed a threshold
    - _Requirements: 6.1, 6.2, 6.3_

  - [ ] 8.3 Create `sdk/examples/simple_observer.py`
    - Observer that summarizes negotiation state
    - _Requirements: 6.1, 6.2, 6.3_

  - [ ] 8.4 Create `sdk/examples/llm_negotiator.py`
    - Demonstrates wrapping an LLM call (OpenAI or Anthropic) inside `BaseAgent`
    - Shows how to use the SDK with any LLM provider
    - _Requirements: 6.4_

  - [ ] 8.5 Create `sdk/examples/Dockerfile`
    - Dockerfile template for containerized agent deployment
    - _Requirements: 4.6_

  - [ ]* 8.6 Write property test for template agent validity
    - **Property 8: Template Agents Return Valid Responses**
    - **Validates: Requirements 6.2**
    - In `sdk/tests/property/test_sdk_properties.py`, generate random valid `TurnPayload`s with matching `agent_type`, call each template agent's `on_turn`, assert response is valid instance of the corresponding Pydantic response model

  - [ ]* 8.7 Write integration tests for template agents with TestHarness
    - In `sdk/tests/test_templates.py`, run each template agent through `TestHarness` with default settings
    - Assert zero validation failures for all three simple templates
    - _Requirements: 6.5_

- [ ] 9. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 10. Create OpenAPI specification
  - [ ] 10.1 Create `sdk/openapi.yaml` describing the Agent Gateway HTTP contract
    - OpenAPI 3.1 format
    - Define `POST /` endpoint with `TurnPayload` request body and `oneOf` response schemas discriminated by `agent_type`
    - Define `GET /` health check endpoint
    - Include example request/response pairs for each agent type (negotiator, regulator, observer)
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

  - [ ]* 10.2 Write unit test for OpenAPI spec validity
    - In `sdk/tests/test_openapi.py`, parse `openapi.yaml` and validate it is valid OpenAPI 3.1
    - _Requirements: 7.5_

- [ ] 11. Create documentation
  - [ ] 11.1 Create `sdk/docs/quickstart.md`
    - Step-by-step guide: install SDK → create negotiator → test with TestHarness → deploy (Docker) → register with JuntoAI (Spec 210) → run negotiation
    - Copy-pasteable code blocks for each step
    - "What happens under the hood" section with sequence diagram of TurnPayload → on_turn → TurnResponse flow
    - _Requirements: 8.1, 8.2, 8.3_

  - [ ] 11.2 Create `sdk/docs/architecture.md`
    - Explain JuntoAI orchestrator (LangGraph), RemoteAgentNode (Spec 200), TurnPayload/TurnResponse contract, error handling/fallback, mixed local/remote negotiations
    - Sequence diagram: orchestrator → RemoteAgentNode → HTTP POST → remote agent → HTTP response → state update → next turn
    - "Designing Good Agents" section: response time targets (<10s), stateless vs stateful, handling history, price movement strategies
    - _Requirements: 9.1, 9.2, 9.3_

- [ ] 12. Create CI type sync script and mypy config
  - [ ] 12.1 Create `sdk/scripts/check_type_sync.py`
    - Import SDK response models and backend output models
    - Compare `model_fields` (names, annotation types, defaults) for each pair
    - Exit non-zero with clear error message if any field diverges
    - _Requirements: 2.5_

  - [ ] 12.2 Add mypy configuration for strict mode
    - Add `[tool.mypy]` section to `sdk/pyproject.toml` with `strict = true`
    - Ensure `sdk/src/juntoai_agent_sdk/` passes `mypy --strict`
    - _Requirements: 1.5_

- [ ] 13. Final checkpoint — Ensure all tests pass and CI checks are green
  - Run `pytest` in `sdk/` with coverage threshold 70%
  - Run `mypy --strict sdk/src/`
  - Run `python sdk/scripts/check_type_sync.py`
  - Validate `sdk/openapi.yaml`
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate the 8 universal correctness properties from the design
- Unit tests validate specific examples and edge cases
- The SDK is a standalone package — no backend code changes needed except the CI type sync script reads backend models
