# Tasks

## Task 1: Backend project scaffold and dependency configuration

- [x] Create `/backend/app/__init__.py`, `/backend/app/main.py`, `/backend/app/config.py`
- [x] Create `backend/requirements.txt` with pinned dependencies: `fastapi>=0.115.0`, `uvicorn[standard]>=0.30.0`, `pydantic>=2.0.0`, `pydantic-settings>=2.0.0`, `google-cloud-firestore>=2.16.0`, `google-cloud-aiplatform>=1.60.0`, `langgraph>=0.2.0`, `langchain-google-vertexai>=2.0.0`
- [x] Create `backend/Dockerfile` with Python 3.11-slim base, `requirements.txt` install, and `uvicorn app.main:app --host 0.0.0.0 --port 8080` entrypoint
- [x] Implement `backend/app/config.py` with Pydantic `BaseSettings` class reading `CORS_ALLOWED_ORIGINS` (default `http://localhost:3000`), `APP_VERSION` (default `0.1.0`), `ENVIRONMENT` (default `development`), `GOOGLE_CLOUD_PROJECT` (default `""`), and a `cors_origins_list` property that splits the comma-separated string
- [x] Implement `backend/app/main.py` with a FastAPI app titled `"JuntoAI A2A API"`, `CORSMiddleware` configured from Settings (methods: GET/POST/OPTIONS, headers: Content-Type/Authorization/Cache-Control, credentials: true), an `/api/v1` router prefix, and a startup log line printing version, environment, and CORS origins
- [x] Verify the app starts locally with `uvicorn app.main:app` without import errors

Requirements covered: 1.1–1.7

## Task 2: Health check endpoint and HealthResponse model

- [x] Create `backend/app/models/__init__.py` and `backend/app/models/health.py` with a `HealthResponse` Pydantic V2 model containing `status: str` and `version: str`
- [x] Create `backend/app/routers/__init__.py` and `backend/app/routers/health.py` with a `GET /health` route returning `HealthResponse(status="ok", version=settings.APP_VERSION)`
- [x] Register the health router on the `/api/v1` APIRouter in `main.py`
- [x] Verify `GET /api/v1/health` returns `{"status": "ok", "version": "0.1.0"}` with HTTP 200

Requirements covered: 2.1–2.4

## Task 3: NegotiationState and SSE event Pydantic models

- [x] Create `backend/app/models/negotiation.py` with `NegotiationStateModel` containing all fields per the design data model table: `session_id` (str), `scenario_id` (str), `turn_count` (int, default 0, ge=0), `max_turns` (int, default 15, gt=0), `current_speaker` (str, default "Buyer"), `deal_status` (Literal["Negotiating","Agreed","Blocked","Failed"], default "Negotiating"), `current_offer` (float, default 0.0, ge=0.0), `history` (list[dict[str,Any]], default_factory=list), `warning_count` (int, default 0, ge=0), `hidden_context` (dict[str,Any], default_factory=dict), `agreement_threshold` (float, default 1000000.0, gt=0.0), `active_toggles` (list[str], default_factory=list), `turn_order` (list[str], default_factory=list), `turn_order_index` (int, default 0, ge=0), `agent_states` (dict[str, dict[str,Any]], default_factory=dict)
- [x] Create `backend/app/models/events.py` with four Pydantic V2 models using Literal discriminators: `AgentThoughtEvent`, `AgentMessageEvent`, `NegotiationCompleteEvent`, `StreamErrorEvent` — fields per design data models table
- [x] Export all models from `backend/app/models/__init__.py`
- [x] Verify `deal_status` rejects invalid values and all models instantiate with defaults

Requirements covered: 3.1–3.13, 6.1–6.5

## Task 4: SSE event formatting utility

- [x] Create `backend/app/utils/__init__.py` and `backend/app/utils/sse.py` with `format_sse_event(event: BaseModel) -> str` that returns `f"data: {event.model_dump_json()}\n\n"`
- [x] Verify output for each event type starts with `data: `, ends with `\n\n`, and contains parseable JSON with `event_type` field

Requirements covered: 5.4, 5.5, 5.6

## Task 5: Custom exceptions and Firestore client module

