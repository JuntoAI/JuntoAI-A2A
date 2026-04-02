# Implementation Plan: A2A Local Battle Arena

## Overview

Convert the JuntoAI A2A MVP from a GCP-only deployment to a dual-mode application (cloud + local) controlled by a single `RUN_MODE` environment variable. All changes are additive — the cloud path remains untouched. Ollama runs as a Docker Compose sidecar (default `LLM_PROVIDER`), giving developers a working LLM out of the box with `docker compose up` — no API keys or `.env` file needed. Implementation proceeds bottom-up: exceptions → config → DB abstraction → SQLite → model mapping → model router → auth bypass → Docker Compose (backend + frontend + ollama + ollama-pull) → frontend env detection → environment file.

## Tasks

- [ ] 1. Generalize exceptions and update config
  - [-] 1.1 Rename `FirestoreConnectionError` to `DatabaseConnectionError` in `backend/app/exceptions.py`
    - Rename the class to `DatabaseConnectionError`, keep same constructor signature
    - Add `FirestoreConnectionError = DatabaseConnectionError` alias for backward compat
    - _Requirements: 10.1_

  - [~] 1.2 Update `backend/app/main.py` exception handler to reference `DatabaseConnectionError`
    - Change import from `FirestoreConnectionError` to `DatabaseConnectionError`
    - Update the exception handler registration to use `DatabaseConnectionError`
    - Keep the 503 response body `{"detail": "Database unavailable"}` unchanged
    - _Requirements: 10.2, 10.5_

  - [~] 1.3 Update `FirestoreSessionClient` to raise `DatabaseConnectionError`
    - Change import in `backend/app/db/firestore_client.py` from `FirestoreConnectionError` to `DatabaseConnectionError`
    - _Requirements: 10.3_

  - [~] 1.4 Add new config fields to `backend/app/config.py` Settings class
    - Add `RUN_MODE: Literal["cloud", "local"]` with default `"local"`
    - Add `SQLITE_DB_PATH: str` with default `"data/juntoai.db"`
    - Add `LLM_PROVIDER: str` with default `"ollama"` (zero-config: Ollama is the default provider)
    - Add `LLM_MODEL_OVERRIDE: str` with default `""`
    - Add `MODEL_MAP: str` with default `""`
    - Add `OLLAMA_BASE_URL: str` with default `"http://ollama:11434"` (Docker Compose internal URL)
    - Add `OLLAMA_MODEL: str` with default `"llama3.1"` (model to pull and use for all agents)
    - Pydantic validates `RUN_MODE` is one of `cloud` or `local` at startup
    - _Requirements: 6.1, 6.2, 6.5_

  - [~] 1.5 Write property test for RUN_MODE validation (Property 7)
    - **Property 7: RUN_MODE validation rejects invalid values**
    - For any string not in `{"cloud", "local"}`, constructing Settings with that RUN_MODE raises `ValidationError`
    - **Validates: Requirements 6.5**

  - [~] 1.6 Write property test for DatabaseConnectionError → HTTP 503 (Property 9)
    - **Property 9: DatabaseConnectionError produces HTTP 503**
    - For any request triggering `DatabaseConnectionError`, the handler returns 503 with `{"detail": "Database unavailable"}`
    - **Validates: Requirements 10.5**

- [~] 2. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 3. Database abstraction layer and SQLite implementation
  - [~] 3.1 Create `SessionStore` protocol in `backend/app/db/base.py`
    - Define `Protocol` with `@runtime_checkable` decorator
    - Declare async methods: `create_session`, `get_session`, `get_session_doc`, `update_session`
    - Signatures must match existing `FirestoreSessionClient` public API exactly
    - _Requirements: 1.1_

  - [~] 3.2 Implement `SQLiteSessionClient` in `backend/app/db/sqlite_client.py`
    - Implement `SessionStore` protocol using `aiosqlite`
    - Auto-create DB file at `SQLITE_DB_PATH` and `negotiation_sessions` table on init
    - Schema: `session_id TEXT PRIMARY KEY`, `data JSON NOT NULL`, `created_at TIMESTAMP`, `updated_at TIMESTAMP`
    - `create_session`: serialize via `model.model_dump_json()`, insert row
    - `get_session`: deserialize via `NegotiationStateModel.model_validate_json()`
    - `get_session_doc`: return parsed JSON dict
    - `update_session`: read existing JSON, merge updates dict, write back, bump `updated_at`
    - Raise `SessionNotFoundError` for missing session_id
    - Raise `DatabaseConnectionError` if SQLite file cannot be opened/created
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 1.6, 1.7_

  - [~] 3.3 Refactor `backend/app/db/__init__.py` factory to return `SessionStore`
    - Replace `get_firestore_client()` with `get_session_store() -> SessionStore`
    - When `RUN_MODE=local`: lazy import and instantiate `SQLiteSessionClient`
    - When `RUN_MODE=cloud`: lazy import `google.cloud.firestore` and instantiate `FirestoreSessionClient`
    - Maintain singleton pattern
    - _Requirements: 1.3, 1.4, 1.5, 6.3, 13.1, 13.2_

  - [~] 3.4 Update all call sites from `get_firestore_client` to `get_session_store`
    - Update `backend/app/routers/negotiation.py` import and `Depends()` call
    - Update type annotation from `FirestoreSessionClient` to `SessionStore`
    - Verify no other files import `get_firestore_client`
    - _Requirements: 1.2, 1.5_

  - [~] 3.5 Write property test for session round-trip (Property 1)
    - **Property 1: Session round-trip (create → read equivalence)**
    - For any valid `NegotiationStateModel`, `create_session` then `get_session` returns equivalent model
    - Use Hypothesis strategies for all NegotiationStateModel fields
    - **Validates: Requirements 2.4, 2.5, 2.7**

  - [~] 3.6 Write property test for missing session error (Property 2)
    - **Property 2: Missing session raises SessionNotFoundError**
    - For any random session_id not inserted, `get_session` raises `SessionNotFoundError`
    - **Validates: Requirements 1.6**

  - [~] 3.7 Write property test for update merge (Property 3)
    - **Property 3: Update merge preserves unmodified fields**
    - For any persisted model and any partial updates dict, updated fields match new values, others unchanged
    - **Validates: Requirements 2.6**

