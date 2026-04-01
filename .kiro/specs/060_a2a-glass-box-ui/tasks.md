# Implementation Plan: Glass Box Simulation UI

## Overview

Implement the real-time simulation UI for the JuntoAI A2A MVP on top of the existing Next.js scaffold from spec 050. This covers the Arena Control Panel (`/arena`), Glass Box live simulation view (`/arena/session/{session_id}`), SSE client module, Glass Box reducer, and Outcome Receipt overlay. All code is TypeScript with Tailwind CSS styling.

## Tasks

- [ ] 1. Define SSE event types and API client
  - [ ] 1.1 Create SSE event type definitions (`types/sse.ts`)
    - Define `AgentThoughtEvent`, `AgentMessageEvent`, `NegotiationCompleteEvent`, `SSEErrorEvent`, and the `SSEEvent` union type
    - Include all fields per design: `event_type`, `agent_name`, `inner_thought`, `turn_number`, `public_message`, `proposed_price`, `retention_clause_demanded`, `status`, `deal_status`, `final_summary`, `session_id`, `message`
    - _Requirements: 5.2, 5.3, 5.4, 5.5, 5.6_

  - [ ] 1.2 Create API client module (`lib/api.ts`)
    - Define `ScenarioSummary`, `ArenaScenario`, `StartNegotiationResponse` interfaces
    - Implement `fetchScenarios()` calling `GET /api/v1/scenarios`
    - Implement `fetchScenarioDetail(scenarioId)` calling `GET /api/v1/scenarios/{id}`
    - Implement `startNegotiation(email, scenarioId, activeToggles)` calling `POST /api/v1/negotiation/start`
    - `startNegotiation` must check for HTTP 429 and throw a typed `TokenLimitError`
    - All functions throw on non-2xx with error detail from response body
    - Use `NEXT_PUBLIC_API_URL` env var with `http://localhost:8000/api/v1` fallback
    - _Requirements: 1.1, 1.3, 4.3, 4.4, 4.6, 4.7, 11.5_

  - [ ]* 1.3 Write unit tests for API client (`__tests__/lib/api.test.ts`)
    - Test `fetchScenarios` returns parsed scenario list on 200
    - Test `fetchScenarios` throws on network error
    - Test `fetchScenarioDetail` returns full scenario on 200
    - Test `startNegotiation` returns session_id and tokens_remaining on 200
    - Test `startNegotiation` throws `TokenLimitError` on HTTP 429
    - Test `startNegotiation` throws with error detail on other 4xx/5xx
    - _Requirements: 1.1, 1.4, 4.3, 4.6, 4.7, 11.5_

  - [ ]* 1.4 Write property test for SSE event JSON parsing
    - **Property 2: SSE event JSON parsing correctness**
    - **Validates: Requirements 5.2, 5.3, 5.4, 5.5, 5.6**

  - [ ]* 1.5 Write property test for API error display on negotiation start failure
    - **Property 13: API error display on negotiation start failure**
    - **Validates: Requirements 4.7, 11.5**

- [ ] 2. Implement Glass Box reducer
  - [ ] 2.1 Create Glass Box reducer and state types (`lib/glassBoxReducer.ts`)
    - Define `ThoughtEntry`, `MessageEntry`, `GlassBoxState`, `GlassBoxAction` types
    - Implement `createInitialState(maxTurns)` returning initial state with empty arrays, `currentOffer: 0`, `regulatorStatus: "CLEAR"`, `turnNumber: 0`, `dealStatus: "Negotiating"`, `isConnected: false`
    - Implement `glassBoxReducer(state, action)` as a pure function handling: `AGENT_THOUGHT` (append thought, update turnNumber), `AGENT_MESSAGE` (append message, update turnNumber/currentOffer/regulatorStatus), `NEGOTIATION_COMPLETE` (set dealStatus/finalSummary, isConnected=false), `SSE_ERROR` (set error, isConnected=false), `CONNECTION_OPENED` (isConnected=true, clear error), `CONNECTION_ERROR` (set error, isConnected=false)
    - _Requirements: 5.3, 5.4, 5.5, 5.6, 6.3, 7.3, 8.2, 8.3, 8.4, 11.2_

  - [ ]* 2.2 Write property test for reducer state invariants
    - **Property 1: Reducer state invariant under event sequences**
    - Generate random sequences of `GlassBoxAction` objects, apply through reducer, verify: thoughts.length matches AGENT_THOUGHT count, messages.length matches AGENT_MESSAGE count, currentOffer matches last proposed_price, regulatorStatus matches last status, turnNumber is max across events, dealStatus matches NEGOTIATION_COMPLETE if dispatched
    - **Validates: Requirements 5.3, 5.4, 5.5, 5.6, 6.3, 7.3, 8.2, 8.3, 8.4, 11.2**

  - [ ]* 2.3 Write unit tests for Glass Box reducer (`__tests__/lib/glassBoxReducer.test.ts`)
    - Test `createInitialState` returns correct defaults
    - Test `AGENT_THOUGHT` appends to thoughts array
    - Test `AGENT_MESSAGE` appends to messages and updates currentOffer when proposed_price present
    - Test `AGENT_MESSAGE` updates regulatorStatus when status present
    - Test `NEGOTIATION_COMPLETE` sets dealStatus and finalSummary, isConnected=false
    - Test `SSE_ERROR` sets error and isConnected=false
    - Test `CONNECTION_OPENED` sets isConnected=true and clears error
    - Test turnNumber tracks max across thought and message events
    - _Requirements: 5.3, 5.4, 5.5, 5.6, 6.3, 8.2, 8.3, 11.2_

