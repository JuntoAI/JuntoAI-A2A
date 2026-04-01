# Requirements Document — A2A Local Battle Arena

## Introduction

The JuntoAI A2A Local Battle Arena enables the existing cloud MVP to run entirely on a developer's machine with zero GCP dependencies. Developers clone the repo, run `docker compose up`, and get the full Arena (FastAPI backend + Next.js frontend) on localhost. They bring their own LLM API keys (OpenAI, Anthropic, Ollama, etc.) via a `.env` file. The cloud deployment continues working exactly as before — this is purely additive.

This spec covers five abstraction layers: database (SQLite fallback), LLM routing (LiteLLM), auth bypass, Docker Compose infrastructure, and environment configuration. It does NOT cover custom agent plugins or the global leaderboard (post-MVP).

## Glossary

- **Backend**: The FastAPI Python application in `/backend` that orchestrates negotiations via LangGraph.
- **Frontend**: The Next.js 14+ application in `/frontend` that renders the Glass Box UI.
- **Session_Store**: The abstract interface for session CRUD operations (create, read, update). Implemented by `FirestoreSessionClient` (cloud) and `SQLiteSessionClient` (local).
- **Model_Router**: The module (`backend/app/orchestrator/model_router.py`) that maps `model_id` strings from scenario JSON configs to initialized LangChain chat model instances.
- **LiteLLM_Router**: The local-mode Model_Router implementation that uses the LiteLLM library to route `model_id` strings to any LLM provider (OpenAI, Anthropic, Ollama, Azure, etc.) without Vertex AI dependencies.
- **Run_Mode**: An environment variable (`RUN_MODE`) that selects between `cloud` (GCP Firestore + Vertex AI + waitlist gate) and `local` (SQLite + LiteLLM + no gate). Defaults to `local`.
- **Scenario_Config**: A JSON file (e.g., `talent_war.scenario.json`) loaded from `SCENARIOS_DIR` that defines agents, toggles, and negotiation parameters.
- **Docker_Compose_Stack**: The `docker-compose.yml` file at the monorepo root that launches the Backend and Frontend containers together on localhost.
- **Env_Example**: The `.env.example` file at the monorepo root documenting all configurable environment variables with safe defaults.
- **Auth_Gate**: The waitlist email check and 100-token-per-day enforcement layer in the Backend.
- **NegotiationStateModel**: The Pydantic model (`backend/app/models/negotiation.py`) representing a persisted negotiation session.

## Requirements

### Requirement 1: Database Abstraction Layer

**User Story:** As a backend developer, I want the session persistence layer abstracted behind a protocol (Python `Protocol` or ABC), so that Firestore and SQLite implementations are interchangeable at runtime based on Run_Mode.

#### Acceptance Criteria

1. THE Backend SHALL define a `SessionStore` protocol in `backend/app/db/base.py` with async methods: `create_session(state: NegotiationStateModel) -> None`, `get_session(session_id: str) -> NegotiationStateModel`, `get_session_doc(session_id: str) -> dict`, and `update_session(session_id: str, updates: dict) -> None`.
2. THE `FirestoreSessionClient` in `backend/app/db/firestore_client.py` SHALL implement the `SessionStore` protocol without changing its existing public API.
3. WHEN Run_Mode is `local`, THE Backend SHALL instantiate `SQLiteSessionClient` as the `SessionStore` implementation.
4. WHEN Run_Mode is `cloud`, THE Backend SHALL instantiate `FirestoreSessionClient` as the `SessionStore` implementation.
5. THE `backend/app/db/__init__.py` factory function SHALL read Run_Mode and return the appropriate `SessionStore` implementation as a singleton.
6. IF a session_id does not exist in the Session_Store, THEN THE Session_Store SHALL raise `SessionNotFoundError`.
7. IF the Session_Store connection fails during initialization, THEN THE Session_Store SHALL raise `DatabaseConnectionError` (renamed from `FirestoreConnectionError` to be provider-agnostic).

### Requirement 2: SQLite Session Store Implementation

**User Story:** As a developer running locally, I want sessions persisted in a local SQLite database file, so that I need zero cloud credentials or network access for session state.

#### Acceptance Criteria

