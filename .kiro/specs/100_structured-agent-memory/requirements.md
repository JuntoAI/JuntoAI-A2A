# Requirements Document

## Introduction

The current A2A negotiation engine uses stateless LLM calls per agent turn. Each turn, the full negotiation history is serialized into the prompt as plain text. Agents have no persistent memory — they reconstruct context from scratch every call. This causes quadratic token cost scaling, degraded strategic recall as history grows, and no structured recall capability (agents cannot efficiently answer "what did I offer last time?").

This feature introduces a structured agent memory system (Option 2 from the design options RFC) that maintains a typed, per-agent memory object updated after each turn. When enabled, the agent receives structured memory data plus a sliding window of the last 3 raw messages for conversational context, instead of the full history transcript. The feature is optional — toggled via an "Advanced Options" section in the Arena Selector UI — and fully backward compatible with the existing full-history approach when disabled.

## Glossary

- **Agent_Memory**: A Pydantic V2 model representing the structured, typed memory state for a single agent. Contains fields for offer history, concessions, open items, tactics, red lines, and compliance status.
- **Memory_Extractor**: The logic within `_update_state` in `agent_node.py` that parses a completed agent turn's output and updates the corresponding Agent_Memory fields deterministically.
- **Sliding_Window**: The last 3 raw history entries (messages) retained alongside structured memory to preserve conversational tone and immediate context.
- **Agent_Node**: The backend orchestrator function (`create_agent_node` in `agent_node.py`) that builds prompts and invokes the LLM for each agent turn.
- **NegotiationState**: The LangGraph TypedDict (`state.py`) representing the full runtime state of a negotiation session.
- **StartNegotiationRequest**: The Pydantic model for the POST `/api/v1/negotiation/start` request body.
- **Arena_Selector**: Screen 2 of the core user flow where users pick a scenario, view agent cards, toggle hidden variables, and initialize a negotiation.
- **Advanced_Options_Section**: A collapsible UI section on the Arena_Selector page that exposes optional feature toggles such as structured agent memory enablement.
- **Stall_Detector**: The module (`stall_detector.py`) that analyzes negotiation state to detect repetitive patterns and terminate stalled negotiations early.
- **NegotiationStateModel**: The Pydantic model (`models/negotiation.py`) used for Firestore persistence and API serialization of session state.

## Requirements

### Requirement 1: AgentMemory Pydantic Model

**User Story:** As a developer, I want a typed Pydantic V2 model for per-agent structured memory, so that memory fields are validated, serializable, and inspectable at runtime.

#### Acceptance Criteria

1. THE Agent_Memory model SHALL define the following typed fields: `my_offers` (list of floats), `their_offers` (list of floats), `concessions_made` (list of strings), `concessions_received` (list of strings), `open_items` (list of strings), `tactics_used` (list of strings), `red_lines_stated` (list of strings), `compliance_status` (dict of string to string), and `turn_count` (integer, default 0)
2. THE Agent_Memory model SHALL initialize all list fields to empty lists and `turn_count` to 0 by default
3. THE Agent_Memory model SHALL be defined in `backend/app/orchestrator/outputs.py` alongside the existing output models
4. FOR ALL valid Agent_Memory instances, serializing to dict via `model_dump()` then reconstructing via `AgentMemory(**data)` SHALL produce an equivalent object (round-trip property)

### Requirement 2: NegotiationState Memory Fields

**User Story:** As a developer, I want the LangGraph runtime state and the Firestore persistence model to carry structured memory data and the enablement flag, so that memory is available throughout the orchestration pipeline and persisted across requests.

#### Acceptance Criteria

1. THE NegotiationState TypedDict SHALL include a `structured_memory_enabled` field of type `bool`
2. THE NegotiationState TypedDict SHALL include an `agent_memories` field of type `dict[str, dict[str, Any]]` to store serialized Agent_Memory objects keyed by agent role
3. THE `create_initial_state` factory function SHALL initialize `structured_memory_enabled` from the value passed by the caller
4. WHEN `structured_memory_enabled` is True, THE `create_initial_state` function SHALL initialize `agent_memories` with an empty Agent_Memory dict for each agent role
5. WHEN `structured_memory_enabled` is False, THE `create_initial_state` function SHALL initialize `agent_memories` as an empty dict
6. THE NegotiationStateModel Pydantic model SHALL include `structured_memory_enabled` (bool, default False) and `agent_memories` (dict, default empty) fields for Firestore persistence

### Requirement 3: Frontend Advanced Options Toggle

**User Story:** As a user, I want an "Advanced Options" section on the Arena Selector page with a toggle for structured agent memory, so that I can opt into the memory system before starting a negotiation.

#### Acceptance Criteria

1. WHEN a scenario is selected and agent cards are displayed, THE Arena_Selector SHALL render a collapsible "Advanced Options" section below the Hidden Variables section
2. THE Advanced_Options_Section SHALL be collapsed by default, showing only the section header with an expand/collapse chevron icon
3. WHEN the user expands the Advanced_Options_Section, THE Arena_Selector SHALL display a labeled toggle switch for "Structured Agent Memory" with a brief description: "Agents maintain structured recall of offers, concessions, and tactics instead of replaying full history each turn"
4. THE structured memory toggle SHALL default to off (disabled)
5. WHEN the user selects a different scenario, THE Arena_Selector SHALL reset the structured memory toggle to off

### Requirement 4: Pass Memory Toggle to Backend

**User Story:** As a developer, I want the structured memory enablement flag transmitted from the frontend to the backend when a negotiation starts, so that the orchestrator knows whether to use structured memory.