- [ ] 3. Implement SSE client hook
  - [ ] 3.1 Create useSSE hook (`hooks/useSSE.ts`)
    - Accept `sessionId`, `email`, `maxTurns`, `dispatch` parameters
    - On mount (when sessionId non-null): open `EventSource` to `GET /api/v1/negotiation/stream/{sessionId}?email={email}`
    - Parse `message.data` as JSON, switch on `event_type`, dispatch corresponding `GlassBoxAction`
    - On `EventSource.onopen`: dispatch `CONNECTION_OPENED`, capture `startTime = Date.now()`
    - On `EventSource.onerror`: attempt one reconnect after 2-second delay; if retry fails, dispatch `CONNECTION_ERROR`
    - On unmount: call `eventSource.close()` for cleanup
    - Skip malformed JSON events (log to console, continue)
    - Return `{ isConnected, startTime }`
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8, 11.2, 11.3, 11.4_

  - [ ]* 3.2 Write unit tests for useSSE hook (`__tests__/hooks/useSSE.test.ts`)
    - Mock `EventSource` constructor
    - Test connection opens with correct URL including sessionId and email
    - Test `agent_thought` event dispatches `AGENT_THOUGHT` action
    - Test `agent_message` event dispatches `AGENT_MESSAGE` action
    - Test `negotiation_complete` event dispatches `NEGOTIATION_COMPLETE` action
    - Test `error` event dispatches `SSE_ERROR` action
    - Test connection cleanup on unmount calls `eventSource.close()`
    - Test reconnect attempt after 2-second delay on error
    - Test malformed JSON is skipped without crashing
    - _Requirements: 5.1, 5.2, 5.7, 5.8, 11.4_

- [ ] 4. Checkpoint — Core logic complete
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 5. Implement Arena Control Panel components
  - [ ] 5.1 Create ScenarioSelector component (`components/arena/ScenarioSelector.tsx`)
    - Render `<select>` dropdown with placeholder "Select Simulation Environment"
    - Populate options from `scenarios` prop using each scenario's `name`
    - Disable during loading state
    - Show error message if fetch failed
    - Call `onSelect(scenarioId)` on change
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

  - [ ] 5.2 Create AgentCard component (`components/arena/AgentCard.tsx`)
    - Display agent `name`, `role` badge, `goals` list, and `modelId`
    - Use `index` prop to pick from predefined color palette for role differentiation
    - _Requirements: 2.1, 2.2, 2.3_

  - [ ] 5.3 Create InformationToggle component (`components/arena/InformationToggle.tsx`)
    - Render labeled checkbox with toggle `id` and `label`
    - Call `onChange(id, checked)` on state change
    - _Requirements: 3.1, 3.2, 3.4_

  - [ ] 5.4 Create InitializeButton component (`components/arena/InitializeButton.tsx`)
    - Render "Initialize A2A Protocol" label
    - Show spinner when `isLoading` is true
    - Show "Insufficient tokens — resets at midnight UTC" when `insufficientTokens` is true
    - Disabled when `disabled || isLoading || insufficientTokens`
    - _Requirements: 4.1, 4.2, 4.5, 4.8_

  - [ ]* 5.5 Write unit tests for Arena Control Panel components
    - Test ScenarioSelector renders placeholder, loading state, error state, and options
    - Test AgentCard renders name, role, goals, modelId with distinct colors per index
    - Test InformationToggle renders label and fires onChange
    - Test InitializeButton renders label, disabled states, loading spinner, insufficient tokens message
    - _Requirements: 1.2, 1.4, 1.5, 2.2, 2.3, 3.2, 4.1, 4.2, 4.5, 4.8_

  - [ ]* 5.6 Write property test for scenario selection component counts
    - **Property 3: Scenario selection renders correct component counts**
    - **Validates: Requirements 1.3, 2.1, 3.1**

  - [ ]* 5.7 Write property test for Agent Card field display
    - **Property 4: Agent Card displays all required fields**
    - **Validates: Requirements 2.2**

  - [ ]* 5.8 Write property test for toggle state management and reset
    - **Property 5: Toggle state management and reset**
    - **Validates: Requirements 3.3, 3.4, 3.5**

  - [ ]* 5.9 Write property test for insufficient tokens disabling Initialize button
    - **Property 6: Insufficient tokens disables Initialize button**
    - **Validates: Requirements 4.5**

