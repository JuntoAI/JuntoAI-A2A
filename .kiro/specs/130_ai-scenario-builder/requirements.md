# Requirements Document

## Introduction

An AI-powered interactive scenario builder that lets users create custom ArenaScenario JSON configurations through a guided chatbot conversation. The builder integrates into the existing Arena Selector as a "Build Your Own Scenario" option, opens a split-screen modal with an AI chatbot on the left and a live JSON preview on the right, and persists completed scenarios to Firestore so users can reuse them. The chatbot is powered by Claude Opus 4.6 via Vertex AI and walks users through every section of the ArenaScenario schema — metadata, agents, toggles, negotiation params, and outcome receipt — producing JSON that passes full Pydantic validation including cross-reference checks.

## Glossary

- **Builder_Modal**: The full-screen modal UI containing the chatbot, JSON preview, and progress indicator that opens when a user selects "Build Your Own Scenario"
- **Builder_Chatbot**: The AI assistant (Claude Opus 4.6 via Vertex AI) that conducts the guided conversation to collect scenario parameters from the user
- **JSON_Preview**: The right-side panel of the Builder_Modal that displays the scenario JSON being constructed in real time
- **Progress_Indicator**: The percentage bar at the top of the Builder_Modal showing how much of the ArenaScenario schema has been completed
- **Scenario_Builder_API**: The backend FastAPI endpoints that manage builder chat sessions, stream AI responses, validate partial/complete scenarios, and persist user-created scenarios
- **ArenaScenario**: The Pydantic V2 model (`backend/app/scenarios/models.py`) that defines the complete scenario JSON schema with cross-reference validation
- **ScenarioSelector**: The existing frontend dropdown component (`frontend/components/arena/ScenarioSelector.tsx`) that lists available scenarios
- **ScenarioRegistry**: The existing backend class (`backend/app/scenarios/registry.py`) that discovers and indexes scenario JSON files
- **Custom_Scenario_Store**: The Firestore collection that persists user-created scenarios keyed by user email and scenario ID
- **LinkedIn_Persona_Generator**: The subsystem that accepts a public LinkedIn profile URL and generates an AI agent persona based on the person's professional background
- **Health_Check_Analyzer**: The AI-powered subsystem (Claude Opus 4.6 via Vertex AI) that performs simulation readiness analysis on a completed ArenaScenario, evaluating prompt quality, goal tension, budget overlap, toggle effectiveness, turn sanity, stall risk, and regulator feasibility to produce a structured readiness report with actionable recommendations

## Requirements

### Requirement 1: Builder Entry Point in Scenario Selector

**User Story:** As a user, I want to see a "Build Your Own Scenario" option in the scenario dropdown, so that I can create custom negotiation scenarios.

#### Acceptance Criteria

1. WHEN the ScenarioSelector dropdown is rendered, THE ScenarioSelector SHALL display a "Build Your Own Scenario" option visually separated from the list of pre-built scenarios
2. WHEN the user selects "Build Your Own Scenario", THE ScenarioSelector SHALL invoke a callback to open the Builder_Modal instead of fetching a scenario detail
3. WHEN the user has previously saved custom scenarios, THE ScenarioSelector SHALL display those custom scenarios in a "My Scenarios" group below the pre-built scenarios and above the "Build Your Own Scenario" option

### Requirement 2: Builder Modal Layout

**User Story:** As a user, I want a split-screen builder interface, so that I can chat with the AI while seeing my scenario JSON take shape in real time.

#### Acceptance Criteria

1. WHEN the Builder_Modal opens, THE Builder_Modal SHALL display a split-screen layout with the Builder_Chatbot on the left half and the JSON_Preview on the right half
2. WHILE the Builder_Modal is open, THE Progress_Indicator SHALL be visible at the top of the modal showing the percentage of ArenaScenario sections completed
3. WHILE the viewport width is less than 1024px, THE Builder_Modal SHALL stack the Builder_Chatbot above the JSON_Preview in a single-column layout
4. WHEN the user clicks the close button on the Builder_Modal, THE Builder_Modal SHALL prompt the user to confirm abandoning unsaved progress before closing
5. THE Builder_Modal SHALL be rendered as a full-screen overlay with a z-index above all other page content

