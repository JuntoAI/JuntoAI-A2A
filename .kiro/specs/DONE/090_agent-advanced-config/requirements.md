# Requirements Document

## Introduction

This feature adds an "Advanced Configuration" capability to each agent card on the Arena Selector screen (Screen 2). Users can click an "Advanced Config" button on any agent card to open a modal where they can extend the agent's system prompt with free-text instructions and override the agent's default LLM model by selecting from the list of currently available models. Both the custom prompt text and model override are sent alongside the scenario config when a negotiation starts. The backend appends the custom prompt to the agent's system message and routes the LLM call through the overridden model when specified. The feature is entirely optional — agents work identically without any overrides.

## Glossary

- **Arena_Selector**: Screen 2 of the core user flow where users pick a scenario, view agent cards, toggle hidden variables, and initialize a negotiation
- **Agent_Card**: A UI component displaying an agent's name, role, goals, and model — one per agent in the selected scenario
- **Advanced_Config_Modal**: A dialog/modal that opens when the user clicks "Advanced Config" on an Agent_Card, containing configuration options for that agent
- **Custom_Prompt**: A free-text string the user writes to extend an agent's system prompt with additional instructions or personality tweaks
- **Agent_Node**: The backend orchestrator function (`create_agent_node`) that builds prompts and invokes the LLM for each agent
- **StartNegotiationRequest**: The Pydantic model for the POST `/api/v1/negotiation/start` request body
- **ArenaScenario**: The Pydantic model representing a complete scenario JSON config
- **Model_Override**: A user-selected LLM model that replaces the agent's default `model_id` from the scenario config for a single negotiation session
- **Available_Models**: The set of LLM model identifiers the system can instantiate via the Model_Router — currently: `gemini-2.5-flash`, `gemini-2.5-pro`, `gemini-3-flash-preview`, `claude-3-5-sonnet`, `claude-sonnet-4-6`
- **Model_Router**: The backend module (`model_router.py`) that maps model_id strings to LangChain chat model instances based on the model-family prefix (`gemini` → ChatVertexAI, `claude` → ChatAnthropicVertex)
- **Model_Selector**: A dropdown UI control in the Advanced_Config_Modal that lets the user pick from Available_Models to override the agent's default model

## Requirements

### Requirement 1: Advanced Config Button on Agent Card

**User Story:** As a user, I want to see an "Advanced Config" option on each agent card, so that I can customize agent behavior before starting a negotiation.

#### Acceptance Criteria

1. WHEN a scenario is selected and agent cards are displayed, THE Agent_Card SHALL render a clickable "Advanced Config" button below the agent's model info
2. THE Agent_Card advanced config button SHALL use a Lucide React settings/sliders icon alongside the text label
3. WHEN the user clicks the "Advanced Config" button, THE Arena_Selector SHALL open the Advanced_Config_Modal for that specific agent
4. THE Agent_Card SHALL visually indicate when a Custom_Prompt has been configured for that agent (e.g., a small dot or badge)
5. THE Agent_Card SHALL visually indicate when a Model_Override has been configured for that agent, displaying the overridden model name in place of the default

### Requirement 2: Advanced Configuration Modal

**User Story:** As a user, I want a clean modal interface for configuring advanced agent settings, so that I can focus on customization without leaving the Arena Selector.

#### Acceptance Criteria

1. WHEN the Advanced_Config_Modal opens, THE Advanced_Config_Modal SHALL display the agent's name and role in the modal header
2. THE Advanced_Config_Modal SHALL contain a labeled textarea input for the Custom_Prompt field
3. THE Advanced_Config_Modal SHALL contain a labeled Model_Selector dropdown below the Custom_Prompt textarea
4. THE Advanced_Config_Modal textarea SHALL display placeholder text: "e.g., Be more aggressive in counter-offers and always cite market data to justify your position."
5. THE Model_Selector SHALL display the agent's default model_id as the pre-selected option with a "(default)" suffix label
6. THE Advanced_Config_Modal SHALL include a "Save" button that stores the Custom_Prompt and Model_Override in local component state and closes the modal
7. THE Advanced_Config_Modal SHALL include a "Cancel" button that discards unsaved changes and closes the modal
8. WHEN the user presses the Escape key, THE Advanced_Config_Modal SHALL close and discard unsaved changes
9. THE Advanced_Config_Modal SHALL trap keyboard focus within the modal while open (accessibility requirement)
10. THE Advanced_Config_Modal SHALL render a backdrop overlay that prevents interaction with the Arena_Selector behind it

### Requirement 3: Custom Prompt Character Limit

**User Story:** As a system operator, I want to enforce a character limit on custom prompts, so that users cannot inject excessively long text that inflates LLM token costs or degrades performance.