#### Acceptance Criteria

1. WHEN the user clicks "Initialize A2A Protocol", THE Arena_Selector SHALL include a `structured_memory_enabled` boolean field in the StartNegotiationRequest payload
2. THE StartNegotiationRequest Pydantic model SHALL accept an optional `structured_memory_enabled` field of type `bool` with a default of `False`
3. WHEN the backend receives a StartNegotiationRequest with `structured_memory_enabled` set to True, THE negotiation router SHALL pass the value through to `create_initial_state`
4. WHEN the backend receives a StartNegotiationRequest without the `structured_memory_enabled` field, THE negotiation router SHALL default to `False` (full-history mode)

### Requirement 5: Prompt Building with Structured Memory

**User Story:** As a developer, I want the agent prompt builder to use structured memory plus a sliding window of recent messages instead of the full history, so that token costs are reduced and strategic recall is precise.

#### Acceptance Criteria

1. WHEN `structured_memory_enabled` is True in the negotiation state, THE Agent_Node `_build_prompt` function SHALL serialize the agent's Agent_Memory into the user message instead of the full history transcript
2. WHEN `structured_memory_enabled` is True, THE Agent_Node `_build_prompt` function SHALL include the last 3 entries from the history list as a sliding window for conversational context
3. WHEN the history contains fewer than 3 entries, THE Agent_Node `_build_prompt` function SHALL include all available history entries in the sliding window
4. THE structured memory section in the prompt SHALL be formatted with clear labels for each field (e.g., "Your previous offers:", "Concessions you made:", "Open items remaining:")
5. WHEN `structured_memory_enabled` is False, THE Agent_Node `_build_prompt` function SHALL build the prompt identically to the current behavior with full history (backward compatible, no change)
6. THE sliding window entries SHALL display the same format as current history entries (role and public message or reasoning)

### Requirement 6: Memory Extraction After Each Turn

**User Story:** As a developer, I want the agent's structured memory to be updated deterministically after each turn based on the parsed LLM output, so that memory stays accurate without extra LLM calls.

#### Acceptance Criteria

1. WHEN `structured_memory_enabled` is True and a negotiator agent completes a turn, THE Memory_Extractor SHALL append the agent's `proposed_price` to the `my_offers` field of that agent's Agent_Memory
2. WHEN `structured_memory_enabled` is True and a negotiator agent completes a turn, THE Memory_Extractor SHALL append the most recent opposing negotiator's `proposed_price` (from the last history entry by a different negotiator) to the `their_offers` field
3. WHEN `structured_memory_enabled` is True, THE Memory_Extractor SHALL increment the `turn_count` field of the agent's Agent_Memory by 1 after each turn
4. WHEN `structured_memory_enabled` is True, THE Memory_Extractor SHALL store the updated Agent_Memory (serialized via `model_dump()`) into `agent_memories[role]` in the state delta
5. WHEN `structured_memory_enabled` is False, THE `_update_state` function SHALL skip all memory extraction logic (no performance overhead)

### Requirement 7: Stall Detector Structured Memory Integration

**User Story:** As a developer, I want the stall detector to optionally use structured memory data for more accurate and efficient stall detection, so that stall analysis does not depend on re-parsing the full history when memory is available.

#### Acceptance Criteria

1. WHEN `structured_memory_enabled` is True in the state, THE Stall_Detector `detect_stall` function SHALL read price histories directly from `agent_memories` instead of extracting them from the full history
2. WHEN `structured_memory_enabled` is True, THE Stall_Detector price ping-pong check SHALL use the `my_offers` list from each agent's Agent_Memory
3. WHEN `structured_memory_enabled` is False, THE Stall_Detector SHALL use the existing history-parsing logic with no changes (backward compatible)
4. THE Stall_Detector SHALL produce identical stall detection results regardless of whether structured memory or full history parsing is used for the same negotiation data

### Requirement 8: Backward Compatibility

**User Story:** As a user running existing scenarios, I want the negotiation engine to behave identically when structured memory is disabled, so that no existing functionality is broken.

#### Acceptance Criteria

1. WHEN `structured_memory_enabled` is False, THE Agent_Node SHALL build prompts using the full history transcript exactly as the current implementation does
2. WHEN `structured_memory_enabled` is False, THE `_update_state` function SHALL produce state deltas identical to the current implementation
3. WHEN `structured_memory_enabled` is False, THE Stall_Detector SHALL execute the same detection logic as the current implementation
4. WHEN the `structured_memory_enabled` field is absent from the NegotiationState (e.g., sessions created before this feature), THE system SHALL treat the value as False
5. THE NegotiationStateModel SHALL accept documents from Firestore that do not contain `structured_memory_enabled` or `agent_memories` fields without validation errors

### Requirement 9: Memory Serialization Round-Trip

**User Story:** As a developer, I want Agent_Memory to serialize and deserialize cleanly through all state boundaries (LangGraph state, Firestore, API responses), so that memory data is never corrupted or lost in transit.

#### Acceptance Criteria

1. FOR ALL valid Agent_Memory instances, converting to dict via `model_dump()`, storing in `agent_memories`, and reconstructing via `AgentMemory(**data)` SHALL produce an equivalent object
2. FOR ALL valid NegotiationState dicts containing `agent_memories`, serializing to NegotiationStateModel and back SHALL preserve all Agent_Memory data without loss
3. THE Agent_Memory `model_dump()` output SHALL contain only JSON-serializable types (no custom objects, datetimes, or non-primitive types)
