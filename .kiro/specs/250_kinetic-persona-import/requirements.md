# Requirements Document

## External Dependency: Kinetic Identity API (NOT YET DEVELOPED)

This spec depends on the Kinetic Identity API documented at `docs/kinetic-identity-api.md`. The API is designed but NOT yet implemented. It runs on CareGraph's AWS infrastructure, separate from this GCP-based repo. This spec defines the A2A-side integration (account linking callback, envelope fetching, caching, persona mapping) so that implementation can proceed as soon as the Kinetic API is available. All Kinetic-facing code paths MUST degrade gracefully when the API is unreachable.

## Internal Dependencies

- **Spec 130 (AI Scenario Builder)**: This feature extends the Builder_Chatbot's agent definition flow with a new persona source. The builder's existing LinkedIn URL persona generation (Requirement 8 in Spec 130), SSE event format, session management, and health check pipeline remain unchanged.
- **Spec 140 (User Profile Token Upgrade)**: The Kinetic account linking state (`kinetic_user_id`) is stored on the user's Profile_Document in the `profiles` Firestore collection. The builder's token enforcement and profile gating from Spec 140 apply to all Kinetic import interactions.

## Introduction

A "negotiation rehearsal" feature that lets users import their real professional identity from CareGraph's Kinetic Identity API into the AI Scenario Builder (Spec 130). Instead of manually defining an agent persona or pasting a LinkedIn URL, users who have linked their Kinetic account can pull their Identity Envelope — archetype, communication style, verified skills, values, credibility index — and use it to seed an agent that represents themselves. The Builder_Chatbot auto-generates a persona_prompt from the envelope data, pre-fills tone and name, then asks the user for the negotiation-specific fields that are NOT in the envelope: goals and budget. The user then proceeds through the normal builder flow (other agents, toggles, params, health check) to complete a scenario seeded with their real professional DNA.

This is an optional enrichment in the builder flow. If the user has no linked Kinetic account, the existing LinkedIn URL and manual entry paths remain fully available. The Kinetic import path is additive — it does not replace or modify any existing builder functionality.

## Glossary

- **Kinetic_Identity_API**: The REST API on CareGraph's AWS service that returns a curated Identity Envelope for a linked user. Authenticated via service-level API key (`X-Api-Key` header) and gated by user consent established during account linking. Documented at `docs/kinetic-identity-api.md`. NOT YET IMPLEMENTED.
- **Identity_Envelope**: The versioned JSON payload returned by the Kinetic_Identity_API containing: archetype, professionalIdentity, skills (with verified war stories), communicationStyle, contentThemes, values, depthScore, and credibilityIndex. Schema defined in `docs/kinetic-identity-api.md`.
- **Kinetic_Account_Linker**: The backend subsystem that handles the A2A side of the explicit account linking flow: initiating the redirect to Kinetic's consent page, handling the callback with the one-time linking code, exchanging the code for a `kinetic_user_id` via the Kinetic_Identity_API, and storing the mapping on the user's Profile_Document.
- **Kinetic_Envelope_Cache**: The Firestore-backed cache that stores a user's Identity_Envelope with a 7-day TTL to avoid repeated cross-cloud API calls. Stored as a field on the Profile_Document.
- **Kinetic_Persona_Generator**: The subsystem within the Builder_Chatbot flow that maps Identity_Envelope fields to ArenaScenario AgentDefinition fields (persona_prompt, tone, name) using AI-generated text from the Builder_Chatbot's LLM.
- **Builder_Chatbot**: The AI assistant (Claude Opus 4.6 via Vertex AI) from Spec 130 that conducts the guided scenario-building conversation. Extended in this spec to recognize Kinetic import requests and generate personas from envelope data.
- **Builder_Modal**: The full-screen modal UI from Spec 130 containing the chatbot, JSON preview, and progress indicator.
- **Scenario_Builder_API**: The backend FastAPI endpoints from Spec 130 that manage builder chat sessions, stream AI responses, validate scenarios, and persist user-created scenarios. Extended in this spec with account linking and envelope fetching endpoints.
- **Profile_Document**: The Firestore document in the `profiles` collection (from Spec 140) keyed by user email. Extended in this spec with `kinetic_user_id` and `kinetic_envelope_cache` fields.
- **AgentDefinition**: The Pydantic V2 model (`backend/app/scenarios/models.py`) defining a single AI agent's configuration: role, name, type, persona_prompt, goals, budget, tone, output_fields, model_id, fallback_model_id.

