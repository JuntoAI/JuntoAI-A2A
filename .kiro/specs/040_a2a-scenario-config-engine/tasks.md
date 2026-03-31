# Implementation Plan: Scenario Config Engine

## Overview

Build the config-driven Scenario Engine under `backend/app/scenarios/`. The engine loads Arena Scenario JSON files, validates them against Pydantic V2 models, indexes them in an in-memory registry, exposes them via FastAPI endpoints, and provides a Toggle Injector for assembling hidden context dictionaries. Implementation proceeds bottom-up: exceptions → models → loader → registry → toggle injector → pretty printer → scenario data files → router → wiring.

## Tasks

- [ ] 1. Create module skeleton and exception classes
  - [ ] 1.1 Create `backend/app/scenarios/` package with `__init__.py`
    - Create directory structure: `backend/app/scenarios/` and `backend/app/scenarios/data/`
    - `__init__.py` should be empty initially (re-exports added in final wiring step)
    - _Requirements: 4.1, 4.7_

  - [ ] 1.2 Implement `backend/app/scenarios/exceptions.py`
    - Define `ScenarioValidationError(file_path, errors)` with both attributes stored
    - Define `ScenarioFileNotFoundError(file_path)` with `file_path` attribute
    - Define `ScenarioParseError(file_path, detail)` with both attributes stored
    - Define `ScenarioNotFoundError(scenario_id)` with `scenario_id` attribute
    - Define `InvalidToggleError(toggle_id, scenario_id)` with both attributes stored
    - All exceptions inherit from `Exception` with descriptive `__str__` messages
    - _Requirements: 2.2, 2.3, 2.4, 4.6, 5.6_

- [ ] 2. Implement Pydantic V2 models
  - [ ] 2.1 Implement `backend/app/scenarios/models.py`
    - Define `Budget` model with `min`, `max`, `target` (float, ge=0) and `model_validator` enforcing `min <= max`
    - Define `AgentDefinition` with `role`, `name`, `type` (Literal["negotiator", "regulator"]), `persona_prompt`, `goals` (list[str], min_length=1), `budget` (Budget), `tone`, `output_fields` (list[str], min_length=1), `model_id`, `fallback_model_id` (optional)
    - Define `ToggleDefinition` with `id`, `label`, `target_agent_role`, `hidden_context_payload` (dict, min_length=1)
    - Define `NegotiationParams` with `max_turns` (int, gt=0), `agreement_threshold` (float, gt=0)
    - Define `OutcomeReceipt` with `equivalent_human_time`, `process_label`
    - Define `ArenaScenario` with `id`, `name`, `description`, `agents` (list[AgentDefinition], min_length=2), `toggles` (list[ToggleDefinition], min_length=1), `negotiation_params`, `outcome_receipt`
    - Add `model_validator` on `ArenaScenario` to enforce unique agent roles and validate toggle `target_agent_role` references
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 2.5, 2.6_

  - [ ]* 2.2 Write unit tests for Pydantic models (`backend/tests/unit/test_scenario_models.py`)
    - Test valid `Budget` instantiation and `min <= max` constraint rejection
    - Test valid `AgentDefinition` with all required fields, missing field rejection
    - Test valid `ToggleDefinition`, empty `hidden_context_payload` rejection
    - Test valid `ArenaScenario` with cross-reference validation (unique roles, valid toggle targets)
    - Test duplicate agent roles raise `ValidationError`
    - Test invalid toggle `target_agent_role` raises `ValidationError`
    - _Requirements: 1.1–1.9, 2.5, 2.6_