### Requirement 3: AI Chatbot Guided Conversation

**User Story:** As a user, I want the AI to guide me through building a scenario step by step, so that I don't need to understand the raw JSON schema.

#### Acceptance Criteria

1. WHEN the Builder_Modal opens, THE Builder_Chatbot SHALL send an initial greeting message that explains the builder process and asks the user to describe the negotiation scenario they want to create
2. THE Builder_Chatbot SHALL collect scenario parameters in a structured order: scenario metadata (name, description) first, then agents (one at a time), then toggles, then negotiation parameters, then outcome receipt
3. WHEN the user provides a response, THE Scenario_Builder_API SHALL stream the Builder_Chatbot reply token-by-token via Server-Sent Events to the Builder_Modal
4. WHEN the Builder_Chatbot collects enough information to populate a section of the ArenaScenario schema, THE Scenario_Builder_API SHALL emit a structured JSON delta event containing the updated section
5. IF the user provides ambiguous or incomplete information for a required field, THEN THE Builder_Chatbot SHALL ask a specific follow-up question targeting the missing information rather than proceeding with assumptions
6. WHILE collecting agent definitions, THE Builder_Chatbot SHALL ask for each agent's role, name, type, persona prompt, goals, budget range, tone, output fields, and model selection
7. THE Builder_Chatbot SHALL enforce that at least 2 agents are defined and at least 1 agent has type "negotiator" before proceeding past the agents section

### Requirement 4: Live JSON Preview

**User Story:** As a user, I want to see the scenario JSON update in real time as I answer questions, so that I can verify the AI is capturing my intent correctly.

#### Acceptance Criteria

1. WHEN the Scenario_Builder_API emits a JSON delta event, THE JSON_Preview SHALL update to display the current state of the scenario JSON with syntax highlighting
2. WHILE the scenario JSON is incomplete, THE JSON_Preview SHALL display placeholder markers for sections not yet populated
3. WHEN a section of the JSON is newly updated, THE JSON_Preview SHALL visually highlight the changed section for 2 seconds
4. THE JSON_Preview SHALL render the JSON with 2-space indentation consistent with the existing pretty_print function output format

### Requirement 5: Progress Indicator

**User Story:** As a user, I want to see how far along I am in building my scenario, so that I know how much is left.

#### Acceptance Criteria

1. THE Progress_Indicator SHALL calculate completion percentage based on the number of top-level ArenaScenario sections populated (id, name, description, agents, toggles, negotiation_params, outcome_receipt) out of the total required sections
2. WHEN a section transitions from empty to populated, THE Progress_Indicator SHALL update the displayed percentage within 500ms of the JSON delta event
3. WHEN all required sections are populated and the scenario passes ArenaScenario validation, THE Progress_Indicator SHALL display 100% and enable a "Save Scenario" action

### Requirement 6: Scenario Validation

**User Story:** As a user, I want the builder to validate my scenario before saving, so that I know it will work in the Arena.

#### Acceptance Criteria

1. WHEN the user triggers "Save Scenario", THE Scenario_Builder_API SHALL validate the complete JSON against the ArenaScenario Pydantic model including all cross-reference checks (toggle targets reference valid agent roles, turn_order references valid roles, at least 1 negotiator exists, unique agent roles, budget min <= max)
2. IF the ArenaScenario validation fails, THEN THE Scenario_Builder_API SHALL return the specific validation errors and THE Builder_Chatbot SHALL explain the errors in plain language and guide the user to fix them
3. WHEN the ArenaScenario validation succeeds, THE Scenario_Builder_API SHALL proceed to persist the scenario
4. THE Scenario_Builder_API SHALL perform a round-trip validation: serialize the validated ArenaScenario to JSON via pretty_print, then parse and re-validate the output to confirm equivalence

### Requirement 7: Scenario Persistence

**User Story:** As a user, I want to save my custom scenarios so I can come back and use them in negotiations later.

#### Acceptance Criteria

