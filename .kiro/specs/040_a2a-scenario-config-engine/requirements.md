# Requirements Document

## Introduction

This specification covers the Config-Driven Scenario Engine for the JuntoAI A2A MVP. The engine decouples the backend from any single hardcoded negotiation use case by loading "Arena Scenarios" from JSON configuration files at runtime. Each scenario JSON file defines the full cast of AI agents (personas, goals, budgets, output schemas, LLM assignments) and a set of investor-facing "Information Toggles" that inject hidden context into agent system prompts before the simulation begins. The MVP ships with three pre-configured scenarios (Talent War, M&A Buyout, Enterprise B2B Sales). The architecture ensures a 4th scenario can be added by dropping a new JSON file into the scenarios directory without modifying frontend or backend code. The JSON parser, scenario validation, toggle injection into LangGraph NegotiationState, and the three MVP scenario JSON files are all in scope. The LangGraph state machine and agent node implementations are covered in the `a2a-langgraph-orchestration` spec. The FastAPI scaffold and SSE streaming are covered in the `a2a-backend-core-sse` spec.

## Glossary

- **Scenario_Engine**: The backend module responsible for discovering, loading, parsing, validating, and serving Arena Scenario configurations.
- **Arena_Scenario**: A complete negotiation scenario definition loaded from a JSON file, containing metadata, agent definitions, toggle definitions, and negotiation parameters.
- **Scenario_File**: A JSON file stored in the scenarios directory conforming to the Arena Scenario JSON schema.
- **Scenario_Registry**: An in-memory index maintained by the Scenario_Engine that maps scenario identifiers to their parsed Arena_Scenario objects.
- **Agent_Definition**: A JSON object within an Arena_Scenario that defines a single AI agent's role name, persona system prompt, goals, budget constraints, tone, output schema fields, and assigned LLM model identifier.
- **Toggle_Definition**: A JSON object within an Arena_Scenario that defines a single investor-facing information toggle, including its identifier, display label, target agent role, and the hidden context payload to inject when activated.
- **Hidden_Context**: A dictionary injected into the `hidden_context` field of the LangGraph NegotiationState before the first node executes, keyed by agent role, containing toggle payloads for activated toggles.
- **Scenario_Schema**: The JSON Schema that all Scenario_Files must conform to for successful validation.
- **Scenario_Loader**: The component within the Scenario_Engine that reads Scenario_Files from disk and parses them into Arena_Scenario objects.
- **Toggle_Injector**: The component within the Scenario_Engine that takes a list of activated toggle identifiers and an Arena_Scenario, and produces the Hidden_Context dictionary for injection into NegotiationState.
- **NegotiationState**: The LangGraph-compatible state object (defined in the `a2a-langgraph-orchestration` spec) that includes a `hidden_context` field of type `dict[str, Any]`.
- **Pretty_Printer**: The component that serializes an Arena_Scenario object back into a formatted JSON string.

## Requirements

### Requirement 1: Arena Scenario JSON Schema Definition

**User Story:** As a developer, I want a well-defined JSON schema for Arena Scenarios, so that scenario files are validated consistently and new scenarios can be authored without ambiguity.

#### Acceptance Criteria

1. THE Scenario_Engine SHALL define a Scenario_Schema that requires a top-level `id` field of type string, uniquely identifying the scenario.
2. THE Scenario_Schema SHALL require a top-level `name` field of type string containing the human-readable scenario title.
3. THE Scenario_Schema SHALL require a top-level `description` field of type string summarizing the scenario premise.
4. THE Scenario_Schema SHALL require an `agents` field containing an array of exactly 3 Agent_Definition objects.
5. THE Scenario_Schema SHALL require each Agent_Definition to contain `role` (string), `name` (string), `persona_prompt` (string), `goals` (array of strings), `budget` (object with `min`, `max`, and `target` numeric fields), `tone` (string), `output_fields` (array of strings), and `model_id` (string) fields.
6. THE Scenario_Schema SHALL require a `toggles` field containing an array of at least 1 Toggle_Definition object.
7. THE Scenario_Schema SHALL require each Toggle_Definition to contain `id` (string), `label` (string), `target_agent_role` (string), and `hidden_context_payload` (object) fields.
8. THE Scenario_Schema SHALL require a `negotiation_params` field containing `max_turns` (integer) and `agreement_threshold` (number) fields.
9. THE Scenario_Schema SHALL require the `target_agent_role` in each Toggle_Definition to match the `role` field of one of the Agent_Definitions in the same scenario.

