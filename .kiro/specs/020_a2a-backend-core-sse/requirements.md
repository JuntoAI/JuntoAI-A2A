# Requirements Document

## Introduction

This specification covers the foundational Python FastAPI backend and the Server-Sent Events (SSE) streaming infrastructure for the JuntoAI A2A MVP. It includes the FastAPI application scaffold with Pydantic validation, a health check endpoint, the Firestore database client for session state management, and the core SSE streaming endpoint that will broadcast AI agent inner thoughts and public messages in real time. The GCP infrastructure (Cloud Run, Firestore provisioning, IAM) is covered in the separate `a2a-gcp-infrastructure` spec.

## Glossary

- **Backend**: The Python 3.11+ FastAPI application that orchestrates the A2A negotiation protocol.
- **Health_Endpoint**: The `GET /api/v1/health` API route used for liveness and readiness probes.
- **Firestore_Client**: The application-level client module that wraps the Google Cloud Firestore SDK to read and write negotiation session documents.
- **Session_Document**: A Firestore document keyed by `session_id` that stores the full `NegotiationState` for a single negotiation run.
- **NegotiationState**: A Pydantic model representing the complete state of a negotiation session, including `session_id`, `turn_count`, `max_turns`, `current_speaker`, `deal_status`, `current_offer`, and `history`.
- **SSE_Stream_Endpoint**: The `GET /api/v1/negotiation/stream/{session_id}` API route that opens a Server-Sent Events connection and yields real-time JSON event chunks.
- **SSE_Event**: A single Server-Sent Events message yielded by the SSE_Stream_Endpoint, formatted as `data: <JSON>\n\n` per the SSE specification.
- **StreamingResponse**: The FastAPI/Starlette response class used to send a stream of SSE_Events to the client over a long-lived HTTP connection.
- **AgentThoughtEvent**: An SSE_Event with `event_type` of `agent_thought` containing an agent's `inner_thought` field.
- **AgentMessageEvent**: An SSE_Event with `event_type` of `agent_message` containing an agent's `public_message` and optional structured fields (`proposed_price`, `retention_clause_demanded`, `status`).
- **Pydantic_Model**: A Python class inheriting from `pydantic.BaseModel` used for request/response validation and serialization.

## Requirements

### Requirement 1: FastAPI Application Scaffold

**User Story:** As a developer, I want a well-structured FastAPI application with Pydantic validation configured, so that the backend has a solid foundation for all API endpoints.

#### Acceptance Criteria

1. THE Backend SHALL expose a FastAPI application instance configured with the title "JuntoAI A2A API" and a versioned API prefix of `/api/v1`.
2. THE Backend SHALL enable CORS middleware allowing configurable origins, so that the Next.js frontend can communicate with the API.
3. THE Backend SHALL use Pydantic V2 `BaseModel` classes for all request and response schema validation.
4. WHEN the Backend starts, THE Backend SHALL log the application version and environment name to standard output.

### Requirement 2: Health Check Endpoint

**User Story:** As a DevOps engineer, I want a health check endpoint, so that Cloud Run liveness and readiness probes can verify the backend is operational.

#### Acceptance Criteria

1. THE Health_Endpoint SHALL respond to `GET /api/v1/health` requests.
2. WHEN a health check request is received, THE Health_Endpoint SHALL return an HTTP 200 status code with a JSON body containing `status` set to `"ok"` and a `version` field.
3. WHEN a health check request is received, THE Health_Endpoint SHALL respond within 500 milliseconds under normal operating conditions.
4. THE Health_Endpoint SHALL validate its response against a Pydantic_Model named `HealthResponse`.

### Requirement 3: NegotiationState Pydantic Model

**User Story:** As a developer, I want a strongly-typed Pydantic model for negotiation state, so that session data is validated consistently across the backend.

#### Acceptance Criteria

1. THE NegotiationState Pydantic_Model SHALL contain a `session_id` field of type `str`.
2. THE NegotiationState Pydantic_Model SHALL contain a `turn_count` field of type `int` with a default value of `0`.
3. THE NegotiationState Pydantic_Model SHALL contain a `max_turns` field of type `int` with a default value of `15`.
4. THE NegotiationState Pydantic_Model SHALL contain a `current_speaker` field of type `str` with a default value of `"Buyer"`.
5. THE NegotiationState Pydantic_Model SHALL contain a `deal_status` field of type `str` with a default value of `"Negotiating"`, constrained to the values `"Negotiating"`, `"Agreed"`, `"Blocked"`, or `"Failed"`.
6. THE NegotiationState Pydantic_Model SHALL contain a `current_offer` field of type `float` with a default value of `0.0`.
7. THE NegotiationState Pydantic_Model SHALL contain a `history` field of type `List[Dict[str, Any]]` with a default value of an empty list.
8. FOR ALL valid NegotiationState instances, serializing to JSON then deserializing back SHALL produce an equivalent NegotiationState object (round-trip property).