1. WHEN a scenario passes validation, THE Scenario_Builder_API SHALL store the scenario JSON in the Custom_Scenario_Store Firestore collection keyed by the user's email and a generated scenario ID
2. THE Custom_Scenario_Store SHALL store each scenario document with fields: scenario_json (the full ArenaScenario dict), email (owner), created_at (UTC timestamp), and updated_at (UTC timestamp)
3. WHEN the user loads the Arena page, THE Scenario_Builder_API SHALL return the user's custom scenarios alongside the pre-built scenarios from the ScenarioRegistry
4. WHEN the user selects a custom scenario from the ScenarioSelector, THE system SHALL load and use the custom scenario identically to a pre-built scenario for negotiation initialization
5. THE Scenario_Builder_API SHALL enforce a maximum of 20 custom scenarios per user email

### Requirement 8: LinkedIn Persona Generation

**User Story:** As a user, I want to paste a LinkedIn profile URL and have the AI create an agent persona from it, so that I can quickly build realistic agent profiles.

#### Acceptance Criteria

1. WHEN the user pastes a URL matching the pattern `https://www.linkedin.com/in/*` during agent definition, THE Builder_Chatbot SHALL recognize the URL as a LinkedIn persona generation request
2. WHEN a LinkedIn URL is detected, THE Scenario_Builder_API SHALL instruct the Builder_Chatbot (Claude Opus 4.6) to research the public profile information and generate an agent persona_prompt, suggested role, name, goals, and tone based on the person's professional background
3. IF the LinkedIn URL is invalid or the profile information is insufficient, THEN THE Builder_Chatbot SHALL inform the user that the persona could not be generated and ask the user to provide the agent details manually
4. THE Builder_Chatbot SHALL present the generated persona to the user for review and allow modifications before incorporating it into the scenario JSON

### Requirement 9: Builder Chat Session Management

**User Story:** As a user, I want my builder conversation to be maintained throughout the session, so that the AI has full context of what we've discussed.

#### Acceptance Criteria

1. THE Scenario_Builder_API SHALL maintain the full conversation history for each builder session in memory for the duration of the session
2. WHEN the user sends a message, THE Scenario_Builder_API SHALL include the complete conversation history and the current partial scenario JSON as context to the Builder_Chatbot LLM call
3. WHEN the Builder_Modal is closed and reopened without saving, THE Scenario_Builder_API SHALL start a fresh builder session with no prior conversation history
4. THE Scenario_Builder_API SHALL enforce a maximum conversation length of 50 user messages per builder session to bound LLM context window usage

### Requirement 10: Token Budget Enforcement

**User Story:** As a user, I expect the scenario builder to respect the platform's token limits, so that the system remains fair for all users.

#### Acceptance Criteria

1. WHEN a user sends a message in the Builder_Chatbot, THE Scenario_Builder_API SHALL deduct 1 token from the user's daily token balance (same 100 tokens/day pool used for negotiations)
2. IF the user's token balance reaches 0, THEN THE Scenario_Builder_API SHALL reject further builder messages with an HTTP 429 response and THE Builder_Chatbot SHALL display a message indicating the daily token limit has been reached
3. WHILE the Builder_Modal is open, THE Builder_Modal SHALL display the user's current token balance

### Requirement 11: Backend API Endpoints

**User Story:** As a developer, I want well-defined API endpoints for the scenario builder, so that the frontend can integrate cleanly.

#### Acceptance Criteria

1. THE Scenario_Builder_API SHALL expose a POST `/api/v1/builder/chat` endpoint that accepts `{email, session_id, message}` and returns a streaming SSE response with chatbot reply tokens and JSON delta events
2. THE Scenario_Builder_API SHALL expose a POST `/api/v1/builder/save` endpoint that accepts `{email, scenario_json}`, validates the scenario, persists it to Firestore, and returns the saved scenario summary
3. THE Scenario_Builder_API SHALL expose a GET `/api/v1/builder/scenarios` endpoint that accepts an `email` query parameter and returns the list of the user's custom scenarios
4. THE Scenario_Builder_API SHALL expose a DELETE `/api/v1/builder/scenarios/{scenario_id}` endpoint that accepts an `email` query parameter and deletes the specified custom scenario owned by that user
5. IF any builder endpoint receives a request without a valid email, THEN THE Scenario_Builder_API SHALL return HTTP 401

