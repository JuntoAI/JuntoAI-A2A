# Requirements Document

## Introduction

The LLM Availability Checker is a pre-flight validation system that probes configured LLM models at backend startup to determine which models are actually reachable and functional. It produces a verified "allowed models" list that gates scenario validation and builder operations, eliminating mid-negotiation failures caused by unreachable models.

Currently, model availability is only discovered when an agent attempts to speak during a live negotiation. If a model is down or misconfigured, the negotiation fails mid-stream with no recovery. This feature shifts that failure to startup time, where it can be surfaced cleanly.

## Glossary

- **Availability_Checker**: The module that probes each registered model at startup to determine reachability and functionality.
- **Model_Registry**: The canonical list of all model entries defined in `available_models.py` (`AVAILABLE_MODELS` tuple).
- **Allowed_Models_List**: The subset of Model_Registry entries that passed the availability probe at startup.
- **Probe**: A lightweight LLM invocation (minimal prompt, short max tokens) used to verify a model responds without error.
- **Model_Router**: The dual-mode routing layer (`model_router.py`) that instantiates LangChain chat model instances for cloud (Vertex AI) or local (LiteLLM) mode.
- **Scenario_Builder**: The AI-powered builder that generates and validates scenario JSON configurations.
- **Scenario_Registry**: The in-memory index of validated scenarios loaded from `*.scenario.json` files at startup.
- **Health_Endpoint**: The existing `/api/v1/health` liveness endpoint.
- **Models_Endpoint**: The existing `/api/v1/models` endpoint that returns available models.
- **RUN_MODE**: Configuration value (`cloud` or `local`) that determines which LLM provider path is used.
- **Admin_Dashboard**: The password-protected admin backend (gated behind `ADMIN_PASSWORD` env var) served at `/api/v1/admin/*` routes, providing operational visibility into the platform.
- **CLI_Checker**: A standalone Python script that reuses the Availability_Checker probe logic to let developers verify model connectivity from the command line without starting the full FastAPI application.

## Requirements

### Requirement 1: Extend Model Registry with New Models

**User Story:** As a developer, I want the model registry to include the latest Gemini preview models, so that scenarios can reference them and the availability checker can probe them.

#### Acceptance Criteria

1. THE Model_Registry SHALL include entries for `gemini-3.1-pro-preview`, `gemini-3.1-flash-lite-preview`, and `gemini-3-flash-preview` with family `gemini` and descriptive labels.
2. WHEN a new model entry is added to the Model_Registry, THE `VALID_MODEL_IDS` set, `MODELS_PROMPT_BLOCK` string, and `DEFAULT_MODEL_MAP` mappings SHALL update automatically without code changes outside the registry and mapping modules.

### Requirement 2: Startup Availability Probe

**User Story:** As a platform operator, I want the backend to probe all registered models at startup, so that I know which models are actually reachable before any negotiation begins.

#### Acceptance Criteria

1. WHEN the FastAPI application starts (lifespan context manager), THE Availability_Checker SHALL probe each model in the Model_Registry by sending a minimal prompt and awaiting a response.
2. WHILE RUN_MODE is `cloud`, THE Availability_Checker SHALL probe models via the Vertex AI path (ChatGoogleGenerativeAI for Gemini family, ChatAnthropicVertex for Claude family).
3. WHILE RUN_MODE is `local`, THE Availability_Checker SHALL probe models via the LiteLLM path using the model mapping resolution chain.
4. THE Availability_Checker SHALL execute probes concurrently with a configurable timeout per probe (default: 15 seconds).
5. IF a probe raises an exception or exceeds the timeout, THEN THE Availability_Checker SHALL mark that model as unavailable and log the model ID and error reason at WARNING level.
6. WHEN all probes complete, THE Availability_Checker SHALL log a summary listing each model ID and its availability status at INFO level.
7. IF zero models pass the probe, THEN THE Availability_Checker SHALL log an ERROR and allow the application to start (degraded mode) rather than crashing.

### Requirement 3: Allowed Models List Construction

**User Story:** As a backend service, I want a single authoritative list of verified-working models available at runtime, so that all downstream consumers reference the same truth.

#### Acceptance Criteria

1. WHEN all probes complete, THE Availability_Checker SHALL produce an Allowed_Models_List containing only the Model_Registry entries whose probes succeeded.
2. THE Allowed_Models_List SHALL be stored in the FastAPI application state (`app.state`) so that route handlers and services can access the list via dependency injection.
3. THE Allowed_Models_List SHALL be immutable after construction (no runtime mutations).

### Requirement 4: Models Endpoint Reflects Availability

**User Story:** As a frontend consumer, I want the `/api/v1/models` endpoint to return only verified-working models, so that the UI never offers models that will fail.

#### Acceptance Criteria

1. WHEN the Models_Endpoint is called, THE Models_Endpoint SHALL return only models present in the Allowed_Models_List.
2. IF the Allowed_Models_List is empty (degraded mode), THEN THE Models_Endpoint SHALL return an empty list.

### Requirement 5: Scenario Validation Against Allowed Models

**User Story:** As a platform operator, I want scenarios to be validated against the working models list at load time, so that scenarios referencing unavailable models are flagged before any negotiation starts.

#### Acceptance Criteria

