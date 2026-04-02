# Requirements Document

## Introduction

This feature adds an "Advanced Configuration" capability to each agent card on the Arena Selector screen (Screen 2). Users can click an "Advanced Config" button on any agent card to open a modal where they can extend the agent's system prompt with free-text instructions. This custom prompt text is sent alongside the scenario config when a negotiation starts, and the backend appends it to the agent's system message during prompt construction. The feature is entirely optional — agents work identically without it.

## Glossary

- **Arena_Selector**: Screen 2 of the core user flow where users pick a scenario, view agent cards, toggle hidden variables, and initialize a negotiation
- **Agent_Card**: A UI component displaying an agent's name, role, goals, and model — one per agent in the selected scenario
- **Advanced_Config_Modal**: A dialog/modal that opens when the user clicks "Advanced Config" on an Agent_Card, containing configuration options for that agent
- **Custom_Prompt**: A free-text string the user writes to extend an agent's system prompt with additional instructions or personality tweaks
- **Agent_Node**: The backend orchestrator function (`create_agent_node`) that builds prompts and invokes the LLM for each agent
- **StartNegotiationRequest**: The Pydantic model for the POST `/api/v1/negotiation/start` request body
- **ArenaScenario**: The Pydantic model representing a complete scenario JSON config

## Requirements

### Requirement 1: Advanced Config Button on Agent Card

**User Story:** As a user, I want to see an "Advanced Config" option on each agent card, so that I can customize agent behavior before starting a negotiation.

#### Acceptance Criteria

1. WHEN a scenario is selected and agent cards are displayed, THE Agent_Card SHALL render a clickable "Advanced Config" button below the agent's model info
2. THE Agent_Card advanced config button SHALL use a Lucide React settings/sliders icon alongside the text label
3. WHEN the user clicks the "Advanced Config" button, THE Arena_Selector SHALL open the Advanced_Config_Modal for that specific agent
4. THE Agent_Card SHALL visually indicate when a Custom_Prompt has been configured for that agent (e.g., a small dot or badge)

### Requirement 2: Advanced Configuration Modal

**User Story:** As a user, I want a clean modal interface for configuring advanced agent settings, so that I can focus on customization without leaving the Arena Selector.

#### Acceptance Criteria

1. WHEN the Advanced_Config_Modal opens, THE Advanced_Config_Modal SHALL display the agent's name and role in the modal header
2. THE Advanced_Config_Modal SHALL contain a labeled textarea input for the Custom_Prompt field
3. THE Advanced_Config_Modal textarea SHALL display placeholder text: "e.g., Be more aggressive in counter-offers and always cite market data to justify your position."
4. THE Advanced_Config_Modal SHALL include a "Save" button that stores the Custom_Prompt in local component state and closes the modal
5. THE Advanced_Config_Modal SHALL include a "Cancel" button that discards unsaved changes and closes the modal
6. WHEN the user presses the Escape key, THE Advanced_Config_Modal SHALL close and discard unsaved changes
7. THE Advanced_Config_Modal SHALL trap keyboard focus within the modal while open (accessibility requirement)
8. THE Advanced_Config_Modal SHALL render a backdrop overlay that prevents interaction with the Arena_Selector behind it

### Requirement 3: Custom Prompt Character Limit

**User Story:** As a system operator, I want to enforce a character limit on custom prompts, so that users cannot inject excessively long text that inflates LLM token costs or degrades performance.

#### Acceptance Criteria

1. THE Advanced_Config_Modal SHALL enforce a maximum character limit of 500 characters on the Custom_Prompt textarea
2. WHILE the user types in the Custom_Prompt textarea, THE Advanced_Config_Modal SHALL display a live character counter showing current length vs. maximum (e.g., "142 / 500")
3. WHEN the Custom_Prompt reaches 500 characters, THE Advanced_Config_Modal SHALL prevent further input and visually indicate the limit has been reached
4. IF the user pastes text that exceeds 500 characters, THEN THE Advanced_Config_Modal SHALL truncate the pasted content to 500 characters

### Requirement 4: Custom Prompt State Management

**User Story:** As a user, I want my custom prompts to persist across scenario interactions within the same session, so that I don't lose my configuration when toggling hidden variables.

#### Acceptance Criteria

1. THE Arena_Selector SHALL maintain a mapping of agent role to Custom_Prompt string in component state
2. WHEN the user saves a Custom_Prompt for an agent, THE Arena_Selector SHALL store the value keyed by the agent's role
3. WHEN the user selects a different scenario, THE Arena_Selector SHALL clear all Custom_Prompt values (since agents change per scenario)
4. WHEN the user re-opens the Advanced_Config_Modal for an agent that already has a Custom_Prompt, THE Advanced_Config_Modal SHALL pre-populate the textarea with the previously saved value

### Requirement 5: Send Custom Prompts to Backend

**User Story:** As a developer, I want custom prompts to be transmitted to the backend when a negotiation starts, so that the orchestrator can inject them into agent system messages.

#### Acceptance Criteria

1. WHEN the user clicks "Initialize A2A Protocol", THE Arena_Selector SHALL include a `custom_prompts` field in the StartNegotiationRequest payload
2. THE `custom_prompts` field SHALL be a JSON object mapping agent role strings to Custom_Prompt strings (e.g., `{"Recruiter": "Be more aggressive...", "Candidate": "Focus on remote work..."}`)
3. THE `custom_prompts` field SHALL omit agents that have no Custom_Prompt configured (empty or unset values are excluded)
4. IF no agents have Custom_Prompts configured, THEN THE `custom_prompts` field SHALL be an empty object or omitted entirely

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