### Requirement 12: SSE Event Format for Builder

**User Story:** As a developer, I want the builder streaming events to follow a consistent format, so that the frontend can parse them reliably.

#### Acceptance Criteria

1. THE Scenario_Builder_API SHALL emit builder SSE events with `event_type` values: `builder_token` (individual chatbot response tokens), `builder_json_delta` (updated scenario JSON section), `builder_complete` (chatbot finished responding), and `builder_error` (error occurred)
2. WHEN emitting a `builder_json_delta` event, THE Scenario_Builder_API SHALL include the `section` name (e.g., "agents", "toggles") and the `data` containing the updated JSON for that section
3. THE Scenario_Builder_API SHALL format all SSE events as `data: <JSON>\n\n` consistent with the existing SSE format used by the negotiation streaming endpoints

### Requirement 13: Scenario JSON Serialization Round-Trip

**User Story:** As a developer, I want to ensure that scenarios built by the AI can be serialized and deserialized without data loss, so that saved scenarios are always loadable.

#### Acceptance Criteria

1. FOR ALL valid ArenaScenario objects produced by the builder, parsing the pretty_print output then re-validating SHALL produce an equivalent ArenaScenario object (round-trip property)
2. FOR ALL valid ArenaScenario objects produced by the builder, THE Scenario_Builder_API SHALL verify that `load_scenario_from_dict(scenario.model_dump())` produces an equivalent scenario before persisting

### Requirement 14: Scenario Health Check Trigger

**User Story:** As a user, I want the AI to analyze whether my scenario will produce a working simulation before I save it, so that I don't waste tokens on broken or boring negotiations.

#### Acceptance Criteria

1. WHEN the scenario JSON passes ArenaScenario Pydantic validation, THE Scenario_Builder_API SHALL automatically invoke the Health_Check_Analyzer before persisting the scenario
2. THE Health_Check_Analyzer SHALL use Claude Opus 4.6 via Vertex AI (the same model used by the Builder_Chatbot) to perform simulation readiness analysis
3. WHEN the Health_Check_Analyzer produces results, THE Scenario_Builder_API SHALL stream the health check report to the Builder_Modal via SSE using event_type `builder_health_report`
4. WHEN the health check report contains a readiness_score below 60, THE Builder_Chatbot SHALL present the report findings and recommend the user iterate on the scenario before saving
5. WHEN the health check report contains a readiness_score of 60 or above, THE Builder_Modal SHALL allow the user to proceed with saving while displaying the report findings
6. THE Health_Check_Analyzer SHALL include the gold-standard scenario files (talent-war, b2b-sales, ma-buyout, freelance-gig, urban-development) as few-shot reference examples in the analysis prompt

### Requirement 15: Prompt Quality Analysis

**User Story:** As a user, I want the AI to evaluate whether my agent persona prompts are detailed enough to produce meaningful LLM responses, so that agents don't generate generic or incoherent messages.

#### Acceptance Criteria

1. FOR EACH agent in the scenario, THE Health_Check_Analyzer SHALL evaluate the persona_prompt for: presence of a clear negotiation strategy, specificity of character background, inclusion of behavioral constraints (what the agent will and will not do), and sufficient context for the LLM to reason about trade-offs
2. FOR EACH agent in the scenario, THE Health_Check_Analyzer SHALL evaluate the goals list for: specificity (numeric targets where applicable), internal consistency (goals do not contradict each other), and actionability (goals the LLM can translate into negotiation moves)
3. IF a persona_prompt lacks a negotiation strategy or behavioral constraints, THEN THE Health_Check_Analyzer SHALL flag the agent with a "prompt_quality" warning and provide a specific recommendation referencing the gold-standard scenario prompts
4. THE Health_Check_Analyzer SHALL assign each agent a prompt_quality_score from 0 to 100 based on the evaluation criteria

### Requirement 16: Goal Conflict and Tension Validation

**User Story:** As a user, I want the AI to verify that my agents have genuine opposing interests, so that the negotiation produces meaningful back-and-forth rather than instant agreement or aimless conversation.

#### Acceptance Criteria