1. THE `SQLiteSessionClient` in `backend/app/db/sqlite_client.py` SHALL implement the `SessionStore` protocol using `aiosqlite` for async SQLite access.
2. WHEN `SQLiteSessionClient` is initialized, THE `SQLiteSessionClient` SHALL create the database file at the path specified by the `SQLITE_DB_PATH` environment variable (default: `data/juntoai.db`).
3. WHEN `SQLiteSessionClient` is initialized, THE `SQLiteSessionClient` SHALL create the `negotiation_sessions` table if it does not exist, with columns: `session_id TEXT PRIMARY KEY`, `data JSON NOT NULL`, `created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP`, `updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP`.
4. WHEN `create_session` is called, THE `SQLiteSessionClient` SHALL serialize the `NegotiationStateModel` to JSON and insert it into the `negotiation_sessions` table.
5. WHEN `get_session` is called with a valid session_id, THE `SQLiteSessionClient` SHALL deserialize the JSON `data` column back into a `NegotiationStateModel`.
6. WHEN `update_session` is called, THE `SQLiteSessionClient` SHALL merge the updates dict into the existing JSON data and update the `updated_at` timestamp.
7. FOR ALL valid NegotiationStateModel instances, creating a session then reading it back SHALL produce an equivalent NegotiationStateModel (round-trip property).

### Requirement 3: LLM Router Abstraction

**User Story:** As a backend developer, I want the model routing layer abstracted so that Vertex AI (cloud) and LiteLLM (local) are interchangeable at runtime based on Run_Mode.

#### Acceptance Criteria

1. THE Model_Router module SHALL expose a `get_model(model_id: str, fallback_model_id: str | None = None) -> BaseChatModel` function that delegates to the appropriate provider based on Run_Mode.
2. WHEN Run_Mode is `cloud`, THE Model_Router SHALL route to Vertex AI model classes (`ChatVertexAI`, `ChatAnthropicVertex`) using the existing implementation logic.
3. WHEN Run_Mode is `local`, THE Model_Router SHALL route to LiteLLM via `langchain_community.chat_models.ChatLiteLLM` or the `litellm` library's LangChain integration.
4. WHEN Run_Mode is `local`, THE LiteLLM_Router SHALL read the `LLM_PROVIDER` environment variable and map scenario `model_id` values to provider-specific model strings (e.g., `gemini-2.5-flash` → `openai/gpt-4o` when `LLM_PROVIDER=openai`).
5. WHEN Run_Mode is `local` and the LLM provider API key is missing or invalid, THE LiteLLM_Router SHALL raise `ModelNotAvailableError` with a descriptive message naming the missing key.
6. THE existing `agent_node.py` call to `model_router.get_model(agent_config["model_id"])` SHALL continue working without modification in both Run_Mode values.

### Requirement 4: LLM Model Mapping Configuration

**User Story:** As a developer, I want a clear mapping from scenario `model_id` values to local LLM provider models, so that I can run any scenario with my preferred provider.

#### Acceptance Criteria

1. THE Backend SHALL define a default model mapping in `backend/app/orchestrator/model_mapping.py` that maps each scenario `model_id` to a default local model string per provider (e.g., `gemini-2.5-flash` → `gpt-4o` for OpenAI, `claude-3-5-sonnet` for Anthropic, `llama3` for Ollama).
2. WHERE a developer sets the `LLM_MODEL_OVERRIDE` environment variable, THE LiteLLM_Router SHALL use that single model for all agents regardless of scenario `model_id` values.
3. THE model mapping SHALL be overridable via a `MODEL_MAP` environment variable containing a JSON string (e.g., `{"gemini-2.5-flash": "gpt-4o-mini", "claude-3-5-sonnet-v2": "gpt-4o"}`).
4. IF a scenario `model_id` has no mapping for the current provider and no override is set, THEN THE LiteLLM_Router SHALL fall back to the provider's default model and log a warning.

### Requirement 5: Auth Gate Bypass for Local Mode

**User Story:** As a developer running locally, I want the waitlist email check and token limit enforcement completely bypassed, so that I have unlimited usage without configuring any auth infrastructure.

#### Acceptance Criteria