#### Acceptance Criteria

1. THE Advanced_Config_Modal SHALL enforce a maximum character limit of 500 characters on the Custom_Prompt textarea
2. WHILE the user types in the Custom_Prompt textarea, THE Advanced_Config_Modal SHALL display a live character counter showing current length vs. maximum (e.g., "142 / 500")
3. WHEN the Custom_Prompt reaches 500 characters, THE Advanced_Config_Modal SHALL prevent further input and visually indicate the limit has been reached
4. IF the user pastes text that exceeds 500 characters, THEN THE Advanced_Config_Modal SHALL truncate the pasted content to 500 characters

### Requirement 4: Custom Prompt and Model Override State Management

**User Story:** As a user, I want my custom prompts and model overrides to persist across scenario interactions within the same session, so that I don't lose my configuration when toggling hidden variables.

#### Acceptance Criteria

1. THE Arena_Selector SHALL maintain a mapping of agent role to Custom_Prompt string in component state
2. THE Arena_Selector SHALL maintain a separate mapping of agent role to Model_Override string in component state
3. WHEN the user saves a Custom_Prompt for an agent, THE Arena_Selector SHALL store the value keyed by the agent's role
4. WHEN the user saves a Model_Override for an agent, THE Arena_Selector SHALL store the selected model_id keyed by the agent's role
5. WHEN the user selects a different scenario, THE Arena_Selector SHALL clear all Custom_Prompt and Model_Override values (since agents change per scenario)
6. WHEN the user re-opens the Advanced_Config_Modal for an agent that already has a Custom_Prompt, THE Advanced_Config_Modal SHALL pre-populate the textarea with the previously saved value
7. WHEN the user re-opens the Advanced_Config_Modal for an agent that already has a Model_Override, THE Model_Selector SHALL pre-select the previously saved model

### Requirement 5: Send Custom Prompts and Model Overrides to Backend

**User Story:** As a developer, I want custom prompts and model overrides to be transmitted to the backend when a negotiation starts, so that the orchestrator can inject them into agent system messages and route LLM calls accordingly.

#### Acceptance Criteria

1. WHEN the user clicks "Initialize A2A Protocol", THE Arena_Selector SHALL include a `custom_prompts` field in the StartNegotiationRequest payload
2. THE `custom_prompts` field SHALL be a JSON object mapping agent role strings to Custom_Prompt strings (e.g., `{"Recruiter": "Be more aggressive...", "Candidate": "Focus on remote work..."}`)
3. THE `custom_prompts` field SHALL omit agents that have no Custom_Prompt configured (empty or unset values are excluded)
4. IF no agents have Custom_Prompts configured, THEN THE `custom_prompts` field SHALL be an empty object or omitted entirely
5. WHEN the user clicks "Initialize A2A Protocol", THE Arena_Selector SHALL include a `model_overrides` field in the StartNegotiationRequest payload
6. THE `model_overrides` field SHALL be a JSON object mapping agent role strings to model_id strings (e.g., `{"Recruiter": "claude-3-5-sonnet", "Candidate": "gemini-2.5-pro"}`)
7. THE `model_overrides` field SHALL omit agents that have no Model_Override configured (agents using their default model are excluded)
8. IF no agents have Model_Overrides configured, THEN THE `model_overrides` field SHALL be an empty object or omitted entirely

### Requirement 6: Backend Custom Prompt Validation

**User Story:** As a system operator, I want the backend to validate custom prompts, so that malformed or oversized payloads are rejected.

#### Acceptance Criteria

1. THE StartNegotiationRequest Pydantic model SHALL accept an optional `custom_prompts` field of type `dict[str, str]` with a default of empty dict
2. WHEN a `custom_prompts` value exceeds 500 characters, THE backend SHALL return HTTP 422 with a validation error
3. WHEN a `custom_prompts` key does not match any agent role in the selected scenario, THE backend SHALL ignore that key (no error, just skip)
4. THE backend SHALL store the validated `custom_prompts` in the NegotiationStateModel alongside `hidden_context`

### Requirement 7: Backend Prompt Injection

**User Story:** As a developer, I want the orchestrator to append custom prompts to agent system messages, so that user-provided instructions influence agent behavior.

#### Acceptance Criteria

1. WHEN building the system message for an agent, THE Agent_Node SHALL check for a Custom_Prompt in the negotiation state for that agent's role
2. WHEN a Custom_Prompt exists for the agent, THE Agent_Node SHALL append it to the system message after the persona prompt and goals but before the output schema instructions
3. THE Agent_Node SHALL prefix the Custom_Prompt with a clear delimiter: "\nAdditional user instructions:\n"
4. WHEN no Custom_Prompt exists for the agent, THE Agent_Node SHALL build the system message identically to the current behavior (no change)