### Requirement 2: JSON Scenario Parser

**User Story:** As a developer, I want a JSON parser that loads and validates Arena Scenario files, so that the backend can reliably consume scenario configurations at runtime.

#### Acceptance Criteria

1. WHEN a valid Scenario_File path is provided, THE Scenario_Loader SHALL read the file, parse the JSON content, and return a validated Arena_Scenario object.
2. WHEN the JSON content does not conform to the Scenario_Schema, THE Scenario_Loader SHALL raise a `ScenarioValidationError` containing the file path and a list of specific validation failures.
3. WHEN the Scenario_File path does not exist or is unreadable, THE Scenario_Loader SHALL raise a `ScenarioFileNotFoundError` containing the attempted file path.
4. WHEN the file content is not valid JSON, THE Scenario_Loader SHALL raise a `ScenarioParseError` containing the file path and the JSON decode error details.
5. THE Scenario_Loader SHALL validate that all `target_agent_role` values in Toggle_Definitions reference a valid `role` from the `agents` array within the same scenario.
6. THE Scenario_Loader SHALL validate that all Agent_Definition `role` values within a single scenario are unique.

### Requirement 3: Arena Scenario Pretty Printer

**User Story:** As a developer, I want to serialize Arena_Scenario objects back to formatted JSON, so that scenarios can be exported and round-trip integrity can be verified.

#### Acceptance Criteria

1. THE Pretty_Printer SHALL accept an Arena_Scenario object and return a JSON string formatted with 2-space indentation.
2. THE Pretty_Printer SHALL preserve all fields from the Arena_Scenario object in the output JSON.
3. FOR ALL valid Arena_Scenario objects, parsing the Pretty_Printer output back through the Scenario_Loader SHALL produce an equivalent Arena_Scenario object (round-trip property).

### Requirement 4: Scenario Registry and Discovery

**User Story:** As a developer, I want the engine to automatically discover and index all scenario files from a directory, so that adding a new scenario requires only dropping a JSON file without code changes.

#### Acceptance Criteria

1. WHEN the Scenario_Engine initializes, THE Scenario_Engine SHALL scan a configurable directory path for all files matching the `*.scenario.json` pattern.
2. WHEN Scenario_Files are discovered, THE Scenario_Engine SHALL parse and validate each file using the Scenario_Loader and register valid scenarios in the Scenario_Registry.
3. IF a discovered Scenario_File fails validation, THEN THE Scenario_Engine SHALL log a warning with the file path and validation errors, and skip the invalid file without halting initialization.
4. THE Scenario_Registry SHALL provide a `list_scenarios()` method that returns a list of all registered Arena_Scenario identifiers and names.
5. WHEN a valid scenario `id` is provided, THE Scenario_Registry SHALL return the corresponding Arena_Scenario object.
6. IF a scenario `id` that does not exist in the registry is requested, THEN THE Scenario_Registry SHALL raise a `ScenarioNotFoundError` with the requested identifier.
7. THE Scenario_Engine SHALL accept the scenarios directory path from a `SCENARIOS_DIR` environment variable with a default value of `./scenarios`.

### Requirement 5: Investor Toggle Injection into NegotiationState

**User Story:** As a developer, I want activated investor toggles to be dynamically injected as hidden context into the LangGraph NegotiationState before the first node executes, so that information asymmetry alters agent behavior at runtime.