1. THE Health_Check_Analyzer SHALL identify the primary negotiation dimension (price, terms, scope, or other) from the agents' goals and budget ranges
2. THE Health_Check_Analyzer SHALL verify that at least 2 negotiator agents have goals that create opposing pressure on the primary negotiation dimension
3. IF no genuine goal conflict exists between negotiator agents, THEN THE Health_Check_Analyzer SHALL flag a "no_tension" critical finding and recommend specific goal modifications that would create opposing interests
4. THE Health_Check_Analyzer SHALL evaluate whether non-price dimensions (terms, conditions, timelines, scope) exist in agent goals to create multi-dimensional negotiation friction

### Requirement 17: Budget Overlap Analysis

**User Story:** As a user, I want the AI to check whether agent budget ranges allow for a realistic negotiation, so that the simulation doesn't always fail or always instantly converge.

#### Acceptance Criteria

1. THE Health_Check_Analyzer SHALL compute the overlap zone between negotiator agents' budget ranges (the intersection of [min, max] intervals)
2. IF no overlap exists between any pair of negotiator budget ranges, THEN THE Health_Check_Analyzer SHALL flag a "no_overlap" critical finding and warn that the negotiation will likely always end in failure
3. IF the overlap zone exceeds 50% of both negotiators' total budget ranges, THEN THE Health_Check_Analyzer SHALL flag an "excessive_overlap" warning and warn that the negotiation may converge too quickly
4. THE Health_Check_Analyzer SHALL evaluate whether the agreement_threshold is realistic given the budget gap between negotiator target prices — specifically, whether the gap between targets is at least 3 times the agreement_threshold to allow meaningful negotiation movement
5. THE Health_Check_Analyzer SHALL report the computed overlap zone, the gap between target prices, and the relationship to agreement_threshold in the health check report

### Requirement 18: Toggle Effectiveness Check

**User Story:** As a user, I want the AI to verify that my toggles inject meaningful hidden context that would change agent behavior, so that the investor "aha moment" actually works.

#### Acceptance Criteria

1. FOR EACH toggle in the scenario, THE Health_Check_Analyzer SHALL evaluate whether the hidden_context_payload contains actionable information that would alter the target agent's negotiation strategy
2. FOR EACH toggle in the scenario, THE Health_Check_Analyzer SHALL verify that the hidden_context_payload references specific negotiation dimensions (price, terms, timeline, leverage) rather than generic or vague context
3. IF a toggle's hidden_context_payload does not contain information that would plausibly change the target agent's proposed_price or negotiation stance, THEN THE Health_Check_Analyzer SHALL flag a "weak_toggle" warning with a specific recommendation for strengthening the payload
4. THE Health_Check_Analyzer SHALL verify that toggles target agents whose persona_prompts are compatible with the injected context (the agent can plausibly act on the hidden information)

### Requirement 19: Turn Order and Turn Limit Sanity Check

**User Story:** As a user, I want the AI to verify that the turn order and max turns make sense for my scenario, so that agents get enough speaking time and the negotiation doesn't end prematurely or drag on.

#### Acceptance Criteria

1. THE Health_Check_Analyzer SHALL verify that every agent role defined in the agents list appears at least once in the turn_order
2. THE Health_Check_Analyzer SHALL verify that max_turns provides at least 2 full cycles through the turn_order (max_turns >= 2 * number of unique roles in turn_order)
3. IF a negotiator agent does not appear in the turn_order, THEN THE Health_Check_Analyzer SHALL flag a "missing_from_turn_order" critical finding
4. IF max_turns is fewer than 2 full cycles, THEN THE Health_Check_Analyzer SHALL flag an "insufficient_turns" warning and recommend a minimum turn count based on the number of agents and turn_order length
5. THE Health_Check_Analyzer SHALL evaluate whether regulator agents appear in the turn_order at appropriate intervals to provide meaningful oversight (at least once per cycle)

### Requirement 20: Stall Risk Assessment

**User Story:** As a user, I want the AI to predict whether my scenario configuration is likely to trigger stall detection patterns, so that I can fix the design before running a simulation.

#### Acceptance Criteria