## Requirements

### Requirement 1: Kinetic Account Linking — Initiation

**User Story:** As a user, I want to connect my Kinetic profile to my A2A account, so that I can import my professional identity into negotiation scenarios.

#### Acceptance Criteria

1. WHEN the user clicks "Connect Kinetic Profile" on the Profile_Page or in the Builder_Modal during agent definition, THE Kinetic_Account_Linker SHALL redirect the user's browser to the Kinetic linking page at `{KINETIC_BASE_URL}/v1/link?service=a2a&callback={A2A_CALLBACK_URL}`
2. THE Kinetic_Account_Linker SHALL use the A2A service callback URL configured via the `KINETIC_LINK_CALLBACK_URL` environment variable as the `callback` parameter
3. WHILE the Kinetic_Identity_API is unreachable or not yet deployed, THE Kinetic_Account_Linker SHALL display a message indicating that Kinetic integration is not yet available and offer the user the LinkedIn URL or manual entry alternatives

### Requirement 2: Kinetic Account Linking — Callback and Code Exchange

**User Story:** As a user, I want the linking process to complete automatically after I consent on Kinetic's site, so that I don't have to do any manual configuration.

#### Acceptance Criteria

1. WHEN the user is redirected back to A2A with a `code` query parameter after consenting on Kinetic's domain, THE Kinetic_Account_Linker SHALL exchange the one-time code by calling `POST {KINETIC_BASE_URL}/v1/identity/link` with the A2A service API key and the received code
2. WHEN the code exchange returns a valid `kinetic_user_id`, THE Kinetic_Account_Linker SHALL store the `kinetic_user_id` on the user's Profile_Document in the `profiles` Firestore collection
3. IF the code exchange fails due to an expired or invalid code, THEN THE Kinetic_Account_Linker SHALL display an error message and offer the user the option to retry the linking flow
4. IF the code exchange fails due to a network error or Kinetic_Identity_API unavailability, THEN THE Kinetic_Account_Linker SHALL display an error message indicating the service is temporarily unavailable and suggest retrying later
5. THE Kinetic_Account_Linker SHALL pass the A2A service API key via the `X-Api-Key` header on all requests to the Kinetic_Identity_API, using the value from the `KINETIC_API_KEY` environment variable stored in GCP Secret Manager

### Requirement 3: Kinetic Account Linking — Status Display

**User Story:** As a user, I want to see whether my Kinetic account is linked, so that I know if the import option is available to me.

#### Acceptance Criteria

1. WHEN the user's Profile_Document contains a non-null `kinetic_user_id`, THE Profile_Page SHALL display a "Kinetic Profile: Connected" status with the user's archetype name (from cached envelope if available) and a "Disconnect" option
2. WHEN the user's Profile_Document contains a null `kinetic_user_id`, THE Profile_Page SHALL display a "Connect Kinetic Profile" button
3. WHEN the user clicks "Disconnect" on the Profile_Page, THE Kinetic_Account_Linker SHALL call `DELETE {KINETIC_BASE_URL}/v1/identity/{kinetic_user_id}/consent` with the A2A service API key, then set `kinetic_user_id` to null and clear `kinetic_envelope_cache` on the Profile_Document

### Requirement 4: Identity Envelope Fetching and Caching

**User Story:** As a user, I want my Kinetic identity data to load quickly when I use it in the builder, so that the import flow feels responsive.

#### Acceptance Criteria

