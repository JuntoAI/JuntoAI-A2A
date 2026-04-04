# Requirements Document: Agent Registration & Validation

## Dependency

This spec depends on **Spec 200 (Agent Gateway API & Remote Agent Node)** being fully implemented. The registration system validates agents against the Agent Gateway HTTP contract defined in Spec 200. It also depends on **Spec 140 (User Profile Token Upgrade)** for user identity — agent registrations are tied to user profiles.

## Introduction

An agent registration and validation system that allows external developers to register their remote agents with the JuntoAI platform, validate that agents conform to the Agent Gateway HTTP contract, and discover registered agents when building scenarios. Registered agents are stored in Firestore (or SQLite in local mode) and exposed via API endpoints. The system performs live contract validation — sending a test Turn_Payload and verifying the Turn_Response matches the expected schema — so that only working agents appear in the registry. This is the discoverability layer that makes the Agent Gateway usable without manually editing scenario JSON files.

## Glossary

- **Agent_Registry**: The Firestore collection (or SQLite table in local mode) that stores registered remote agent metadata
- **Agent_Registration**: A record in the Agent_Registry containing the agent's endpoint URL, supported types, capabilities, owner email, and validation status
- **Contract_Validation**: The process of sending a synthetic Turn_Payload to a remote agent endpoint and verifying the Turn_Response conforms to the Agent Gateway HTTP contract (from Spec 200)
- **Agent_Card**: The public metadata about a registered agent — name, description, supported types, endpoint URL, last validated timestamp, and validation status
- **Validation_Probe**: A synthetic Turn_Payload sent during registration to verify the agent responds correctly for each declared agent type

## Requirements

### Requirement 1: Agent Registration API

**User Story:** As an external developer, I want to register my remote agent with JuntoAI, so that it can be discovered and used in scenarios.

#### Acceptance Criteria

1. THE system SHALL expose a `POST /api/v1/agents/register` endpoint that accepts: `email` (string, required), `name` (string, required, 3-100 chars), `description` (string, required, 10-500 chars), `endpoint` (string, required, valid HTTP/HTTPS URL), `supported_types` (array of strings, required, each one of "negotiator", "regulator", "observer", at least one required)
2. WHEN a registration request is received, THE system SHALL verify the user has an existing Profile_Document (from Spec 140). If no profile exists, return HTTP 403
3. WHEN a registration request is received with a valid profile, THE system SHALL perform Contract_Validation against the endpoint for each declared supported_type
4. IF Contract_Validation succeeds for all declared types, THE system SHALL store the Agent_Registration in the Agent_Registry and return HTTP 201 with the agent_id and validation results
5. IF Contract_Validation fails for any declared type, THE system SHALL return HTTP 422 with specific details about which type failed and what the expected vs actual response was
6. THE system SHALL enforce a maximum of 10 registered agents per user profile
7. THE system SHALL reject duplicate registrations for the same endpoint URL (regardless of owner). Return HTTP 409 if the endpoint is already registered

### Requirement 2: Contract Validation Process

**User Story:** As the platform, I want to verify that registered agents actually work before listing them, so that scenario authors don't waste time with broken agents.

#### Acceptance Criteria

1. FOR EACH declared supported_type, THE Contract_Validation SHALL construct a synthetic Turn_Payload with realistic test data: a 2-agent scenario, 3 history entries, turn_number=4, max_turns=12, current_offer=100000.0
2. THE Contract_Validation SHALL send the synthetic Turn_Payload as a `POST` request to the agent's endpoint with a 10-second timeout
3. THE Contract_Validation SHALL validate the Turn_Response against the appropriate Pydantic output model: `NegotiatorOutput` for "negotiator", `RegulatorOutput` for "regulator", `ObserverOutput` for "observer"
4. IF the endpoint returns HTTP 200 and the response body passes Pydantic validation, THE type validation SHALL be marked as "passed"
5. IF the endpoint returns a non-200 status, times out, returns invalid JSON, or fails Pydantic validation, THE type validation SHALL be marked as "failed" with a specific error message
6. THE Contract_Validation results SHALL be stored in the Agent_Registration record for each supported_type

### Requirement 3: Agent Registry Storage

**User Story:** As the platform, I want to persist agent registrations, so that they survive server restarts and can be queried by scenario authors.

#### Acceptance Criteria