- [ ] 3. Implement scenario loader
  - [ ] 3.1 Implement `backend/app/scenarios/loader.py`
    - Implement `load_scenario_from_file(file_path)` that reads JSON, parses, validates via Pydantic, raises typed exceptions
    - Implement `load_scenario_from_dict(data, source_path)` that validates a dict against `ArenaScenario`
    - `ScenarioFileNotFoundError` for missing/unreadable files
    - `ScenarioParseError` for invalid JSON content
    - `ScenarioValidationError` for schema violations (wraps Pydantic `ValidationError.errors()`)
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

  - [ ]* 3.2 Write unit tests for loader (`backend/tests/unit/test_scenario_loader.py`)
    - Test loading a valid JSON file returns `ArenaScenario`
    - Test non-existent path raises `ScenarioFileNotFoundError`
    - Test invalid JSON content raises `ScenarioParseError`
    - Test schema-invalid JSON raises `ScenarioValidationError` with error details
    - Use `tmp_path` fixture for temp file creation
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

  - [ ]* 3.3 Write property test for non-JSON parse errors (`backend/tests/property/test_scenario_properties.py`)
    - **Property 8: Non-JSON content raises ScenarioParseError**
    - Generate random non-JSON strings via hypothesis, write to temp files, assert `load_scenario_from_file()` raises `ScenarioParseError`
    - `@settings(max_examples=100)`
    - **Validates: Requirements 2.4**

- [ ] 4. Implement scenario registry
  - [ ] 4.1 Implement `backend/app/scenarios/registry.py`
    - `ScenarioRegistry.__init__(scenarios_dir)` with `SCENARIOS_DIR` env var fallback
    - `_discover()` scans for `*.scenario.json`, loads each via `load_scenario_from_file`, logs and skips failures
    - `list_scenarios()` returns list of `{"id", "name", "description"}` dicts
    - `get_scenario(scenario_id)` returns `ArenaScenario` or raises `ScenarioNotFoundError`
    - `__len__()` for convenience
    - Use `sorted()` on glob for deterministic ordering
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 10.1, 10.4_

  - [ ]* 4.2 Write unit tests for registry (`backend/tests/unit/test_scenario_registry.py`)
    - Test discovery from temp directory with valid and invalid files
    - Test `list_scenarios()` returns correct entries
    - Test `get_scenario()` returns correct object
    - Test `get_scenario()` with unknown id raises `ScenarioNotFoundError`
    - Test `SCENARIOS_DIR` env var is respected
    - Test invalid files are skipped with warning (not crash)
    - _Requirements: 4.1–4.7, 10.1, 10.4_

  - [ ]* 4.3 Write property test for registry get/list consistency (`backend/tests/property/test_scenario_properties.py`)
    - **Property 7: Registry get/list consistency**
    - Generate random sets of valid `ArenaScenario` objects, register in `ScenarioRegistry`
    - Assert `list_scenarios()` returns all ids, `get_scenario(id)` returns correct object, unknown id raises `ScenarioNotFoundError`
    - `@settings(max_examples=100)`
    - **Validates: Requirements 4.4, 4.5, 4.6**

- [ ] 5. Checkpoint — Core engine components
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 6. Implement toggle injector
  - [ ] 6.1 Implement `backend/app/scenarios/toggle_injector.py`
    - `build_hidden_context(scenario, active_toggle_ids)` returns `dict[str, Any]`
    - Empty `active_toggle_ids` returns `{}`
    - Shallow-merge payloads when multiple toggles target the same role (last wins on key conflict)
    - Raise `InvalidToggleError` for unrecognized toggle ids
    - _Requirements: 5.1, 5.2, 5.3, 5.5, 5.6, 10.3_

  - [ ]* 6.2 Write unit tests for toggle injector (`backend/tests/unit/test_toggle_injector.py`)
    - Test single toggle injection
    - Test multiple toggles targeting same role merge correctly
    - Test no toggles returns empty dict
    - Test invalid toggle id raises `InvalidToggleError`
    - _Requirements: 5.1, 5.2, 5.3, 5.5, 5.6_

  - [ ]* 6.3 Write property test for toggle injection correctness (`backend/tests/property/test_scenario_properties.py`)
    - **Property 5: Toggle injection produces correct hidden context**
    - Generate random valid `ArenaScenario` instances and random subsets of toggle ids
    - Assert output keys match activated toggle target roles, values contain all merged payloads, no non-activated toggle keys appear
    - `@settings(max_examples=100)`
    - **Validates: Requirements 5.1, 5.2, 5.3, 10.3**

  - [ ]* 6.4 Write property test for invalid toggle error (`backend/tests/property/test_scenario_properties.py`)
    - **Property 6: Invalid toggle identifiers raise InvalidToggleError**
    - Generate random valid `ArenaScenario` instances and random strings not matching any toggle id
    - Assert `build_hidden_context()` raises `InvalidToggleError`
    - `@settings(max_examples=100)`
    - **Validates: Requirements 5.6**