1. WHEN Run_Mode is `local`, THE Backend SHALL skip all waitlist email validation on negotiation endpoints.
2. WHEN Run_Mode is `local`, THE Backend SHALL skip all token balance checks and token deduction logic.
3. WHEN Run_Mode is `local`, THE Backend SHALL accept requests to `/api/v1/negotiation/start` without an `email` field or with any placeholder email value.
4. WHEN Run_Mode is `cloud`, THE Backend SHALL enforce waitlist and token gate logic exactly as before (no behavioral change).
5. WHEN Run_Mode is `local`, THE Frontend SHALL hide the waitlist/email gate screen and navigate directly to the Arena Selector.
6. WHEN Run_Mode is `local`, THE Frontend SHALL hide the token counter display or show "Unlimited" in place of a numeric token count.

### Requirement 6: Application Configuration for Run Mode

**User Story:** As a developer, I want a single `RUN_MODE` environment variable that switches the entire application between cloud and local behavior, so that configuration is simple and predictable.

#### Acceptance Criteria

1. THE `backend/app/config.py` Settings class SHALL include a `RUN_MODE` field with allowed values `cloud` and `local`, defaulting to `local`.
2. THE `backend/app/config.py` Settings class SHALL include fields: `SQLITE_DB_PATH` (default: `data/juntoai.db`), `LLM_PROVIDER` (default: `openai`), `LLM_MODEL_OVERRIDE` (default: empty string), `MODEL_MAP` (default: empty string).
3. WHEN Run_Mode is `local`, THE Backend SHALL not import or initialize any GCP-specific libraries (Firestore SDK, Vertex AI SDK) to avoid requiring GCP credentials.
4. WHEN Run_Mode is `cloud`, THE Backend SHALL behave identically to the current production implementation with no regressions.
5. THE Backend SHALL validate that `RUN_MODE` is one of `cloud` or `local` at startup and raise a clear error for invalid values.

### Requirement 7: Docker Compose Local Stack

**User Story:** As a developer, I want a single `docker compose up` command to launch the full Arena (backend + frontend) on localhost, so that setup requires only Docker and API keys.

#### Acceptance Criteria

1. THE monorepo root SHALL contain a `docker-compose.yml` file defining two services: `backend` (FastAPI on port 8000) and `frontend` (Next.js on port 3000).
2. WHEN `docker compose up` is executed, THE Docker_Compose_Stack SHALL build both containers from their respective Dockerfiles and start them with `RUN_MODE=local` set by default.
3. THE `backend` service SHALL mount a named volume for the SQLite database file so that session data persists across container restarts.
4. THE `backend` service SHALL load environment variables from the `.env` file at the monorepo root.
5. THE `frontend` service SHALL set `NEXT_PUBLIC_API_URL=http://localhost:8000` by default so the frontend connects to the local backend.
6. THE Docker_Compose_Stack SHALL include a health check for the backend service using the existing `GET /api/v1/health` endpoint.
7. THE `frontend` service SHALL depend on the `backend` service with a `condition: service_healthy` dependency so the frontend waits for the backend to be ready.

### Requirement 8: Environment Configuration File

**User Story:** As a developer, I want a well-documented `.env.example` file, so that I can configure my API keys and preferences by copying and editing a single file.

#### Acceptance Criteria

1. THE monorepo root SHALL contain a `.env.example` file with all configurable environment variables, grouped by category (Run Mode, LLM Provider, Database, Frontend).
2. THE `.env.example` file SHALL include inline comments explaining each variable, its allowed values, and its default.
3. THE `.env.example` file SHALL include examples for at least three LLM providers: OpenAI, Anthropic, and Ollama.
4. THE `.env.example` file SHALL set `RUN_MODE=local` as the default.
5. THE `.env.example` file SHALL be listed in `.gitignore` as a pattern exception (`.env` is ignored, `.env.example` is tracked).
6. WHEN a developer copies `.env.example` to `.env` and sets one API key, THE Docker_Compose_Stack SHALL start successfully with that single configuration change.

### Requirement 9: Scenario Config Compatibility

**User Story:** As a developer, I want the same scenario JSON config files to work identically in both cloud and local modes, so that I can develop and test scenarios locally before deploying to cloud.

#### Acceptance Criteria