- [ ] 6. Implement Control Panel page
  - [ ] 6.1 Create Control Panel page (`app/(protected)/arena/page.tsx`)
    - Client component with state: `scenarios`, `selectedScenarioId`, `scenarioDetail`, `activeToggles`, loading/error states
    - On mount: fetch scenarios list via `fetchScenarios()`. On error, show inline error message
    - On scenario select: fetch detail via `fetchScenarioDetail()`, render AgentCards and InformationToggles, reset toggles
    - On Initialize click: call `startNegotiation(email, scenarioId, activeToggles)`. On success, update token balance via SessionContext, navigate to `/arena/session/{session_id}?max_turns={max_turns}`
    - Handle HTTP 429: show token limit message, sync token balance to 0
    - Handle other errors: show error detail from response body
    - If URL has `?scenario={id}` query param, pre-select that scenario on mount
    - Disable Initialize button when no scenario selected or insufficient tokens
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.1, 2.4, 3.1, 3.3, 3.5, 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 11.5_

  - [ ]* 6.2 Write unit tests for Control Panel page (`__tests__/pages/arena.test.tsx`)
    - Test scenarios fetched and rendered on mount
    - Test scenario selection fetches detail and renders agent cards + toggles
    - Test toggles reset on scenario switch
    - Test Initialize button calls startNegotiation with correct payload
    - Test HTTP 429 shows token limit message and syncs balance to 0
    - Test other API errors display error detail
    - Test pre-selection from URL query param
    - Test Initialize button disabled when no scenario selected
    - _Requirements: 1.1, 1.3, 3.5, 4.3, 4.6, 4.7, 10.6_

  - [ ]* 6.3 Write property test for start negotiation request payload
    - **Property 7: Start negotiation request contains correct payload**
    - **Validates: Requirements 4.3**

- [ ] 7. Checkpoint — Control Panel complete
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 8. Implement Glass Box simulation components
  - [ ] 8.1 Create TerminalPanel component (`components/glassbox/TerminalPanel.tsx`)
    - Dark background (`#1C1C1E`), monospace font (`font-mono`), green/white text
    - Each entry: `[AgentName]` prefix in green, thought text in white
    - Auto-scroll to bottom via `useRef` + `scrollIntoView` on `thoughts` change
    - Show blinking cursor (`animate-pulse`) when `isConnected && dealStatus === "Negotiating"`
    - Show "Awaiting agent initialization..." when thoughts is empty and connected
    - Scrollable container with `max-h-[60vh] overflow-y-auto`
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 9.5_

  - [ ] 8.2 Create ChatPanel component (`components/glassbox/ChatPanel.tsx`)
    - Chat bubbles with agent name as sender label
    - Each agent assigned a unique color from Agent_Color_Palette by index. All messages left-aligned with colored agent name label. No left/right alignment (breaks with N agents).
    - If `proposedPrice` present, render as highlighted badge below message text
    - If `regulatorStatus` present, render as system message with color coding: green for CLEAR, yellow for WARNING, red for BLOCKED
    - Auto-scroll to bottom on new messages
    - Scrollable container with `max-h-[60vh] overflow-y-auto`
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 9.5_

  - [ ] 8.3 Create MetricsDashboard component (`components/glassbox/MetricsDashboard.tsx`)
    - Full-width top bar with four metric cards
    - Current Offer: formatted as currency with `transition-all` animation on value change
    - Regulator Traffic Lights: one per regulator agent in scenario, each labeled with regulator name. Colored circle (`bg-green-500` / `bg-yellow-500` / `bg-red-500`) with pulse animation. Zero regulators = no traffic lights. Flexbox wrapping layout.
    - Turn Counter: "Turn: X / Y"
    - Token Balance: "Tokens: X / 100"
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7_

  - [ ]* 8.4 Write unit tests for Glass Box simulation components
    - Test TerminalPanel renders thoughts with agent name prefix, auto-scroll, blinking cursor, placeholder message
    - Test ChatPanel renders messages with correct alignment/colors per agent, proposed price badge, regulator status colors
    - Test MetricsDashboard renders all four metrics with correct formatting and color classes
    - _Requirements: 6.2, 6.3, 6.4, 6.5, 6.6, 7.2, 7.3, 7.4, 7.6, 7.7, 8.2, 8.3, 8.4, 8.5_

  - [ ]* 8.5 Write property test for agent visual differentiation
    - **Property 10: Agent visual differentiation**
    - **Validates: Requirements 2.3, 7.4**

  - [ ]* 8.6 Write property test for regulator status to color mapping
    - **Property 11: Regulator status to color mapping**
    - **Validates: Requirements 7.7, 8.3**

  - [ ]* 8.7 Write property test for proposed price rendering in Chat Panel
    - **Property 12: Proposed price rendering in Chat Panel**
    - **Validates: Requirements 7.6**