1. THE Health_Check_Analyzer SHALL evaluate the scenario against each stall detection pattern defined in the stall_detector module: price_ping_pong, price_stagnation, message_repetition, and instant_convergence
2. IF negotiator budget target prices are within the agreement_threshold of each other, THEN THE Health_Check_Analyzer SHALL flag an "instant_convergence_risk" warning
3. IF negotiator persona_prompts lack explicit concession strategies or fallback tactics, THEN THE Health_Check_Analyzer SHALL flag a "repetition_risk" warning indicating agents may repeat similar messages
4. IF negotiator budget ranges are narrow (max - min < 3 * agreement_threshold), THEN THE Health_Check_Analyzer SHALL flag a "price_stagnation_risk" warning indicating agents have insufficient room to make meaningful price moves
5. THE Health_Check_Analyzer SHALL produce a stall_risk_score from 0 (no risk) to 100 (high risk) based on the combined assessment of all stall patterns

### Requirement 21: Regulator Feasibility Check

**User Story:** As a user, I want the AI to verify that regulator agents have clear enforcement criteria, so that they provide meaningful oversight rather than rubber-stamping agreements.

#### Acceptance Criteria

1. FOR EACH agent with type "regulator", THE Health_Check_Analyzer SHALL evaluate whether the persona_prompt contains specific enforcement criteria (thresholds, policies, or rules the regulator enforces)
2. FOR EACH agent with type "regulator", THE Health_Check_Analyzer SHALL evaluate whether the goals list contains at least one condition that could trigger a WARNING or BLOCKED status based on negotiator behavior
3. IF a regulator's persona_prompt lacks specific enforcement criteria, THEN THE Health_Check_Analyzer SHALL flag a "weak_regulator" warning and recommend adding concrete thresholds or policy references
4. THE Health_Check_Analyzer SHALL verify that regulator goals reference dimensions that negotiator agents actually negotiate on (a regulator enforcing price caps is only useful if negotiators discuss price)

### Requirement 22: Overall Simulation Readiness Score

**User Story:** As a user, I want a single composite score with actionable recommendations, so that I can quickly understand whether my scenario is ready to run and what to fix if it isn't.

#### Acceptance Criteria

1. THE Health_Check_Analyzer SHALL produce a readiness_score from 0 to 100 computed as a weighted composite of: prompt_quality_scores (25% weight), tension_score (20% weight), budget_overlap_score (20% weight), toggle_effectiveness_score (15% weight), turn_sanity_score (10% weight), and inverse stall_risk_score (10% weight)
2. THE Health_Check_Analyzer SHALL classify the readiness_score into tiers: "Ready" (80-100), "Needs Work" (60-79), "Not Ready" (0-59)
3. FOR EACH finding with severity "critical" or "warning", THE Health_Check_Analyzer SHALL produce a specific, actionable recommendation that references the relevant scenario field and describes the exact change needed
4. THE Health_Check_Analyzer SHALL order recommendations by impact — critical findings first, then warnings sorted by their contribution to the readiness_score
5. THE Health_Check_Analyzer SHALL return the complete report as a structured JSON object containing: readiness_score, tier, per-agent scores, per-check findings, and ordered recommendations

### Requirement 23: Health Check SSE Event Format

**User Story:** As a developer, I want the health check results streamed in a consistent SSE format, so that the frontend can render the report progressively.

#### Acceptance Criteria

1. THE Scenario_Builder_API SHALL emit health check SSE events with event_type `builder_health_check_start` when the analysis begins, `builder_health_check_finding` for each individual finding as it is produced, and `builder_health_check_complete` when the full report is ready
2. WHEN emitting a `builder_health_check_finding` event, THE Scenario_Builder_API SHALL include the check_name (e.g., "prompt_quality", "budget_overlap"), severity ("critical", "warning", "info"), agent_role (if applicable), and a human-readable message
3. WHEN emitting a `builder_health_check_complete` event, THE Scenario_Builder_API SHALL include the full structured report JSON with readiness_score, tier, and ordered recommendations
4. THE Scenario_Builder_API SHALL format all health check SSE events as `data: <JSON>\n\n` consistent with the existing SSE format used by the builder and negotiation streaming endpoints