### Requirement 4: Firestore Client for Session Management

**User Story:** As a developer, I want a Firestore client module for session management, so that negotiation state can be persisted and retrieved reliably.

#### Acceptance Criteria

1. THE Firestore_Client SHALL initialize a connection to the GCP Firestore database using the `google-cloud-firestore` SDK.
2. THE Firestore_Client SHALL store Session_Documents in a Firestore collection named `negotiation_sessions`.
3. WHEN a new NegotiationState is provided, THE Firestore_Client SHALL create a Session_Document keyed by the `session_id` field.
4. WHEN a valid `session_id` is provided, THE Firestore_Client SHALL retrieve the corresponding Session_Document and return it as a NegotiationState object.
5. WHEN an update to a NegotiationState is provided, THE Firestore_Client SHALL merge the updated fields into the existing Session_Document.
6. IF a `session_id` that does not exist in Firestore is requested, THEN THE Firestore_Client SHALL raise a `SessionNotFoundError` with the requested `session_id` in the error message.
7. IF the Firestore SDK connection fails, THEN THE Firestore_Client SHALL raise a `FirestoreConnectionError` with a descriptive message.
8. FOR ALL NegotiationState objects, writing to Firestore then reading back by `session_id` SHALL produce an equivalent NegotiationState object (round-trip property).

### Requirement 5: SSE Stream Endpoint

**User Story:** As a frontend developer, I want an SSE streaming endpoint, so that the Glass Box UI can receive real-time agent thoughts and messages as they are generated.

#### Acceptance Criteria

1. THE SSE_Stream_Endpoint SHALL respond to `GET /api/v1/negotiation/stream/{session_id}` requests.
2. WHEN a valid `session_id` is provided, THE SSE_Stream_Endpoint SHALL return a StreamingResponse with `Content-Type` set to `text/event-stream`.
3. THE SSE_Stream_Endpoint SHALL set the `Cache-Control` response header to `no-cache` and the `Connection` header to `keep-alive`.
4. WHEN an SSE_Event is yielded, THE SSE_Stream_Endpoint SHALL format the event as `data: <JSON>\n\n` conforming to the W3C Server-Sent Events specification.
5. WHEN an AgentThoughtEvent is yielded, THE SSE_Event JSON payload SHALL contain `event_type` set to `"agent_thought"`, `agent_name`, and `inner_thought` fields.
6. WHEN an AgentMessageEvent is yielded, THE SSE_Event JSON payload SHALL contain `event_type` set to `"agent_message"`, `agent_name`, `public_message`, and optional `proposed_price`, `retention_clause_demanded`, and `status` fields.
7. IF a `session_id` that does not exist is provided, THEN THE SSE_Stream_Endpoint SHALL return an HTTP 404 response with a JSON error body containing the `session_id`.
8. IF an unexpected error occurs during streaming, THEN THE SSE_Stream_Endpoint SHALL yield an SSE_Event with `event_type` set to `"error"` and a descriptive `message` field, then close the stream.
9. WHEN the negotiation reaches a terminal `deal_status` (`"Agreed"`, `"Blocked"`, or `"Failed"`), THE SSE_Stream_Endpoint SHALL yield a final SSE_Event with `event_type` set to `"negotiation_complete"` containing the final `deal_status`, then close the stream.

### Requirement 6: SSE Event Pydantic Models

**User Story:** As a developer, I want strongly-typed Pydantic models for all SSE event types, so that event payloads are validated and serialized consistently.

#### Acceptance Criteria

1. THE AgentThoughtEvent Pydantic_Model SHALL contain `event_type` (literal `"agent_thought"`), `agent_name` (str), `inner_thought` (str), and `turn_number` (int) fields.
2. THE AgentMessageEvent Pydantic_Model SHALL contain `event_type` (literal `"agent_message"`), `agent_name` (str), `public_message` (str), `turn_number` (int), and optional `proposed_price` (float), `retention_clause_demanded` (bool), and `status` (str) fields.
3. THE Backend SHALL define a `NegotiationCompleteEvent` Pydantic_Model containing `event_type` (literal `"negotiation_complete"`), `session_id` (str), `deal_status` (str), and `final_summary` (dict) fields.
4. THE Backend SHALL define a `StreamErrorEvent` Pydantic_Model containing `event_type` (literal `"error"`) and `message` (str) fields.
5. FOR ALL SSE event Pydantic_Models, serializing to JSON then deserializing back SHALL produce an equivalent event object (round-trip property).