- [ ] 9. Implement Outcome Receipt component
  - [ ] 9.1 Create OutcomeReceipt component (`components/glassbox/OutcomeReceipt.tsx`)
    - Render based on `dealStatus`: Agreed (final terms, success styling), Blocked (block reason, warning styling), Failed (max turns message, neutral styling)
    - ROI Metrics in two groups: measured (elapsed time in seconds) and scenario-estimated ("Equivalent Human Time" + process label with "Industry Estimate" label, lighter text/italic)
    - "Run Another Scenario" button → navigates to `/arena`
    - "Reset with Different Variables" button → navigates to `/arena?scenario={scenarioId}`
    - Fade-in transition via Tailwind `animate-fadeIn` or CSS transition
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7_

  - [ ]* 9.2 Write unit tests for OutcomeReceipt (`__tests__/components/glassbox/OutcomeReceipt.test.tsx`)
    - Test Agreed status renders final terms with success styling
    - Test Blocked status renders block reason with warning styling
    - Test Failed status renders max turns failure message
    - Test ROI metrics display both measured and estimated groups
    - Test "Run Another Scenario" navigates to `/arena`
    - Test "Reset with Different Variables" navigates to `/arena?scenario={id}`
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6_

  - [ ]* 9.3 Write property test for Outcome Receipt content per deal status
    - **Property 8: Outcome Receipt renders appropriate content per deal status**
    - **Validates: Requirements 10.1, 10.2, 10.3**

  - [ ]* 9.4 Write property test for Outcome Receipt metric groups
    - **Property 9: Outcome Receipt displays both metric groups**
    - **Validates: Requirements 10.4**

- [ ] 10. Implement Glass Box page and wire everything together
  - [ ] 10.1 Create Glass Box page (`app/(protected)/arena/session/[sessionId]/page.tsx`)
    - Client component reading `sessionId` from route params, `max_turns` from search params, `email` and `tokenBalance` from SessionContext
    - Initialize `useReducer(glassBoxReducer, createInitialState(maxTurns))`
    - Pass `dispatch` to `useSSE` hook
    - Three-region layout: MetricsDashboard (top), TerminalPanel (left), ChatPanel (center)
    - Responsive: `lg:` flex-row for Terminal + Chat side by side (>= 1024px), flex-col stacked (< 1024px)
    - Both panels: `max-h-[60vh] overflow-y-auto`
    - When `dealStatus` is terminal ("Agreed" | "Blocked" | "Failed"): render OutcomeReceipt overlay with computed elapsed time
    - If `sessionId` missing or invalid: show error with "Return to Arena" link, do not open SSE
    - If SSE error: show error with "Return to Arena" link
    - _Requirements: 5.1, 6.1, 7.1, 8.1, 9.1, 9.2, 9.3, 9.4, 9.5, 10.7, 11.1, 11.2, 11.3_

  - [ ]* 10.2 Write unit tests for Glass Box page (`__tests__/pages/glassbox.test.tsx`)
    - Test page renders MetricsDashboard, TerminalPanel, ChatPanel
    - Test SSE connection opens with correct sessionId
    - Test OutcomeReceipt overlay renders when dealStatus is terminal
    - Test invalid sessionId shows error with "Return to Arena" link
    - Test responsive layout classes present (lg:flex-row, flex-col)
    - _Requirements: 5.1, 9.2, 9.3, 10.7, 11.1_

- [ ] 11. Add Tailwind animation config for Outcome Receipt fade-in
  - Extend `tailwind.config.ts` with `animate-fadeIn` keyframe if not already present
  - _Requirements: 10.7_

- [ ] 12. Final checkpoint — All components wired and tests passing
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- This spec builds on the existing Next.js scaffold, SessionContext, TokenDisplay, access gate, and middleware from spec 050
- All components use Tailwind CSS utility classes per the styling guide
- The Glass Box reducer is a pure function — the most critical testable unit
- Property tests use `fast-check` with minimum 100 iterations each
- SSE uses native `EventSource` API — no polyfill needed