1. WHEN the Builder_Chatbot needs the user's Identity_Envelope and a cached envelope exists on the Profile_Document with an `envelope_cached_at` timestamp less than 7 days old, THE Kinetic_Envelope_Cache SHALL return the cached envelope without calling the Kinetic_Identity_API
2. WHEN the Builder_Chatbot needs the user's Identity_Envelope and no valid cache exists, THE Kinetic_Envelope_Cache SHALL fetch the envelope by calling `GET {KINETIC_BASE_URL}/v1/identity/{kinetic_user_id}` with the A2A service API key
3. WHEN the Kinetic_Identity_API returns a valid Identity_Envelope, THE Kinetic_Envelope_Cache SHALL store the envelope and the current timestamp as `kinetic_envelope_cache` and `envelope_cached_at` on the Profile_Document
4. IF the Kinetic_Identity_API returns HTTP 403 (consent revoked), THEN THE Kinetic_Envelope_Cache SHALL set `kinetic_user_id` to null, clear the cached envelope on the Profile_Document, and THE Builder_Chatbot SHALL inform the user that their Kinetic connection has been revoked and offer LinkedIn URL or manual entry alternatives
5. IF the Kinetic_Identity_API returns HTTP 404, HTTP 429, or a network error, THEN THE Kinetic_Envelope_Cache SHALL fall back to the cached envelope if one exists (regardless of TTL), or inform the user that the Kinetic service is temporarily unavailable and offer alternatives
6. THE Kinetic_Envelope_Cache SHALL provide a "Refresh Kinetic Profile" action in the Builder_Modal that forces a fresh fetch from the Kinetic_Identity_API, bypassing the cache TTL

### Requirement 5: Kinetic Persona Import Option in Builder Flow

**User Story:** As a user, I want to see the option to import from my Kinetic profile during agent definition in the builder, so that I can quickly create an agent that represents me.

#### Acceptance Criteria

1. WHILE the Builder_Chatbot is collecting agent definitions and the user's Profile_Document contains a non-null `kinetic_user_id`, THE Builder_Chatbot SHALL present "Import from Kinetic Profile" as a persona source option alongside the existing LinkedIn URL and manual entry options
2. WHILE the Builder_Chatbot is collecting agent definitions and the user's Profile_Document contains a null `kinetic_user_id`, THE Builder_Chatbot SHALL present only the existing LinkedIn URL and manual entry options, with an additional note: "You can also connect your Kinetic profile on your Profile page to import your professional identity"
3. WHEN the user selects "Import from Kinetic Profile", THE Scenario_Builder_API SHALL fetch the user's Identity_Envelope (from cache or API) and provide it to the Builder_Chatbot as context for persona generation
4. THE Scenario_Builder_API SHALL emit a `builder_kinetic_fetch_start` SSE event when beginning the envelope fetch and a `builder_kinetic_fetch_complete` SSE event when the envelope is available, so the Builder_Modal can display a loading indicator

### Requirement 6: Identity Envelope to Agent Persona Mapping

**User Story:** As a user, I want the AI to generate a rich agent persona from my Kinetic identity data, so that the agent in the simulation accurately represents my professional style and strengths.

#### Acceptance Criteria

1. WHEN the Builder_Chatbot receives an Identity_Envelope for persona generation, THE Kinetic_Persona_Generator SHALL map the envelope fields to AgentDefinition fields as follows: `archetype.name` + `professionalIdentity` + `communicationStyle` + `values` + `skills.verified` → `persona_prompt` (AI-generated narrative), `communicationStyle.tone` + `communicationStyle.formality` → `tone`, `professionalIdentity.currentRole` + user's display name from Profile_Document → `name`
2. THE Kinetic_Persona_Generator SHALL generate the `persona_prompt` as a detailed narrative that incorporates the user's archetype as a negotiation style anchor, verified skills as credibility evidence, communication patterns as behavioral constraints, and values as decision-making drivers
3. THE Kinetic_Persona_Generator SHALL set the agent `type` to "negotiator" by default for Kinetic-imported personas, since the user is importing their own identity to participate in the negotiation
4. THE Builder_Chatbot SHALL present the generated persona (name, persona_prompt, tone, type) to the user for review and allow modifications before incorporating it into the scenario JSON
5. THE Kinetic_Persona_Generator SHALL NOT populate `goals`, `budget`, `output_fields`, or `model_id` from the envelope — these fields are negotiation-specific and MUST be collected from the user by the Builder_Chatbot

### Requirement 7: Negotiation-Specific Field Collection After Import

**User Story:** As a user, I want the AI to ask me about my negotiation goals and budget after importing my identity, so that the scenario reflects what I'm actually negotiating for.

#### Acceptance Criteria

