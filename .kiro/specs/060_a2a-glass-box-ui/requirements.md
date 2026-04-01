# Requirements Document

## Introduction

This specification covers the real-time simulation UI for the JuntoAI A2A MVP, consisting of three major screens: the Arena Selector and Control Panel, the Glass Box live simulation view, and the Outcome Receipt dashboard. The Control Panel allows users to select a scenario from the backend API, view the cast of AI agents, toggle hidden context injections, and launch a negotiation. The Glass Box is a split-screen layout that consumes the backend SSE stream to display agent inner thoughts in a terminal-style panel, public messages in a chat-style panel, and live metrics (current offer, regulator traffic light, token balance) in a top dashboard. The Outcome Receipt triggers when the negotiation reaches a terminal state and displays final terms with ROI metrics. The Next.js scaffold, landing page, access gate, and token system are covered in the `a2a-frontend-gate-waitlist` spec. The FastAPI backend, SSE streaming endpoint, and event models are covered in the `a2a-backend-core-sse` spec. The scenario listing API and toggle definitions are covered in the `a2a-scenario-config-engine` spec.

## Glossary

- **Control_Panel**: The Frontend page (`/arena`) that displays the Scenario_Selector, Agent_Cards, Information_Toggles, and the Initialize button.
- **Scenario_Selector**: A dropdown component on the Control_Panel that fetches and displays available Arena Scenarios from `GET /api/v1/scenarios`.
- **Agent_Card**: A UI card component that displays an AI agent's name, role, base goals, and assigned LLM model identifier.
- **Information_Toggle**: A checkbox component on the Control_Panel representing a single investor-facing toggle that injects hidden context into an agent before simulation.
- **Glass_Box**: The Frontend page (`/arena/session/{session_id}`) that renders the live split-screen simulation view consuming the SSE stream.
- **Terminal_Panel**: The left column of the Glass_Box displaying agent inner thoughts in a scrolling, terminal-style format with dark background and monospace text.
- **Chat_Panel**: The center column of the Glass_Box displaying official public messages exchanged between agents in a chat-style interface.
- **Metrics_Dashboard**: The top bar of the Glass_Box displaying the Current_Offer, Regulator_Traffic_Light, Turn_Counter, and Token_Balance.
- **Current_Offer**: A numeric value displayed in the Metrics_Dashboard that updates dynamically as agents propose new prices.
- **Regulator_Traffic_Light**: A visual indicator in the Metrics_Dashboard showing Green (Compliant/CLEAR), Yellow (WARNING), or Red (BLOCKED) based on the Regulator agent's status.
- **Turn_Counter**: A numeric display in the Metrics_Dashboard showing the current turn number out of the maximum turns.
- **Token_Balance_Display**: A display in the Metrics_Dashboard showing the user's remaining tokens formatted as "Tokens: X / 100".
- **SSE_Client**: The client-side module that connects to `GET /api/v1/negotiation/stream/{session_id}` and parses incoming Server-Sent Events into typed event objects.
- **Outcome_Receipt**: The Frontend view that replaces or overlays the Glass_Box when the negotiation reaches a terminal `deal_status` of `"Agreed"`, `"Blocked"`, or `"Failed"`.
- **ROI_Metrics**: A set of computed values displayed on the Outcome_Receipt including elapsed time, equivalent human negotiation time, and a value summary.
- **Initialize_Button**: The primary CTA on the Control_Panel labeled "Initialize A2A Protocol" that triggers `POST /api/v1/negotiation/start` and deducts tokens.

## Requirements

### Requirement 1: Scenario Selector Dropdown

**User Story:** As an investor, I want to select a simulation scenario from a dropdown, so that I can choose which negotiation to observe.

#### Acceptance Criteria

1. WHEN the Control_Panel loads, THE Scenario_Selector SHALL fetch the list of available scenarios from `GET /api/v1/scenarios` and populate the dropdown with each scenario's `name` field.
2. THE Scenario_Selector SHALL display a placeholder option "Select Simulation Environment" when no scenario is selected.
3. WHEN the user selects a scenario from the dropdown, THE Control_Panel SHALL fetch the full scenario details from `GET /api/v1/scenarios/{scenario_id}` and render the Agent_Cards and Information_Toggles for the selected scenario.
4. IF the scenarios API request fails, THEN THE Control_Panel SHALL display an error message indicating that scenarios could not be loaded.
5. WHILE the scenarios API request is in progress, THE Scenario_Selector SHALL display a loading state and disable interaction.