#### Acceptance Criteria

1. WHEN a negotiation is started with a scenario `id` and a list of activated toggle identifiers, THE Toggle_Injector SHALL look up each toggle identifier in the corresponding Arena_Scenario.
2. WHEN an activated toggle is found, THE Toggle_Injector SHALL add the toggle's `hidden_context_payload` to the Hidden_Context dictionary, keyed by the toggle's `target_agent_role`.
3. WHEN multiple toggles target the same agent role, THE Toggle_Injector SHALL merge their `hidden_context_payload` objects into a single dictionary under that agent role key.
4. WHEN the Hidden_Context dictionary is assembled, THE Toggle_Injector SHALL set the `hidden_context` field of the initial NegotiationState to the assembled dictionary before the LangGraph graph execution begins.
5. WHEN no toggles are activated, THE Toggle_Injector SHALL set the `hidden_context` field to an empty dictionary.
6. IF an activated toggle identifier does not exist in the Arena_Scenario, THEN THE Toggle_Injector SHALL raise an `InvalidToggleError` with the unrecognized toggle identifier and the scenario `id`.

### Requirement 6: Scenario A — The Talent War

**User Story:** As a product owner, I want the Talent War scenario pre-configured as a JSON file, so that investors can demo an HR negotiation out of the box.

#### Acceptance Criteria

1. THE Scenario_Engine SHALL include a Scenario_File named `talent-war.scenario.json` that conforms to the Scenario_Schema.
2. THE `talent-war.scenario.json` SHALL define Agent 1 with role `"Recruiter"`, name `"Sarah"`, persona as a Corporate Recruiter, max budget `130000`, target `110000`, and a goal to secure the candidate in-office 5 days per week.
3. THE `talent-war.scenario.json` SHALL define Agent 2 with role `"Candidate"`, name `"Alex"`, persona as a Senior DevOps Candidate, min budget `120000`, and a goal demanding minimum 3 days remote work.
4. THE `talent-war.scenario.json` SHALL define Agent 3 with role `"Regulator"`, name `"HR Compliance Bot"`, persona as an HR compliance monitor that flags unauthorized stock options or biased language.
5. THE `talent-war.scenario.json` SHALL define Toggle 1 with id `"competing_offer"`, label `"Give Alex a hidden €125k competing offer from Google"`, targeting the `"Candidate"` role, with a `hidden_context_payload` containing the competing offer details.
6. THE `talent-war.scenario.json` SHALL define Toggle 2 with id `"deadline_pressure"`, label `"Make Sarah desperate - deadline in 24 hours"`, targeting the `"Recruiter"` role, with a `hidden_context_payload` containing the deadline pressure context.

### Requirement 7: Scenario B — The M&A Buyout

**User Story:** As a product owner, I want the M&A Buyout scenario pre-configured as a JSON file, so that investors can demo a corporate acquisition negotiation out of the box.

#### Acceptance Criteria

1. THE Scenario_Engine SHALL include a Scenario_File named `ma-buyout.scenario.json` that conforms to the Scenario_Schema.
2. THE `ma-buyout.scenario.json` SHALL define Agent 1 with role `"Buyer"`, name `"Titan Corp CEO"`, persona as an aggressive corporate acquirer, max budget `50000000`, target `35000000`.
3. THE `ma-buyout.scenario.json` SHALL define Agent 2 with role `"Seller"`, name `"Innovate Tech Founder"`, persona as a defensive founder, min budget `40000000`, and a goal demanding 2-year team retention.
4. THE `ma-buyout.scenario.json` SHALL define Agent 3 with role `"Regulator"`, name `"EU Regulator Bot"`, persona as an EU compliance monitor that blocks deals involving total data monopoly.
5. THE `ma-buyout.scenario.json` SHALL define Toggle 1 with id `"hidden_debt"`, label `"Give Titan Corp secret knowledge of Innovate Tech's €5M hidden debt"`, targeting the `"Buyer"` role, with a `hidden_context_payload` containing the hidden debt intelligence.
6. THE `ma-buyout.scenario.json` SHALL define Toggle 2 with id `"max_strictness"`, label `"Set EU Regulator to Maximum Strictness"`, targeting the `"Regulator"` role, with a `hidden_context_payload` containing the maximum strictness directive.