### Requirement 8: Responsive Modal Layout

**User Story:** As a mobile user, I want the advanced config modal to work well on small screens, so that I can configure agents on any device.

#### Acceptance Criteria

1. WHILE the viewport width is less than 1024px, THE Advanced_Config_Modal SHALL render as a full-width bottom sheet or centered modal with horizontal padding
2. WHILE the viewport width is 1024px or greater, THE Advanced_Config_Modal SHALL render as a centered modal with a maximum width of 480px
3. THE Advanced_Config_Modal textarea SHALL have a minimum height of 120px to provide comfortable editing space

### Requirement 9: Available Models List API

**User Story:** As a frontend developer, I want a backend endpoint that returns the list of currently available LLM models, so that the Model_Selector dropdown is always in sync with what the system supports.

#### Acceptance Criteria

1. THE backend SHALL expose a GET `/api/v1/models` endpoint that returns the list of Available_Models
2. THE `/api/v1/models` response SHALL be a JSON array of objects, each containing `model_id` (string) and `family` (string, either "gemini" or "claude")
3. THE `/api/v1/models` endpoint SHALL derive the model list from the union of all `model_id` and `fallback_model_id` values across all loaded scenarios in the ScenarioRegistry
4. THE `/api/v1/models` endpoint SHALL return only models whose family prefix exists in the Model_Router MODEL_FAMILIES mapping (filtering out any unrecognized model IDs)

### Requirement 10: Model Selector Dropdown Population

**User Story:** As a user, I want the model selector to show only models the system actually supports, so that I cannot select a model that would fail at runtime.

#### Acceptance Criteria

1. WHEN the Arena_Selector screen loads, THE Arena_Selector SHALL fetch the Available_Models list from the `/api/v1/models` endpoint
2. WHEN the Advanced_Config_Modal opens, THE Model_Selector SHALL populate its options from the fetched Available_Models list
3. THE Model_Selector SHALL display each model option with its model_id as the label and its family as a secondary label or grouped heading (e.g., "gemini-2.5-flash (Gemini)")
4. THE Model_Selector SHALL place the agent's current default model_id as the first option with a "(default)" suffix
5. IF the `/api/v1/models` fetch fails, THEN THE Model_Selector SHALL display only the agent's default model_id and disable the dropdown with a tooltip indicating the model list is unavailable

### Requirement 11: Backend Model Override Validation

**User Story:** As a system operator, I want the backend to validate model overrides against the Available_Models list, so that invalid model selections are rejected before a negotiation starts.

#### Acceptance Criteria

1. THE StartNegotiationRequest Pydantic model SHALL accept an optional `model_overrides` field of type `dict[str, str]` with a default of empty dict
2. WHEN a `model_overrides` value is not present in the Available_Models list, THE backend SHALL return HTTP 422 with a validation error specifying the invalid model_id
3. WHEN a `model_overrides` key does not match any agent role in the selected scenario, THE backend SHALL ignore that key (no error, just skip)
4. THE backend SHALL store the validated `model_overrides` in the NegotiationStateModel alongside `hidden_context` and `custom_prompts`

### Requirement 12: Backend Model Override Application

**User Story:** As a developer, I want the orchestrator to use the overridden model when invoking the LLM for an agent, so that user-selected models take effect during negotiation.

#### Acceptance Criteria

1. WHEN building the LLM call for an agent, THE Agent_Node SHALL check for a Model_Override in the negotiation state for that agent's role
2. WHEN a Model_Override exists for the agent, THE Agent_Node SHALL pass the overridden model_id to the Model_Router instead of the agent's default model_id from the scenario config
3. WHEN a Model_Override exists for the agent, THE Agent_Node SHALL preserve the agent's original `fallback_model_id` from the scenario config as the fallback
4. WHEN no Model_Override exists for the agent, THE Agent_Node SHALL use the agent's default model_id from the scenario config (no change to current behavior)

### Requirement 13: Model Override Persistence in Negotiation State

**User Story:** As a developer, I want model overrides to be persisted in the negotiation state, so that they survive across the full negotiation lifecycle and are available for every agent turn.

#### Acceptance Criteria

1. THE NegotiationStateModel SHALL include a `model_overrides` field of type `dict[str, str]` with a default of empty dict
2. THE `create_initial_state` factory function SHALL accept an optional `model_overrides` parameter and store it in the NegotiationState
3. THE NegotiationState TypedDict SHALL include a `model_overrides` field of type `dict[str, str]`
4. WHEN persisting the negotiation state to Firestore, THE backend SHALL include the `model_overrides` field in the document