### Requirement 2: Agent Character Cards

**User Story:** As an investor, I want to see cards introducing the AI agents for the selected scenario, so that I understand who is negotiating and what drives them.

#### Acceptance Criteria

1. WHEN a scenario is selected, THE Control_Panel SHALL render exactly one Agent_Card for each agent defined in the scenario's `agents` array.
2. THE Agent_Card SHALL display the agent's `name`, `role`, a summary derived from the agent's `goals` array, and the `model_id` identifying the LLM powering the agent.
3. THE Agent_Card SHALL use distinct visual styling (color or icon) to differentiate agent roles.
4. WHEN no scenario is selected, THE Control_Panel SHALL not render any Agent_Cards.

### Requirement 3: Information Toggle Checkboxes

**User Story:** As an investor, I want checkboxes to inject hidden context into agents before the simulation, so that I can observe how information asymmetry changes negotiation outcomes.

#### Acceptance Criteria

1. WHEN a scenario is selected, THE Control_Panel SHALL render one Information_Toggle checkbox for each toggle defined in the scenario's `toggles` array.
2. THE Information_Toggle SHALL display the toggle's `label` text as the checkbox label.
3. THE Information_Toggle SHALL default to an unchecked state when the scenario is first loaded.
4. WHEN the user checks or unchecks an Information_Toggle, THE Control_Panel SHALL update the local list of `active_toggles` to include or exclude the toggle's `id`.
5. WHEN a different scenario is selected, THE Control_Panel SHALL reset all Information_Toggles to unchecked and clear the `active_toggles` list.

### Requirement 4: Initialize A2A Protocol Button

**User Story:** As an investor, I want to click a button to start the negotiation simulation, so that the AI agents begin their autonomous negotiation.

#### Acceptance Criteria

1. THE Control_Panel SHALL render the Initialize_Button with the label "Initialize A2A Protocol".
2. WHEN no scenario is selected, THE Initialize_Button SHALL be disabled.
3. WHEN the user clicks the Initialize_Button, THE Control_Panel SHALL send a `POST /api/v1/negotiation/start` request with the authenticated `email`, the selected `scenario_id`, and the current `active_toggles` array in the request body. The backend is the single source of truth for token deduction — the frontend SHALL NOT deduct tokens before the API call.
4. WHEN the `POST /api/v1/negotiation/start` request succeeds and returns a `session_id` and updated `tokens_remaining`, THE Control_Panel SHALL update the client-side Token_Balance to the `tokens_remaining` value from the response and navigate the user to the Glass_Box page at `/arena/session/{session_id}`.
5. IF the user's client-side Token_Balance appears insufficient for the simulation cost, THEN THE Control_Panel SHALL disable the Initialize_Button and display a message indicating insufficient tokens and the daily reset time. This is an optimistic UI check only; the backend enforces the actual limit.
6. IF the `POST /api/v1/negotiation/start` request returns HTTP 429 (token limit reached), THEN THE Control_Panel SHALL display a message indicating insufficient tokens and the daily reset time, and sync the client-side Token_Balance to `0`.
7. IF the `POST /api/v1/negotiation/start` request fails with any other error, THEN THE Control_Panel SHALL display an error message from the response body. No token refund is needed because no client-side deduction occurred.
8. WHILE the start request is in progress, THE Initialize_Button SHALL display a loading state and prevent duplicate submissions.

### Requirement 5: SSE Stream Client

**User Story:** As a developer, I want a client-side SSE module that connects to the backend stream and parses events, so that the Glass Box UI receives real-time negotiation data.

#### Acceptance Criteria