1. WHEN the Kinetic_Persona_Generator has generated and the user has approved the persona fields, THE Builder_Chatbot SHALL ask the user to define the negotiation-specific fields: goals (what are you negotiating for), budget (target, floor/minimum, ceiling/maximum), and output_fields
2. THE Builder_Chatbot SHALL explain that goals and budget are scenario-specific and not part of the Kinetic identity, using language such as "Your Kinetic profile tells me who you are — now tell me what you're negotiating for in this scenario"
3. WHEN the user provides goals and budget, THE Builder_Chatbot SHALL validate that at least one goal is provided and that the budget has min <= target <= max before incorporating into the scenario JSON
4. THE Builder_Chatbot SHALL suggest a default `model_id` matching the model used by other agents in the scenario, and allow the user to override

### Requirement 8: Graceful Degradation

**User Story:** As a user, I want the builder to work normally even if the Kinetic service is unavailable, so that I'm never blocked from creating scenarios.

#### Acceptance Criteria

1. IF the Kinetic_Identity_API is unreachable during the builder flow, THEN THE Builder_Chatbot SHALL inform the user that the Kinetic import is temporarily unavailable and seamlessly offer the LinkedIn URL and manual entry alternatives without interrupting the conversation flow
2. IF the user's cached Identity_Envelope is stale (older than 7 days) and the Kinetic_Identity_API is unreachable, THEN THE Kinetic_Envelope_Cache SHALL use the stale cached envelope with a warning to the user that the data may be outdated
3. THE Builder_Chatbot SHALL NOT require a Kinetic account link to complete any builder flow — all existing persona creation paths (LinkedIn URL, manual entry) remain fully functional and are the primary paths
4. WHEN the Kinetic_Identity_API returns an unexpected response format or missing required fields, THE Kinetic_Persona_Generator SHALL log the error, inform the user that the import encountered an issue, and offer alternatives

### Requirement 9: Kinetic Integration API Endpoints

**User Story:** As a developer, I want well-defined API endpoints for the Kinetic account linking and envelope operations, so that the frontend can integrate cleanly.

#### Acceptance Criteria

1. THE Scenario_Builder_API SHALL expose a `GET /api/v1/kinetic/link?email={email}` endpoint that returns a redirect URL to the Kinetic linking page with the correct service and callback parameters
2. THE Scenario_Builder_API SHALL expose a `GET /api/v1/kinetic/callback?code={code}&email={email}` endpoint that exchanges the linking code with the Kinetic_Identity_API and stores the `kinetic_user_id` on the user's Profile_Document
3. THE Scenario_Builder_API SHALL expose a `GET /api/v1/kinetic/envelope?email={email}` endpoint that returns the user's cached Identity_Envelope or fetches a fresh one from the Kinetic_Identity_API
4. THE Scenario_Builder_API SHALL expose a `DELETE /api/v1/kinetic/link?email={email}` endpoint that revokes consent on the Kinetic_Identity_API and clears the `kinetic_user_id` and cached envelope from the Profile_Document
5. THE Scenario_Builder_API SHALL expose a `POST /api/v1/kinetic/refresh?email={email}` endpoint that forces a fresh envelope fetch from the Kinetic_Identity_API, bypassing the cache TTL
6. IF any Kinetic endpoint receives a request without a valid email or for a user without an existing Profile_Document, THEN THE Scenario_Builder_API SHALL return HTTP 401 or HTTP 403 respectively

### Requirement 10: Kinetic SSE Event Format

**User Story:** As a developer, I want the Kinetic import events to follow the existing builder SSE format, so that the frontend can handle them consistently.

#### Acceptance Criteria

1. THE Scenario_Builder_API SHALL emit Kinetic-related SSE events with `event_type` values: `builder_kinetic_fetch_start` (envelope fetch initiated), `builder_kinetic_fetch_complete` (envelope data available), and `builder_kinetic_error` (Kinetic API error occurred)
2. WHEN emitting a `builder_kinetic_fetch_complete` event, THE Scenario_Builder_API SHALL include the `archetype_name`, `professional_summary`, and `depth_score` fields from the envelope as a preview for the Builder_Modal to display while the full persona is being generated
3. WHEN emitting a `builder_kinetic_error` event, THE Scenario_Builder_API SHALL include a `message` field describing the error and a `fallback` field set to "linkedin_or_manual" to signal the frontend to offer alternative persona sources
4. THE Scenario_Builder_API SHALL format all Kinetic SSE events as `data: <JSON>\n\n` consistent with the existing SSE format used by the builder streaming endpoints (Spec 130, Requirement 12)