1. WHEN the Scenario_Registry loads scenarios at startup, THE Scenario_Registry SHALL validate each agent's `model_id` and `fallback_model_id` against the Allowed_Models_List.
2. IF a scenario agent references a `model_id` that is not in the Allowed_Models_List and the agent has no `fallback_model_id` in the Allowed_Models_List, THEN THE Scenario_Registry SHALL log a WARNING identifying the scenario ID, agent role, and unavailable model ID.
3. WHEN listing scenarios, THE Scenario_Registry SHALL include an `available` boolean field indicating whether all agent models (primary or fallback) are present in the Allowed_Models_List.

### Requirement 6: Builder Integration with Allowed Models

**User Story:** As a scenario designer using the builder, I want the builder to only offer verified-working models, so that generated scenarios are immediately runnable.

#### Acceptance Criteria

1. WHEN the Scenario_Builder generates or validates a scenario, THE Scenario_Builder SHALL constrain model selection to the Allowed_Models_List.
2. THE builder prompt's model block (`MODELS_PROMPT_BLOCK`) SHALL be filtered to include only models from the Allowed_Models_List before injection into LLM prompts.

### Requirement 7: Health Endpoint Enhancement

**User Story:** As a platform operator, I want the health endpoint to report model availability status, so that monitoring systems can detect degraded LLM connectivity.

#### Acceptance Criteria

1. WHEN the Health_Endpoint is called, THE Health_Endpoint SHALL include a `models` object containing `total_registered` (count of Model_Registry entries) and `total_available` (count of Allowed_Models_List entries).
2. WHEN the Health_Endpoint is called, THE Health_Endpoint SHALL include an `unavailable_models` list containing the model IDs that failed the startup probe.
3. IF `total_available` is zero, THEN THE Health_Endpoint SHALL set the top-level status to `degraded` instead of `ok`.

### Requirement 8: Probe Resilience and Idempotence

**User Story:** As a developer, I want the probe mechanism to be resilient and side-effect-free, so that startup probes never corrupt state or cause cascading failures.

#### Acceptance Criteria

1. THE Availability_Checker probe prompt SHALL be a deterministic, minimal string (e.g., "Respond with OK") that produces no meaningful side effects.
2. THE Availability_Checker SHALL catch all exceptions from individual probes without propagating them to the lifespan context or other probes.
3. WHEN the same Availability_Checker runs multiple times with the same configuration and model state, THE Availability_Checker SHALL produce the same Allowed_Models_List (idempotent given identical external conditions).

### Requirement 9: Admin Dashboard Model Availability View

**User Story:** As a platform operator, I want the admin dashboard to display a dedicated model availability view showing which LLMs are registered, which are working, and which failed (with error reasons), so that I can diagnose model connectivity issues without inspecting logs.

#### Acceptance Criteria

1. WHEN an authenticated admin calls the model availability admin endpoint, THE Admin_Dashboard SHALL return a list of all Model_Registry entries with each entry's probe status (`available` or `unavailable`).
2. WHEN a model probe failed, THE Admin_Dashboard SHALL include the error reason string captured during the probe for that model.
3. THE Admin_Dashboard model availability endpoint SHALL include summary counts: `total_registered`, `total_available`, and `total_unavailable`.
4. THE Admin_Dashboard model availability endpoint SHALL be gated behind the same `ADMIN_PASSWORD` session authentication used by all other admin routes.
5. IF the Availability_Checker has not yet completed (application still starting), THEN THE Admin_Dashboard SHALL return a response indicating that probe results are not yet available.
6. WHEN the Allowed_Models_List is empty (degraded mode), THE Admin_Dashboard model availability endpoint SHALL return all models as unavailable with their respective error reasons.

### Requirement 10: Standalone CLI Model Availability Script

**User Story:** As a developer, I want a standalone CLI script that checks model availability from my local machine, so that I can verify LLM connectivity before starting the full backend application.

#### Acceptance Criteria

1. THE CLI_Checker SHALL be executable as a standalone Python script (e.g., `python -m app.check_models` or `python scripts/check_models.py`) without requiring the FastAPI application to be running.
2. THE CLI_Checker SHALL reuse the same probe logic as the Availability_Checker (Requirement 2) to test each model in the Model_Registry.
3. THE CLI_Checker SHALL read configuration from the same environment variables and `.env` file used by the backend application (`RUN_MODE`, `GOOGLE_CLOUD_PROJECT`, `VERTEX_AI_LOCATION`, `LLM_PROVIDER`, `OLLAMA_BASE_URL`, `OLLAMA_MODEL`, `LLM_MODEL_OVERRIDE`, `MODEL_MAP`).
4. WHEN all probes complete, THE CLI_Checker SHALL print a formatted table to stdout listing each model ID, its family, its probe status (`PASS` or `FAIL`), and the error reason for failed probes.
5. WHEN all probes complete, THE CLI_Checker SHALL print a summary line showing the count of passed models and total models (e.g., `3/5 models available`).
6. IF one or more models fail the probe, THEN THE CLI_Checker SHALL exit with a non-zero exit code (exit code 1).
7. WHEN all models pass the probe, THE CLI_Checker SHALL exit with exit code 0.
8. WHILE RUN_MODE is `cloud`, THE CLI_Checker SHALL probe models via the Vertex AI path, consistent with the Availability_Checker cloud-mode behavior.
9. WHILE RUN_MODE is `local`, THE CLI_Checker SHALL probe models via the LiteLLM path, consistent with the Availability_Checker local-mode behavior.