1. IN cloud mode, THE Agent_Registry SHALL store registrations in a Firestore collection `agent_registry/{agent_id}` with fields: `agent_id`, `owner_email`, `name`, `description`, `endpoint`, `supported_types`, `validation_results` (per-type pass/fail), `validated_at` (UTC timestamp), `created_at`, `updated_at`, `status` (one of "active", "inactive", "validation_failed")
2. IN local mode, THE Agent_Registry SHALL store registrations in a SQLite table `agent_registry` in the same database (`data/juntoai.db`) with equivalent columns
3. THE system SHALL provide a factory function `get_agent_registry()` in `backend/app/db/__init__.py` following the same pattern as `get_profile_client()` and `get_session_store()`
4. THE Agent_Registration `status` SHALL be "active" only when all declared supported_types passed Contract_Validation. Otherwise it SHALL be "validation_failed"

### Requirement 4: Agent Discovery API

**User Story:** As a scenario author, I want to browse registered agents, so that I can include them in my custom scenarios.

#### Acceptance Criteria

1. THE system SHALL expose a `GET /api/v1/agents` endpoint that returns a list of all Agent_Cards with status "active"
2. THE system SHALL expose a `GET /api/v1/agents?type=negotiator` endpoint that filters agents by supported_type
3. THE system SHALL expose a `GET /api/v1/agents/{agent_id}` endpoint that returns the full Agent_Card for a specific agent
4. EACH Agent_Card in the response SHALL include: `agent_id`, `name`, `description`, `endpoint`, `supported_types`, `validated_at`, `owner_email`, `status`
5. THE discovery endpoints SHALL NOT require authentication — agent cards are public (same philosophy as Google A2A Agent Cards)

### Requirement 5: Agent Management API

**User Story:** As an external developer, I want to update and delete my registered agents, so that I can maintain my agent listings.

#### Acceptance Criteria

1. THE system SHALL expose a `PUT /api/v1/agents/{agent_id}` endpoint that accepts the same fields as registration (except email) and re-runs Contract_Validation
2. THE system SHALL expose a `DELETE /api/v1/agents/{agent_id}?email=` endpoint that removes the agent from the registry
3. THE system SHALL expose a `POST /api/v1/agents/{agent_id}/revalidate?email=` endpoint that re-runs Contract_Validation without changing any fields and updates `validated_at` and `validation_results`
4. ONLY the owner (matching email) SHALL be allowed to update, delete, or revalidate an agent. Return HTTP 403 for non-owners
5. THE system SHALL expose a `GET /api/v1/agents/mine?email=` endpoint that returns only agents owned by the specified email

### Requirement 6: Re-Validation on Scenario Start

**User Story:** As the platform, I want to verify registered agents are still working when a negotiation starts, so that stale registrations don't cause failures.

#### Acceptance Criteria

1. WHEN a negotiation starts with a scenario containing remote agents that reference registered agent endpoints, THE system SHALL check the `validated_at` timestamp
2. IF `validated_at` is older than 24 hours, THE system SHALL re-run Contract_Validation before starting the negotiation
3. IF re-validation fails, THE system SHALL return an error to the user indicating which agent failed and suggest the agent owner re-validate
4. IF `validated_at` is within 24 hours, THE system SHALL skip re-validation and proceed (the pre-negotiation health check from Spec 200 Requirement 8 still runs)

### Requirement 7: Integration with Scenario Builder (Spec 130)

**User Story:** As a user building a custom scenario, I want to browse and select registered agents from the builder, so that I can include external agents without knowing their endpoint URLs.

#### Acceptance Criteria

1. WHEN the Builder_Chatbot (from Spec 130) is collecting agent definitions, THE Builder_Chatbot SHALL offer the option to "use a registered agent" in addition to defining a new local agent
2. WHEN the user chooses to use a registered agent, THE Builder_Chatbot SHALL query the Agent Discovery API and present available agents filtered by the needed type
3. WHEN the user selects a registered agent, THE Builder_Chatbot SHALL populate the agent's `endpoint`, `name`, and `role` fields from the Agent_Card, while still allowing the user to customize persona_prompt, goals, and budget
4. THIS requirement is a future enhancement — it SHALL NOT block Spec 200 or the core registration functionality. It can be implemented as a follow-up after Spec 130 is complete