### Requirement 11: Token Cost for Kinetic Import

**User Story:** As a user, I want the Kinetic import itself to be free, so that I'm not penalized for using my own identity data.

#### Acceptance Criteria

1. THE Scenario_Builder_API SHALL NOT deduct tokens for the Identity_Envelope fetch operation — the fetch is a data retrieval, not an LLM call
2. WHEN the Builder_Chatbot generates a persona_prompt from the Identity_Envelope, THE Scenario_Builder_API SHALL deduct 1 token from the user's daily balance as part of the normal chatbot response cost (consistent with Spec 130, Requirement 10)
3. THE Builder_Modal SHALL display the token cost breakdown: "Kinetic import: free | Persona generation: 1 token" when the user selects the Kinetic import option

### Requirement 12: Privacy and Data Boundary Enforcement

**User Story:** As a user, I want to be confident that sensitive data from my Kinetic profile is never exposed or stored beyond what's needed, so that my privacy is protected.

#### Acceptance Criteria

1. THE Kinetic_Envelope_Cache SHALL store only the fields present in the Identity_Envelope schema (version 1.0) — the Kinetic_Identity_API already excludes redFlags, salary expectations, raw transcripts, and audio recordings at the API level
2. THE Kinetic_Persona_Generator SHALL NOT include the user's `depthScore` or `credibilityIndex` numeric values in the generated `persona_prompt` — these are internal quality metrics, not persona characteristics
3. THE Kinetic_Persona_Generator SHALL use `skills.verified` evidence and metrics in the persona_prompt only as narrative credibility anchors (e.g., "led a team that increased revenue by 40%"), never as raw data dumps
4. WHEN the user disconnects their Kinetic account, THE Kinetic_Account_Linker SHALL delete the cached Identity_Envelope and `kinetic_user_id` from the Profile_Document within the same operation — no orphaned identity data

### Requirement 13: Identity Envelope Parsing and Validation

**User Story:** As a developer, I want the Identity Envelope to be parsed into a typed model with validation, so that malformed API responses don't crash the builder.

#### Acceptance Criteria

1. THE Kinetic_Persona_Generator SHALL parse the Identity_Envelope JSON into a Pydantic V2 model (`IdentityEnvelope`) that validates all required fields: version, kineticUserId, archetype (name, reasoning), professionalIdentity (currentRole, company, industry, experienceYears, summary), skills (top, verified), communicationStyle (tone, formality, vocabularyComplexity, patterns), contentThemes, values, depthScore, credibilityIndex
2. IF the Identity_Envelope JSON fails Pydantic validation, THEN THE Kinetic_Persona_Generator SHALL log the validation errors, inform the user that the Kinetic data could not be processed, and offer LinkedIn URL or manual entry alternatives
3. FOR ALL valid IdentityEnvelope objects, serializing via `model_dump()` then re-validating via `IdentityEnvelope.model_validate()` SHALL produce an equivalent object (round-trip property)
4. THE IdentityEnvelope Pydantic model SHALL use `model_config = ConfigDict(extra="ignore")` to tolerate additional fields from future API versions without breaking

### Requirement 14: Kinetic Import in Builder Conversation Context

**User Story:** As a developer, I want the Kinetic envelope data to be included in the builder's LLM context when generating the persona, so that the AI has full information to work with.

#### Acceptance Criteria

1. WHEN the user selects "Import from Kinetic Profile", THE Scenario_Builder_API SHALL include the full Identity_Envelope JSON in the Builder_Chatbot's system prompt context alongside the existing conversation history and partial scenario JSON
2. THE Scenario_Builder_API SHALL instruct the Builder_Chatbot (via system prompt) to use the envelope data to generate a persona_prompt that reads as a natural character description suitable for LLM role-play, not a data summary
3. THE Scenario_Builder_API SHALL instruct the Builder_Chatbot to explicitly ask the user for goals and budget after presenting the generated persona, making clear these are scenario-specific and not derivable from the envelope
4. THE Scenario_Builder_API SHALL NOT increase the per-message token cost for messages that include envelope context — the envelope is treated as system context, not user content