- [~] 4. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 5. Model mapping and LLM router refactor
  - [~] 5.1 Create `backend/app/orchestrator/model_mapping.py`
    - Define `DEFAULT_MODEL_MAP` dict with mappings for `openai`, `anthropic`, `ollama` providers
    - Ollama mapping: all scenario `model_id` values (`gemini-2.5-flash`, `gemini-2.5-pro`) map to `ollama/{OLLAMA_MODEL}` using `os.environ.get("OLLAMA_MODEL", "llama3.1")` at import time
    - OpenAI mapping: `gemini-2.5-flash` → `gpt-4o-mini`, `gemini-2.5-pro` → `gpt-4o`
    - Anthropic mapping: `gemini-2.5-flash` → `claude-3-5-haiku-20241022`, `gemini-2.5-pro` → `claude-sonnet-4-20250514`
    - Implement `resolve_model_id(model_id, provider, model_override, model_map_json)` function
    - Resolution order: `LLM_MODEL_OVERRIDE` → `MODEL_MAP` JSON → `DEFAULT_MODEL_MAP` → provider default + warning
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.6, 4.7, 15.1, 15.5_

  - [~] 5.2 Refactor `backend/app/orchestrator/model_router.py` for dual-mode routing
    - Move GCP imports (`langchain_google_vertexai`, `ChatVertexAI`, `ChatAnthropicVertex`) from top-level to inside cloud-mode branch (lazy imports)
    - When `RUN_MODE=local`: import `ChatLiteLLM` from `langchain_community.chat_models`, use `model_mapping.resolve_model_id()` to translate model_id, return `ChatLiteLLM` instance
    - When `RUN_MODE=local` and `LLM_PROVIDER=ollama`: set `api_base` parameter to `OLLAMA_BASE_URL` (from settings), do NOT require any API key env vars
    - When `RUN_MODE=local` and `LLM_PROVIDER` is not `ollama`: require the provider's API key (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`), raise `ModelNotAvailableError` if missing
    - When `RUN_MODE=cloud`: existing Vertex AI logic unchanged
    - Keep `get_model()` function signature identical so `agent_node.py` needs no changes
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 6.3, 13.1, 13.2, 13.3, 15.2, 15.3, 15.4_

  - [~] 5.3 Write property test for model mapping validity (Property 4)
    - **Property 4: Model mapping produces valid provider model strings**
    - For any supported provider and any scenario model_id in default mapping, result is non-empty string
    - **Validates: Requirements 3.4, 4.1, 9.3**

  - [~] 5.4 Write property test for model override precedence (Property 5)
    - **Property 5: Model override takes precedence over mapping**
    - For any model_id and non-empty override, resolved model equals override regardless of provider/MODEL_MAP
    - When override empty but MODEL_MAP has entry, MODEL_MAP takes precedence over default
    - **Validates: Requirements 4.2, 4.3**

  - [ ]* 5.5 Write property test for Ollama mapping uses OLLAMA_MODEL (Property 10)
    - **Property 10: Ollama mapping uses OLLAMA_MODEL for all scenario model_ids**
    - For any `OLLAMA_MODEL` value and any scenario `model_id` in default mapping, when `LLM_PROVIDER=ollama`, `resolve_model_id()` returns `ollama/{OLLAMA_MODEL}`
    - Overriding `OLLAMA_MODEL` (e.g., to `mistral`) causes all scenario model_ids to resolve to `ollama/mistral`
    - **Validates: Requirements 4.2, 15.1, 15.5**

  - [ ]* 5.6 Write property test for Ollama requires no API keys (Property 11)
    - **Property 11: Ollama provider requires no API keys**
    - For any configuration where `LLM_PROVIDER=ollama`, the model router does not raise `ModelNotAvailableError` due to missing API key env vars
    - Unset all API key env vars (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`), verify Ollama path is functional
    - **Validates: Requirements 15.3**

- [~] 6. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 7. Auth gate bypass for local mode
  - [~] 7.1 Add RUN_MODE check to negotiation router auth logic
    - In `backend/app/routers/negotiation.py`, wrap email ownership check and SSE tracker logic in `if settings.RUN_MODE == "cloud"` guard
    - When `RUN_MODE=local`: skip email validation, skip token checks, use `email or "local@dev"` as placeholder
    - When `RUN_MODE=cloud`: existing auth logic unchanged
    - _Requirements: 5.1, 5.2, 5.3, 5.4_

  - [~] 7.2 Write property test for local mode email acceptance (Property 6)
    - **Property 6: Local mode accepts any email value**
    - For any string (including empty, unicode), `RUN_MODE=local` does not reject based on email
    - **Validates: Requirements 5.3**

- [ ] 8. Docker Compose stack and environment files
  - [~] 8.1 Create `docker-compose.yml` at monorepo root
    - Define `ollama` service: `ollama/ollama` image, ports `11434:11434`, volume `ollama-data:/root/.ollama`, healthcheck on `http://localhost:11434/api/tags`
    - Define `ollama-pull` init service: `ollama/ollama` image, `depends_on` ollama (healthy), entrypoint `ollama pull ${OLLAMA_MODEL:-llama3.1}`, env `OLLAMA_HOST=http://ollama:11434`
    - Define `backend` service: build from `./backend`, ports `8000:8080`, `env_file: .env`, environment `RUN_MODE=local`, `LLM_PROVIDER=ollama`, `OLLAMA_BASE_URL=http://ollama:11434`, volume `sqlite-data:/app/data`, `depends_on` ollama-pull (`condition: service_completed_successfully`), healthcheck on `/api/v1/health`
    - Define `frontend` service: build from `./frontend`, ports `3000:3000`, `NEXT_PUBLIC_API_URL=http://localhost:8000`, `NEXT_PUBLIC_RUN_MODE=local`, `depends_on` backend (`condition: service_healthy`)
    - Define volumes: `sqlite-data`, `ollama-data`
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 7.8, 7.9, 7.10, 7.11, 14.1, 14.2, 14.3, 14.4, 14.5, 14.6, 14.7, 14.8_

  - [~] 8.2 Update `backend/Dockerfile` for local mode support
    - Add `RUN mkdir -p data` to create the SQLite data directory
    - _Requirements: 11.4_

  - [~] 8.3 Update `backend/requirements.txt` with local-mode dependencies
    - Add `aiosqlite` for async SQLite access
    - Add `litellm` for LLM provider routing
    - Add `langchain-community` for `ChatLiteLLM` integration
    - _Requirements: 11.1, 11.2, 11.3_

  - [~] 8.4 Create `.env.example` at monorepo root
    - Group variables by category: Run Mode, LLM Provider, Ollama, Database, Frontend
    - Include `OLLAMA_BASE_URL` (default: `http://ollama:11434`) and `OLLAMA_MODEL` (default: `llama3.1`) in Ollama section
    - Include inline comments for each variable with allowed values and defaults
    - Include examples for OpenAI, Anthropic, and Ollama providers
    - Set `RUN_MODE=local` and `LLM_PROVIDER=ollama` as defaults (zero-config experience)
    - Document that no `.env` file is needed for first run with Ollama
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.6_

  - [~] 8.5 Update `.gitignore` to track `.env.example`
    - Ensure `.env` is ignored but `.env.example` is tracked (add `!.env.example` exception)
    - _Requirements: 8.5_

- [ ] 9. Scenario config compatibility verification
  - [~] 9.1 Write property test for scenario state identity across modes (Property 8)
    - **Property 8: Scenario config produces identical initial state across modes**
    - For any valid scenario config, `create_initial_state()` produces identical NegotiationState in both modes
    - Only the backing LLM differs — state structure is mode-independent
    - **Validates: Requirements 9.1, 9.2, 9.4**

- [ ] 10. Frontend environment detection
  - [~] 10.1 Add local mode detection to frontend
    - Read `NEXT_PUBLIC_RUN_MODE` environment variable (default: `local`)
    - When `local`: skip Landing Page (waitlist gate), render Arena Selector as entry point
    - When `local`: hide token counter or show "Unlimited"
    - When `cloud`: full 4-screen flow unchanged
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 5.5, 5.6_

- [~] 11. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation after each major layer
- Property tests validate universal correctness properties from the design document
- All Python code uses Python 3.11+ with async/await patterns
- The cloud path is never modified — all changes are additive