1. THE Backend SHALL load scenario configs from `SCENARIOS_DIR` identically in both Run_Mode values.
2. THE Backend SHALL not require any local-mode-specific fields in scenario JSON configs.
3. WHEN Run_Mode is `local`, THE Model_Router SHALL translate scenario `model_id` values (e.g., `gemini-2.5-flash`, `claude-3-5-sonnet-v2`) to the local provider's equivalent models transparently.
4. FOR ALL scenario JSON configs, loading in cloud mode and loading in local mode SHALL produce identical `NegotiationState` initial states (same session structure, same agent roles, same turn order, same toggles).

### Requirement 10: Exception Naming Generalization

**User Story:** As a backend developer, I want exception class names to be provider-agnostic, so that error handling code does not reference specific cloud services.

#### Acceptance Criteria

1. THE `backend/app/exceptions.py` module SHALL rename `FirestoreConnectionError` to `DatabaseConnectionError` while maintaining the same constructor signature and behavior.
2. THE `backend/app/main.py` exception handler for database connection errors SHALL reference `DatabaseConnectionError` instead of `FirestoreConnectionError`.
3. THE `FirestoreSessionClient` SHALL raise `DatabaseConnectionError` instead of `FirestoreConnectionError` when the Firestore SDK connection fails.
4. THE `SQLiteSessionClient` SHALL raise `DatabaseConnectionError` when the SQLite database file cannot be opened or created.
5. WHEN a `DatabaseConnectionError` is raised, THE Backend SHALL return HTTP 503 with `{"detail": "Database unavailable"}` regardless of which Session_Store implementation is active.

### Requirement 11: Backend Dockerfile Update for Local Mode

**User Story:** As a developer, I want the backend Docker image to include all dependencies for local mode (aiosqlite, litellm) without breaking cloud mode, so that a single image works in both environments.

#### Acceptance Criteria

1. THE `backend/requirements.txt` SHALL include `aiosqlite` and `litellm` as dependencies.
2. THE `backend/requirements.txt` SHALL include `langchain-community` for the LiteLLM LangChain integration.
3. WHEN Run_Mode is `cloud`, THE Backend SHALL not fail due to the presence of local-mode dependencies in the environment.
4. THE `backend/Dockerfile` SHALL create the `data/` directory for the SQLite database file.

### Requirement 12: Frontend Environment Detection

**User Story:** As a frontend developer, I want the Next.js app to detect local mode and adjust the UI accordingly, so that developers see a streamlined experience without cloud-specific screens.

#### Acceptance Criteria

1. THE Frontend SHALL read a `NEXT_PUBLIC_RUN_MODE` environment variable (default: `local`) to determine the active mode.
2. WHEN `NEXT_PUBLIC_RUN_MODE` is `local`, THE Frontend SHALL skip the Landing Page (waitlist gate) and render the Arena Selector as the entry point.
3. WHEN `NEXT_PUBLIC_RUN_MODE` is `local`, THE Frontend SHALL hide or disable the token counter component.
4. WHEN `NEXT_PUBLIC_RUN_MODE` is `cloud`, THE Frontend SHALL render the full 4-screen flow (Landing Page → Arena Selector → Glass Box → Outcome Receipt) with no behavioral changes.

### Requirement 13: Lazy Import of GCP Dependencies

**User Story:** As a developer running locally, I want GCP-specific Python packages (google-cloud-firestore, langchain-google-vertexai) to be imported only when Run_Mode is `cloud`, so that local mode works even if GCP packages are not installed.

#### Acceptance Criteria

1. WHEN Run_Mode is `local`, THE Backend SHALL not execute top-level imports of `google.cloud.firestore`, `langchain_google_vertexai`, or `google.cloud.aiplatform`.
2. WHEN Run_Mode is `cloud`, THE Backend SHALL import GCP packages at the point of use (lazy import inside the factory function or model router).
3. IF Run_Mode is `cloud` and a required GCP package is not installed, THEN THE Backend SHALL raise an `ImportError` with a message listing the missing package name.
4. WHEN Run_Mode is `local`, THE Backend SHALL start successfully with only the local-mode dependencies installed (`aiosqlite`, `litellm`, `langchain-community`).