- [ ] 7. Implement pretty printer and round-trip validation
  - [ ] 7.1 Implement `backend/app/scenarios/pretty_printer.py`
    - `pretty_print(scenario)` returns `scenario.model_dump_json(indent=2)`
    - _Requirements: 3.1, 3.2_

  - [ ]* 7.2 Write unit tests for pretty printer (`backend/tests/unit/test_pretty_printer.py`)
    - Test output is valid JSON
    - Test output has 2-space indentation
    - Test all fields preserved in output
    - _Requirements: 3.1, 3.2, 3.3_

  - [ ]* 7.3 Write property test for round-trip serialization (`backend/tests/property/test_scenario_properties.py`)
    - **Property 1: ArenaScenario round-trip serialization**
    - Generate random valid `ArenaScenario` instances via hypothesis strategies
    - Assert `load_scenario_from_dict(json.loads(pretty_print(scenario)))` equals original
    - `@settings(max_examples=100)`
    - **Validates: Requirements 3.1, 3.2, 3.3**

  - [ ]* 7.4 Write property test for missing required fields rejection (`backend/tests/property/test_scenario_properties.py`)
    - **Property 2: Schema rejects scenarios with missing required fields**
    - Generate valid scenario dicts, remove one required field at a time
    - Assert `ArenaScenario.model_validate()` raises `ValidationError`
    - `@settings(max_examples=100)`
    - **Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 2.2**

  - [ ]* 7.5 Write property test for cross-reference validation (`backend/tests/property/test_scenario_properties.py`)
    - **Property 3: Cross-reference validation rejects invalid toggle targets**
    - Generate valid scenario dicts, replace `target_agent_role` with invalid string
    - Assert `ArenaScenario.model_validate()` raises `ValidationError`
    - `@settings(max_examples=100)`
    - **Validates: Requirements 1.9, 2.5**

  - [ ]* 7.6 Write property test for unique agent roles (`backend/tests/property/test_scenario_properties.py`)
    - **Property 4: Unique agent roles constraint**
    - Generate scenario dicts with duplicate agent roles
    - Assert `ArenaScenario.model_validate()` raises `ValidationError`
    - `@settings(max_examples=100)`
    - **Validates: Requirements 2.6**