### Requirement 8: Scenario C — Enterprise B2B Sales

**User Story:** As a product owner, I want the Enterprise B2B Sales scenario pre-configured as a JSON file, so that investors can demo a SaaS sales negotiation out of the box.

#### Acceptance Criteria

1. THE Scenario_Engine SHALL include a Scenario_File named `b2b-sales.scenario.json` that conforms to the Scenario_Schema.
2. THE `b2b-sales.scenario.json` SHALL define Agent 1 with role `"Seller"`, name `"SaaS Account Executive"`, persona as a CRM software sales representative, list price `100000` per year, target `80000`.
3. THE `b2b-sales.scenario.json` SHALL define Agent 2 with role `"Buyer"`, name `"Target CTO"`, persona as a technology executive needing the software, budget capped at `70000`.
4. THE `b2b-sales.scenario.json` SHALL define Agent 3 with role `"Regulator"`, name `"Procurement Bot"`, persona as a procurement compliance monitor ensuring SLA guarantees and data compliance.
5. THE `b2b-sales.scenario.json` SHALL define Toggle 1 with id `"q4_pressure"`, label `"It is Q4 - AE is desperate to hit quota"`, targeting the `"Seller"` role, with a `hidden_context_payload` containing the Q4 quota pressure context.
6. THE `b2b-sales.scenario.json` SHALL define Toggle 2 with id `"budget_freeze"`, label `"CTO has budget freeze"`, targeting the `"Buyer"` role, with a `hidden_context_payload` containing the budget freeze constraint.

### Requirement 9: Scenario API Endpoint Integration

**User Story:** As a frontend developer, I want API endpoints to list available scenarios and retrieve scenario details, so that the Arena Selector UI can be populated dynamically.

#### Acceptance Criteria

1. THE Backend SHALL expose a `GET /api/v1/scenarios` endpoint that returns a JSON array of objects containing `id`, `name`, and `description` for each registered Arena_Scenario.
2. WHEN a valid scenario `id` is provided, THE Backend SHALL expose a `GET /api/v1/scenarios/{scenario_id}` endpoint that returns the full Arena_Scenario object as JSON, including agent definitions and toggle definitions.
3. IF a scenario `id` that does not exist is requested via the detail endpoint, THEN THE Backend SHALL return an HTTP 404 response with a JSON error body containing the requested `scenario_id`.
4. WHEN a negotiation start request includes a `scenario_id` and an `active_toggles` array, THE Backend SHALL use the Toggle_Injector to assemble the Hidden_Context and pass it to the Orchestrator as the initial `hidden_context` field of the NegotiationState.

### Requirement 10: Extensibility Without Code Changes

**User Story:** As a developer, I want to add a new scenario by placing a single JSON file in the scenarios directory, so that the platform is truly config-driven and requires no code changes for new use cases.

#### Acceptance Criteria

1. WHEN a new valid Scenario_File is placed in the scenarios directory and the Scenario_Engine is restarted, THE Scenario_Registry SHALL include the new scenario in the `list_scenarios()` output.
2. WHEN a new Scenario_File defines agent roles not previously used (e.g., `"Landlord"`, `"Tenant"`), THE Scenario_Engine SHALL accept the new roles without requiring code changes.
3. WHEN a new Scenario_File defines custom toggle payloads with arbitrary key-value pairs, THE Toggle_Injector SHALL inject the payloads into Hidden_Context without requiring code changes.
4. THE Scenario_Engine SHALL impose no hardcoded limit on the number of Scenario_Files that can be registered.