1. WHEN the Glass_Box page mounts with a valid `session_id`, THE SSE_Client SHALL open a connection to `GET /api/v1/negotiation/stream/{session_id}`.
2. THE SSE_Client SHALL parse each incoming SSE message's `data` field as JSON and classify the event by its `event_type` field into `agent_thought`, `agent_message`, `negotiation_complete`, or `error`.
3. WHEN an `agent_thought` event is received, THE SSE_Client SHALL dispatch the event containing `agent_name`, `inner_thought`, and `turn_number` to the Terminal_Panel.
4. WHEN an `agent_message` event is received, THE SSE_Client SHALL dispatch the event containing `agent_name`, `public_message`, `turn_number`, and optional `proposed_price`, `retention_clause_demanded`, and `status` fields to the Chat_Panel and Metrics_Dashboard.
5. WHEN a `negotiation_complete` event is received, THE SSE_Client SHALL dispatch the event containing `deal_status` and `final_summary` and trigger the Outcome_Receipt view.
6. WHEN an `error` event is received, THE SSE_Client SHALL display the error `message` to the user and close the connection.
7. WHEN the Glass_Box page unmounts, THE SSE_Client SHALL close the SSE connection to prevent resource leaks.
8. IF the SSE connection drops unexpectedly, THEN THE SSE_Client SHALL attempt to reconnect once after a 2-second delay before displaying a connection error to the user.

### Requirement 6: Terminal Panel — Inner Thoughts Display

**User Story:** As an investor, I want to see the AI agents' private reasoning in a terminal-style panel, so that I can observe the "machine thinking" in real time.

#### Acceptance Criteria

1. THE Terminal_Panel SHALL occupy the left column of the Glass_Box layout.
2. THE Terminal_Panel SHALL use a dark background with monospace font and green or white text to create a terminal aesthetic.
3. WHEN an `agent_thought` event is received, THE Terminal_Panel SHALL append a new entry displaying the `agent_name` as a label prefix and the `inner_thought` text.
4. THE Terminal_Panel SHALL auto-scroll to the latest entry as new thoughts arrive.
5. THE Terminal_Panel SHALL display a blinking cursor or typing animation while waiting for the next thought event, indicating the system is actively processing.
6. WHEN the negotiation has not yet started streaming, THE Terminal_Panel SHALL display a placeholder message such as "Awaiting agent initialization...".

### Requirement 7: Chat Panel — Public Messages Display

**User Story:** As an investor, I want to see the official messages exchanged between agents in a clean chat interface, so that I can follow the public negotiation dialogue.

#### Acceptance Criteria

1. THE Chat_Panel SHALL occupy the center column of the Glass_Box layout.
2. THE Chat_Panel SHALL render each public message as a chat bubble with the `agent_name` displayed as the sender label.
3. WHEN an `agent_message` event is received, THE Chat_Panel SHALL append a new chat bubble containing the `public_message` text.
4. THE Chat_Panel SHALL assign each agent a unique color from an Agent_Color_Palette based on the agent's index in the scenario's `agents` array. All messages SHALL be left-aligned with the agent's name displayed in the agent's assigned color as a label above the bubble. The Chat_Panel SHALL NOT use left/right alignment to distinguish agents, as this pattern breaks with more than 2 agents.
5. THE Chat_Panel SHALL auto-scroll to the latest message as new messages arrive.
6. WHEN an `agent_message` event contains a `proposed_price` field, THE Chat_Panel SHALL display the proposed price as a highlighted value within or below the chat bubble.
7. WHEN an `agent_message` event contains a `status` field (from any agent with `type` `"regulator"`), THE Chat_Panel SHALL render the status as a distinct system-style message with appropriate color coding (green for CLEAR, yellow for WARNING, red for BLOCKED). If the scenario has multiple regulators, each regulator's status message SHALL include the regulator's `agent_name` to distinguish which regulator issued the status.

### Requirement 8: Metrics Dashboard — Live Indicators

**User Story:** As an investor, I want a live dashboard showing the current offer, regulator status, and token balance, so that I can track negotiation progress at a glance.

#### Acceptance Criteria

1. THE Metrics_Dashboard SHALL be positioned at the top of the Glass_Box layout, spanning the full width.
2. THE Metrics_Dashboard SHALL display the Current_Offer value, updating dynamically when an `agent_message` event contains a `proposed_price` field.
3. THE Metrics_Dashboard SHALL dynamically render one Regulator_Traffic_Light for each agent with `type` `"regulator"` defined in the active scenario's `agents` array. Each traffic light SHALL be labeled with the regulator agent's `name` and display as a colored circle or icon: green when the regulator's latest status is `"CLEAR"`, yellow when `"WARNING"`, and red when `"BLOCKED"`. If the scenario defines zero regulator agents, THE Metrics_Dashboard SHALL not render any traffic light indicators.
4. THE Metrics_Dashboard SHALL display the Turn_Counter formatted as "Turn: X / Y" where X is the current `turn_number` and Y is the `max_turns` from the session state.
5. THE Metrics_Dashboard SHALL display the Token_Balance_Display formatted as "Tokens: X / 100" reflecting the authenticated user's current Token_Balance.
6. WHEN the Current_Offer value changes, THE Metrics_Dashboard SHALL apply a brief visual transition or animation to draw attention to the updated value.
7. WHEN the Regulator_Traffic_Light transitions from green to yellow or yellow to red, THE Metrics_Dashboard SHALL apply a brief pulse or flash animation to the indicator.