- [x] Create `backend/app/exceptions.py` with `SessionNotFoundError(session_id: str)` and `FirestoreConnectionError(message: str)` exception classes
- [x] Create `backend/app/db/__init__.py` with `get_firestore_client()` singleton dependency function
- [x] Create `backend/app/db/firestore_client.py` with `FirestoreSessionClient` using `google.cloud.firestore.AsyncClient`, targeting the `negotiation_sessions` collection
- [x] Implement `create_session(state: NegotiationStateModel)` — writes document keyed by `session_id`
- [x] Implement `get_session(session_id: str) -> NegotiationStateModel` — reads document, raises `SessionNotFoundError` if not found
- [x] Implement `update_session(session_id: str, updates: dict)` — merges fields, raises `SessionNotFoundError` if document doesn't exist
- [x] Wrap `AsyncClient` initialization in try/except that raises `FirestoreConnectionError`
- [x] Register exception handlers in `main.py` for `SessionNotFoundError` → 404 and `FirestoreConnectionError` → 503

Requirements covered: 4.1–4.8

## Task 6: SSE connection rate limiter

- [x] Create `backend/app/middleware/__init__.py` and `backend/app/middleware/sse_limiter.py` with `SSEConnectionTracker` class using `defaultdict(int)` + `asyncio.Lock` per the design
- [x] Implement `acquire(email: str) -> bool` — returns `True` and increments if under limit (3), `False` if at limit
- [x] Implement `release(email: str)` — decrements count (floor at 0), deletes key if count reaches 0
- [x] Create `get_sse_tracker()` singleton dependency function in `backend/app/middleware/__init__.py`

Requirements covered: 7.1, 7.2, 7.5

## Task 7: SSE stream endpoint

- [x] Create `backend/app/routers/negotiation.py` with `GET /negotiation/stream/{session_id}` accepting `email` query param, injecting `FirestoreSessionClient` and `SSEConnectionTracker` via `Depends`
- [x] Implement session lookup → 404 if not found, email ownership check → 403 if mismatch, connection acquire → 429 if limit reached
- [x] Return `StreamingResponse` with `media_type="text/event-stream"`, headers `Cache-Control: no-cache` and `Connection: keep-alive`
- [x] Implement async generator: compute timeout as `max_turns * 30` seconds, iterate events from placeholder generator (swapped for spec 030's `run_negotiation()` later), yield `format_sse_event(event)` for each
- [x] On terminal `deal_status`: yield `NegotiationCompleteEvent`, break
- [x] On timeout (`asyncio.wait_for`): yield `NegotiationCompleteEvent(deal_status="Failed")`, break
- [x] On unexpected exception: yield `StreamErrorEvent`, log full error server-side, break
- [x] In `finally` block: call `tracker.release(email)`
- [x] Register the negotiation router on the `/api/v1` prefix in `main.py`

Requirements covered: 5.1–5.9, 7.3, 7.4

## Task 8: Unit and integration tests

- [x] Create `backend/tests/conftest.py` with shared fixtures: `test_client` (FastAPI TestClient), mock Firestore client, sample `NegotiationStateModel` factory
- [x] Create `backend/tests/unit/test_models.py` — default values, `deal_status` validation rejects invalid, all event models instantiate, JSON round-trip for `NegotiationStateModel` and all event models
- [x] Create `backend/tests/unit/test_exceptions.py` — message formatting for both exception classes
- [x] Create `backend/tests/unit/test_sse_limiter.py` — acquire up to 3, 4th returns False, release decrements, floor at 0, independent emails
- [x] Create `backend/tests/unit/test_sse_format.py` — `format_sse_event` produces `data: <JSON>\n\n` for each event type, JSON parseable, contains `event_type`
- [x] Create `backend/tests/integration/test_health.py` — GET /api/v1/health returns 200 with correct body
- [x] Create `backend/tests/integration/test_stream.py` — 404 unknown session, 429 limit exceeded, 403 email mismatch, successful stream returns text/event-stream
- [x] Create `backend/tests/unit/test_properties.py` — property-based tests for Properties 1, 2, 3, 5 from the design doc (hypothesis, min 100 examples each)
- [x] Create `backend/pytest.ini` with `--cov=app --cov-fail-under=70` settings and `asyncio_mode = auto`
- [x] Verify all tests pass with `cd backend && pytest --cov=app --cov-fail-under=70`

Requirements covered: All (validation of 1.x–7.x via tests)