- [ ] 8. Checkpoint — All engine logic and property tests
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 9. Create MVP scenario JSON files
  - [ ] 9.1 Create `backend/app/scenarios/data/talent-war.scenario.json`
    - Agent 1: role `"Recruiter"`, name `"Sarah"`, type `"negotiator"`, max budget `130000`, target `110000`, goal to secure candidate in-office 5 days/week
    - Agent 2: role `"Candidate"`, name `"Alex"`, type `"negotiator"`, min budget `120000`, goal demanding min 3 days remote
    - Agent 3: role `"Regulator"`, name `"HR Compliance Bot"`, type `"regulator"`, flags unauthorized stock options or biased language
    - Toggle 1: id `"competing_offer"`, label `"Give Alex a hidden €125k competing offer from Google"`, targets `"Candidate"`
    - Toggle 2: id `"deadline_pressure"`, label `"Make Sarah desperate - deadline in 24 hours"`, targets `"Recruiter"`
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

  - [ ] 9.2 Create `backend/app/scenarios/data/ma-buyout.scenario.json`
    - Agent 1: role `"Buyer"`, name `"Titan Corp CEO"`, type `"negotiator"`, max budget `50000000`, target `35000000`
    - Agent 2: role `"Seller"`, name `"Innovate Tech Founder"`, type `"negotiator"`, min budget `40000000`, goal demanding 2-year team retention
    - Agent 3: role `"Regulator"`, name `"EU Regulator Bot"`, type `"regulator"`, blocks deals involving total data monopoly
    - Toggle 1: id `"hidden_debt"`, targets `"Buyer"` with hidden debt intelligence
    - Toggle 2: id `"max_strictness"`, targets `"Regulator"` with maximum strictness directive
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6_

  - [ ] 9.3 Create `backend/app/scenarios/data/b2b-sales.scenario.json`
    - Agent 1: role `"Seller"`, name `"SaaS Account Executive"`, type `"negotiator"`, list price `100000`, target `80000`
    - Agent 2: role `"Buyer"`, name `"Target CTO"`, type `"negotiator"`, budget capped at `70000`
    - Agent 3: role `"Regulator"`, name `"Procurement Bot"`, type `"regulator"`, ensures SLA guarantees and data compliance
    - Toggle 1: id `"q4_pressure"`, targets `"Seller"` with Q4 quota pressure
    - Toggle 2: id `"budget_freeze"`, targets `"Buyer"` with budget freeze constraint
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6_

  - [ ]* 9.4 Write validation tests for MVP scenario files (`backend/tests/unit/test_scenario_files.py`)
    - Test each of the 3 scenario files loads successfully via `load_scenario_from_file`
    - Test each contains expected agent roles, names, budget values
    - Test each contains expected toggle ids and target roles
    - _Requirements: 6.1–6.6, 7.1–7.6, 8.1–8.6_

- [ ] 10. Implement FastAPI router and wiring
  - [ ] 10.1 Implement `backend/app/scenarios/router.py`
    - Create `APIRouter(prefix="/scenarios", tags=["scenarios"])`
    - `GET ""` → `list_scenarios()` returns list of `{"id", "name", "description"}`
    - `GET "/{scenario_id}"` → returns full scenario via `model_dump()`, 404 on `ScenarioNotFoundError`
    - Implement `get_scenario_registry()` dependency with module-level singleton pattern
    - _Requirements: 9.1, 9.2, 9.3_

  - [ ] 10.2 Update `backend/app/scenarios/__init__.py` with re-exports
    - Re-export `ScenarioRegistry`, `build_hidden_context`, `ArenaScenario`, `load_scenario_from_file`, `load_scenario_from_dict`
    - Re-export all exception classes
    - _Requirements: 4.1, 10.1, 10.2_

  - [ ]* 10.3 Write integration tests for router (`backend/tests/integration/test_scenario_router.py`)
    - Use FastAPI `TestClient` with a test registry loaded from temp scenario files
    - Test `GET /scenarios` returns list with correct structure
    - Test `GET /scenarios/{id}` returns full scenario JSON
    - Test `GET /scenarios/{unknown}` returns 404 with error body
    - _Requirements: 9.1, 9.2, 9.3_

- [ ] 11. Create shared test fixtures and hypothesis strategies
  - [ ] 11.1 Create `backend/tests/conftest.py` with shared fixtures
    - Fixture for a valid scenario dict (reusable across unit/property tests)
    - Fixture for a temp directory with valid scenario files
    - Hypothesis strategies for generating random valid `Budget`, `AgentDefinition`, `ToggleDefinition`, `ArenaScenario` instances
    - Strategy must ensure unique agent roles and valid toggle target references
    - _Requirements: all (test infrastructure)_

- [ ] 12. Final checkpoint — Full integration
  - Ensure all tests pass (`pytest --cov=app --cov-fail-under=70`), ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- All 8 correctness properties from the design are covered as property-based test sub-tasks
- The hypothesis strategies in `conftest.py` (task 11.1) are shared across all property tests
- Test structure follows `backend/tests/{unit,integration,property}/` layout from the design