### Requirement 9: Glass Box Responsive Layout

**User Story:** As a user, I want the Glass Box simulation view to render correctly across screen sizes, so that I can observe the simulation on different devices.

#### Acceptance Criteria

1. THE Glass_Box SHALL use a three-region layout: Metrics_Dashboard (top), Terminal_Panel (left), and Chat_Panel (center).
2. WHEN the viewport width is 1024px or greater, THE Glass_Box SHALL render the Terminal_Panel and Chat_Panel side by side below the Metrics_Dashboard.
3. WHEN the viewport width is less than 1024px, THE Glass_Box SHALL stack the Terminal_Panel above the Chat_Panel in a single-column layout.
4. THE Glass_Box SHALL use Tailwind CSS utility classes for all layout and responsive behavior.
5. THE Terminal_Panel and Chat_Panel SHALL each occupy a scrollable container with a fixed maximum height relative to the viewport, preventing the page from growing unbounded.

### Requirement 10: Outcome Receipt — Deal Summary

**User Story:** As an investor, I want to see a summary dashboard when the negotiation ends, so that I can review the final terms and understand the value of the A2A protocol.

#### Acceptance Criteria

1. WHEN a `negotiation_complete` event is received with `deal_status` of `"Agreed"`, THE Outcome_Receipt SHALL display the final negotiated terms from the `final_summary` object.
2. WHEN a `negotiation_complete` event is received with `deal_status` of `"Blocked"`, THE Outcome_Receipt SHALL display the reason the deal was blocked, sourced from the `final_summary`.
3. WHEN a `negotiation_complete` event is received with `deal_status` of `"Failed"`, THE Outcome_Receipt SHALL display a failure summary indicating the negotiation reached the maximum turn limit without agreement.
4. THE Outcome_Receipt SHALL display ROI_Metrics in two distinct visual groups: (a) measured metrics — elapsed simulation time computed client-side from session start to the `negotiation_complete` event timestamp; and (b) scenario-estimated metrics — "Equivalent Human Time" and "Value Created" values sourced from the scenario JSON's `outcome_receipt` config. The scenario-estimated metrics SHALL be visually labeled with a subtitle such as "Industry Estimate" or rendered with a distinct style (e.g., lighter text, italic, or an info tooltip) to make it clear to investors that these are reference benchmarks, not computed values.
5. THE Outcome_Receipt SHALL render a "Run Another Scenario" button that navigates the user back to the Control_Panel at `/arena`.
6. THE Outcome_Receipt SHALL render a "Reset with Different Variables" button that navigates the user back to the Control_Panel with the same scenario pre-selected.
7. THE Outcome_Receipt SHALL visually replace or overlay the Glass_Box content with a fade or slide transition.

### Requirement 11: Error Handling and Edge Cases

**User Story:** As a user, I want the simulation UI to handle errors gracefully, so that I am informed of issues without the application crashing.

#### Acceptance Criteria

1. IF the Glass_Box page is loaded with an invalid or non-existent `session_id`, THEN THE Glass_Box SHALL display an error message and provide a link back to the Control_Panel.
2. IF the SSE stream yields an `error` event, THEN THE Glass_Box SHALL display the error message in a visible notification area and stop rendering new events.
3. IF the SSE connection cannot be established after the initial attempt and one retry, THEN THE Glass_Box SHALL display a connection failure message with a "Return to Arena" link.
4. WHEN the user navigates away from the Glass_Box while a simulation is in progress, THE SSE_Client SHALL close the connection cleanly.
5. IF the `POST /api/v1/negotiation/start` request returns an HTTP 4xx or 5xx error, THEN THE Control_Panel SHALL display the error detail from the response body to the user.
