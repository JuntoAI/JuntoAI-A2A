# Design Document: Backend Core & SSE Streaming Infrastructure

## Overview

This design covers the foundational Python FastAPI backend application and the Server-Sent Events (SSE) streaming infrastructure for the JuntoAI A2A MVP. The backend serves as the API layer between the Next.js frontend and the LangGraph orchestration engine (spec 030), handling session persistence via Firestore, real-time event streaming via SSE, and connection-level abuse prevention.

### Key Design Decisions

1. **Async-first Firestore client** — Uses `google.cloud.firestore.AsyncClient` (not the sync `Client`) because the SSE streaming endpoint is an async generator. Mixing sync Firestore calls inside an async stream would block the event loop and kill concurrency under Cloud Run's single-process model.
2. **Pydantic V2 models as the serialization boundary** — The `NegotiationStateModel` is the canonical serialization format for Firestore persistence and API responses. The LangGraph `TypedDict` (spec 030) is the runtime format. Explicit `to_pydantic()` / `from_pydantic()` converters bridge the two. This spec owns the Pydantic side; spec 030 owns the TypedDict side and the converters.
3. **SSE generator as a thin adapter** — The SSE endpoint does not contain orchestration logic. It receives an async iterator of Pydantic event objects from the orchestrator (spec 030's `run_negotiation()`) and serializes them to `data: <JSON>\n\n` format. This keeps the streaming layer testable independently of LLM calls.
4. **In-memory connection tracking with known limitations** — The `SSEConnectionTracker` uses a per-process `dict` to count active connections per email. On Cloud Run with `--max-instances > 1`, this means the 3-connection limit is per-instance, not global. This is acceptable for MVP because: (a) Cloud Run defaults to 1 instance for low traffic, (b) a user would need to hit different instances simultaneously to exceed the limit, (c) Firestore-based distributed tracking adds latency to every SSE connect/disconnect and is overkill for a demo product with 100 tokens/day per user.
5. **Session ownership via email query parameter** — The SSE endpoint validates `?email=` against the `owner_email` stored in the Firestore session document. This is not a security boundary (no auth tokens), but prevents casual cross-session snooping. The waitlist email system (spec 050) is the real access gate.
6. **Discriminated union for SSE events** — All four event types share an `event_type` literal discriminator field. This enables the frontend to `switch` on `event_type` without guessing the payload shape, and enables Pydantic to validate the correct model via `Annotated[Union[...], Discriminator("event_type")]` if needed.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      FastAPI Application                     │
│  Title: "JuntoAI A2A API"   Prefix: /api/v1                │
├──────────┬──────────────────┬───────────────────────────────┤
│  Health  │  Negotiation     │  (Future: Waitlist, Scenarios)│
│  Router  │  Router          │  from specs 040, 050          │
│          │                  │                               │
│ GET      │ GET /negotiation/│                               │
│ /health  │ stream/{sid}     │                               │
│          │   ?email=...     │                               │
└────┬─────┴────────┬─────────┴───────────────────────────────┘
     │              │
     │              ▼
     │    ┌─────────────────────┐
     │    │ SSEConnectionTracker│ (in-memory, per-process)
     │    │ acquire(email)->bool│
     │    │ release(email)      │
     │    └────────┬────────────┘
     │             │ if acquired
     │             ▼
     │    ┌─────────────────────┐
     │    │ FirestoreSession    │
     │    │ Client              │
     │    │  create_session()   │
     │    │  get_session()      │
     │    │  update_session()   │
     │    └────────┬────────────┘
     │             │ AsyncClient
     │             ▼
     │    ┌─────────────────────┐
     │    │ GCP Firestore       │
     │    │ Collection:         │
     │    │ negotiation_sessions│
     │    └─────────────────────┘
     │
     │    ┌─────────────────────┐
     │    │ Orchestrator        │ (spec 030 — NOT this spec)
     │    │ run_negotiation()   │──▶ async yields event objects
     │    └─────────────────────┘
     │             │
     │             ▼
     │    ┌─────────────────────┐
     │    │ format_sse_event()  │ Pydantic model → "data: <JSON>\n\n"
     │    └─────────────────────┘
     │             │
     │             ▼
     │    ┌─────────────────────┐
     │    │ StreamingResponse   │ text/event-stream
     │    │ Cache-Control:      │ no-cache
     │    │ Connection:         │ keep-alive
     │    └─────────────────────┘
```

### Directory Layout

```
/backend/
├── Dockerfile
├── requirements.txt
├── pytest.ini
└── app/
    ├── __init__.py
    ├── main.py                 # FastAPI app, CORS, router registration, startup log
    ├── config.py               # Pydantic Settings (env vars)
    ├── exceptions.py           # SessionNotFoundError, FirestoreConnectionError
    ├── models/
    │   ├── __init__.py         # Re-exports all models
    │   ├── health.py           # HealthResponse
    │   ├── negotiation.py      # NegotiationStateModel
    │   └── events.py           # AgentThoughtEvent, AgentMessageEvent,
    │                           # NegotiationCompleteEvent, StreamErrorEvent
    ├── db/
    │   ├── __init__.py         # get_firestore_client() dependency
    │   └── firestore_client.py # FirestoreSessionClient (async)
    ├── middleware/
    │   ├── __init__.py
    │   └── sse_limiter.py      # SSEConnectionTracker
    ├── routers/
    │   ├── __init__.py
    │   ├── health.py           # GET /health
    │   └── negotiation.py      # GET /negotiation/stream/{session_id}
    └── utils/
        ├── __init__.py
        └── sse.py              # format_sse_event() helper
```

## Components and Interfaces

### 1. Configuration (`app/config.py`)

A Pydantic `BaseSettings` class that reads from environment variables with sensible defaults for local development.

```python
class Settings(BaseSettings):
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"
    CORS_ALLOWED_ORIGINS: str = "http://localhost:3000"
    GOOGLE_CLOUD_PROJECT: str = ""

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ALLOWED_ORIGINS.split(",") if o.strip()]

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
```

The `cors_origins_list` property parses the comma-separated string into a list for the CORS middleware. In production, `CORS_ALLOWED_ORIGINS` is set to the Cloud Run frontend URL (e.g., `https://juntoai-frontend-HASH-ew.a.run.app`).

### 2. FastAPI Application (`app/main.py`)

Responsibilities:
- Create the `FastAPI` instance with title and version
- Add `CORSMiddleware` with origins from `Settings`, methods `["GET", "POST", "OPTIONS"]`, headers `["Content-Type", "Authorization", "Cache-Control"]`, `allow_credentials=True`
- Register routers under the `/api/v1` prefix
- Log startup info (version, environment, CORS origins) via a `lifespan` context manager or `@app.on_event("startup")`

The app uses a single `APIRouter` prefix approach:

```python
api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health_router)
api_router.include_router(negotiation_router)
app.include_router(api_router)
```

### 3. Firestore Session Client (`app/db/firestore_client.py`)

An async wrapper around the Firestore SDK. Uses dependency injection so tests can substitute a mock.

```python
class FirestoreSessionClient:
    COLLECTION = "negotiation_sessions"

    def __init__(self, project: str | None = None):
        try:
            self._db = firestore.AsyncClient(project=project)
        except Exception as e:
            raise FirestoreConnectionError(f"Failed to initialize Firestore: {e}")
        self._collection = self._db.collection(self.COLLECTION)

    async def create_session(self, state: NegotiationStateModel) -> None:
        doc_ref = self._collection.document(state.session_id)
        await doc_ref.set(state.model_dump())

    async def get_session(self, session_id: str) -> NegotiationStateModel:
        doc = await self._collection.document(session_id).get()
        if not doc.exists:
            raise SessionNotFoundError(session_id)
        return NegotiationStateModel(**doc.to_dict())

    async def update_session(self, session_id: str, updates: dict) -> None:
        doc_ref = self._collection.document(session_id)
        doc = await doc_ref.get()
        if not doc.exists:
            raise SessionNotFoundError(session_id)
        await doc_ref.update(updates)
```

The `get_firestore_client()` dependency function in `app/db/__init__.py` creates a module-level singleton:

```python
_client: FirestoreSessionClient | None = None

def get_firestore_client() -> FirestoreSessionClient:
    global _client
    if _client is None:
        _client = FirestoreSessionClient(project=settings.GOOGLE_CLOUD_PROJECT or None)
    return _client
```

Why a singleton: Firestore `AsyncClient` manages a gRPC channel pool internally. Creating a new client per request wastes connections and adds latency. The singleton is safe because `AsyncClient` is thread-safe and Cloud Run runs a single process per container.

### 4. SSE Event Formatting (`app/utils/sse.py`)

A single function that converts any Pydantic event model to the SSE wire format:

```python
def format_sse_event(event: BaseModel) -> str:
    return f"data: {event.model_dump_json()}\n\n"
```

This is intentionally minimal. The W3C SSE spec requires `data: <payload>\n\n`. We don't use the `event:` field (SSE named events) because the `event_type` discriminator inside the JSON payload already serves that purpose, and named events complicate EventSource reconnection logic on the frontend.

### 5. SSE Connection Tracker (`app/middleware/sse_limiter.py`)

```python
class SSEConnectionTracker:
    MAX_CONNECTIONS_PER_EMAIL = 3

    def __init__(self):
        self._active: dict[str, int] = defaultdict(int)
        self._lock = asyncio.Lock()

    async def acquire(self, email: str) -> bool:
        async with self._lock:
            if self._active[email] >= self.MAX_CONNECTIONS_PER_EMAIL:
                return False
            self._active[email] += 1
            return True

    async def release(self, email: str) -> None:
        async with self._lock:
            self._active[email] = max(0, self._active[email] - 1)
            if self._active[email] == 0:
                del self._active[email]  # prevent unbounded dict growth
```

Why `asyncio.Lock`: Multiple SSE connections can be opened concurrently on the same event loop. Without the lock, two near-simultaneous `acquire()` calls for the same email could both read count=2 and both increment to 3, allowing 4 connections. The lock serializes access. This is cheap — the critical section is a dict lookup and increment.

The tracker is instantiated as a module-level singleton (same pattern as the Firestore client) and injected via `Depends(get_sse_tracker)`.

### 6. SSE Stream Endpoint (`app/routers/negotiation.py`)

The endpoint orchestrates the full SSE lifecycle:

```
1. Validate email query param exists
2. Look up session in Firestore → 404 if not found
3. Validate email matches session owner → 403 if mismatch
4. Acquire SSE connection slot → 429 if limit reached
5. Return StreamingResponse wrapping the async generator
6. Generator:
   a. Compute timeout = max_turns * 30 seconds
   b. Await events from orchestrator (spec 030) with asyncio timeout
   c. For each event: yield format_sse_event(event)
   d. On terminal deal_status: yield NegotiationCompleteEvent, break
   e. On timeout: yield NegotiationCompleteEvent(deal_status="Failed"), break
   f. On exception: yield StreamErrorEvent, break
7. Finally: release SSE connection slot
```

The endpoint signature:

```python
@router.get("/negotiation/stream/{session_id}")
async def stream_negotiation(
    session_id: str,
    email: str = Query(...),
    db: FirestoreSessionClient = Depends(get_firestore_client),
    tracker: SSEConnectionTracker = Depends(get_sse_tracker),
):
```

The async generator is defined as a nested function inside the endpoint so it captures `session_id`, `email`, `db`, and `tracker` from the closure. The `finally` block guarantees `tracker.release(email)` runs even if the client disconnects mid-stream (Starlette detects disconnection and cancels the generator task).

#### Integration boundary with spec 030

This spec defines the SSE transport layer. The actual event production comes from spec 030's `run_negotiation(initial_state)` async generator. Until spec 030 is implemented, the SSE endpoint will use a placeholder generator that yields a few hardcoded events for testing:

```python
async def _placeholder_event_generator(state: NegotiationStateModel):
    """Temporary: replaced by orchestrator.run_negotiation() in spec 030."""
    yield AgentThoughtEvent(
        event_type="agent_thought", agent_name="Buyer",
        inner_thought="Analyzing the offer...", turn_number=0
    )
    await asyncio.sleep(0.5)
    yield AgentMessageEvent(
        event_type="agent_message", agent_name="Buyer",
        public_message="I propose €35M.", turn_number=0,
        proposed_price=35000000.0
    )
    yield NegotiationCompleteEvent(
        event_type="negotiation_complete", session_id=state.session_id,
        deal_status="Agreed", final_summary={"final_price": 35000000.0}
    )
```

This placeholder is swapped out when spec 030 lands. The SSE endpoint doesn't care what produces the events — it just iterates and serializes.

### 7. Session Document Schema (Firestore)

The `negotiation_sessions` collection stores one document per session:

```
negotiation_sessions/{session_id}
├── session_id: string
├── scenario_id: string
├── owner_email: string          # email that started the session (for SSE auth)
├── turn_count: number (0)
├── max_turns: number (15)
├── current_speaker: string ("Buyer")
├── deal_status: string ("Negotiating")
├── current_offer: number (0.0)
├── history: array ([])
├── warning_count: number (0)
├── hidden_context: map ({})
├── agreement_threshold: number (1000000.0)
├── active_toggles: array ([])
├── turn_order: array ([])           # agent role execution sequence per cycle
├── turn_order_index: number (0)     # current position in turn_order
├── agent_states: map ({})           # per-agent runtime state keyed by role
└── created_at: timestamp
```

Note: `owner_email` is not part of the `NegotiationStateModel` Pydantic model — it's written to the Firestore document by the `POST /api/v1/negotiation/start` endpoint (spec 050) and read by the SSE endpoint for ownership validation. The `NegotiationStateModel` stays focused on negotiation state; session metadata like `owner_email` and `created_at` are Firestore-only fields.

## Data Models

### Pydantic Models Summary

| Model | Module | Key Fields | Discriminator |
|---|---|---|---|
| `HealthResponse` | `models/health.py` | `status`, `version` | — |
| `NegotiationStateModel` | `models/negotiation.py` | `session_id`, `scenario_id`, `turn_count`, `max_turns`, `current_speaker`, `deal_status`, `current_offer`, `history`, `warning_count`, `hidden_context`, `agreement_threshold`, `active_toggles`, `turn_order`, `turn_order_index`, `agent_states` | — |
| `AgentThoughtEvent` | `models/events.py` | `event_type="agent_thought"`, `agent_name`, `inner_thought`, `turn_number` | `event_type` |
| `AgentMessageEvent` | `models/events.py` | `event_type="agent_message"`, `agent_name`, `public_message`, `turn_number`, `proposed_price?`, `retention_clause_demanded?`, `status?` | `event_type` |
| `NegotiationCompleteEvent` | `models/events.py` | `event_type="negotiation_complete"`, `session_id`, `deal_status`, `final_summary` | `event_type` |
| `StreamErrorEvent` | `models/events.py` | `event_type="error"`, `message` | `event_type` |

### NegotiationStateModel Field Constraints

| Field | Type | Default | Constraint |
|---|---|---|---|
| `session_id` | `str` | required | — |
| `scenario_id` | `str` | required | — |
| `turn_count` | `int` | `0` | `>= 0` |
| `max_turns` | `int` | `15` | `> 0` |
| `current_speaker` | `str` | `"Buyer"` | — |
| `deal_status` | `Literal[...]` | `"Negotiating"` | `"Negotiating"`, `"Agreed"`, `"Blocked"`, `"Failed"` |
| `current_offer` | `float` | `0.0` | `>= 0.0` |
| `history` | `list[dict[str, Any]]` | `[]` | — |
| `warning_count` | `int` | `0` | `>= 0` |
| `hidden_context` | `dict[str, Any]` | `{}` | — |
| `agreement_threshold` | `float` | `1000000.0` | `> 0.0` |
| `active_toggles` | `list[str]` | `[]` | — |
| `turn_order` | `list[str]` | `[]` | Agent role execution sequence per cycle |
| `turn_order_index` | `int` | `0` | Current position in turn_order |
| `agent_states` | `dict[str, dict[str, Any]]` | `{}` | Per-agent runtime state (keyed by role) |

## Correctness Properties

### Property 1: SSE event format compliance

*For any* valid Pydantic event model instance (AgentThoughtEvent, AgentMessageEvent, NegotiationCompleteEvent, StreamErrorEvent), the output of `format_sse_event(event)` must: (a) start with `data: `, (b) end with `\n\n`, (c) contain valid JSON between the prefix and suffix, and (d) the parsed JSON must contain an `event_type` field matching the model's literal type.

**Validates: Requirements 5.4, 5.5, 5.6**

### Property 2: Pydantic model round-trip serialization

*For any* valid `NegotiationStateModel` instance, `NegotiationStateModel(**json.loads(instance.model_dump_json()))` must produce an object equal to the original. The same property must hold for all four SSE event models.

**Validates: Requirements 3.13, 6.5**

### Property 3: SSE connection tracker invariant

*For any* sequence of `acquire(email)` and `release(email)` calls on an `SSEConnectionTracker`, the active count for any email must always be in the range `[0, MAX_CONNECTIONS_PER_EMAIL]`. Specifically: (a) `acquire` must return `False` without incrementing when count equals `MAX_CONNECTIONS_PER_EMAIL`, (b) `release` must never decrement below 0, (c) counts for different emails must be independent.

**Validates: Requirements 7.1, 7.2, 7.5**

### Property 4: Firestore session round-trip

*For any* valid `NegotiationStateModel` instance, writing it via `create_session(state)` then reading it back via `get_session(state.session_id)` must produce an equivalent `NegotiationStateModel` object. Fields not in the Pydantic model (e.g., `owner_email`, `created_at`) are ignored in the comparison.

**Validates: Requirements 4.3, 4.4, 4.8**

### Property 5: deal_status constraint enforcement

*For any* attempt to construct a `NegotiationStateModel` with a `deal_status` value not in `{"Negotiating", "Agreed", "Blocked", "Failed"}`, Pydantic must raise a `ValidationError`. No invalid status value can exist in a model instance.

**Validates: Requirement 3.6**

## Error Handling

### Exception Hierarchy

| Exception | Raised By | HTTP Status | Response Body |
|---|---|---|---|
| `SessionNotFoundError(session_id)` | `FirestoreSessionClient` | 404 | `{"detail": "Session {session_id} not found"}` |
| `FirestoreConnectionError(message)` | `FirestoreSessionClient.__init__` | 503 | `{"detail": "Database unavailable"}` |
| Rate limit exceeded | `SSEConnectionTracker` | 429 | `{"detail": "Concurrent SSE connection limit reached (max 3)"}` |
| Email mismatch | SSE endpoint | 403 | `{"detail": "Email does not match session owner"}` |
| Stream timeout | SSE generator | — | SSE event: `NegotiationCompleteEvent(deal_status="Failed")` |
| Unexpected stream error | SSE generator | — | SSE event: `StreamErrorEvent(message=...)` |

### Exception-to-HTTP mapping

FastAPI exception handlers are registered in `main.py` to convert domain exceptions to HTTP responses:

```python
@app.exception_handler(SessionNotFoundError)
async def session_not_found_handler(request, exc):
    return JSONResponse(status_code=404, content={"detail": str(exc)})

@app.exception_handler(FirestoreConnectionError)
async def firestore_connection_handler(request, exc):
    return JSONResponse(status_code=503, content={"detail": "Database unavailable"})
```

### SSE stream error lifecycle

Errors during streaming cannot return HTTP error codes (the 200 response is already sent). Instead:

1. Catch the exception inside the async generator
2. Yield a `StreamErrorEvent` with a sanitized message (no stack traces to the client)
3. Log the full exception server-side with `session_id` for debugging
4. Break out of the generator (triggers the `finally` block → `tracker.release()`)

## Testing Strategy

### Unit Tests (Example-Based)

Unit tests verify specific, concrete expectations about individual components in isolation. External services (Firestore SDK, Vertex AI) are mocked.

**Framework:** `pytest` + `pytest-asyncio` for async tests, `unittest.mock` for mocking.

**Key test areas:**

- `test_models.py`: Default values, `deal_status` validation rejects invalid values, all SSE event models instantiate correctly
- `test_exceptions.py`: `SessionNotFoundError` and `FirestoreConnectionError` message formatting
- `test_sse_limiter.py`: `acquire` succeeds up to 3 times, 4th returns `False`, `release` decrements, floor at 0, independent email tracking
- `test_sse_format.py`: `format_sse_event` produces correct `data: <JSON>\n\n` for each event type, JSON is parseable, contains `event_type`
- `test_health.py` (integration): `GET /api/v1/health` returns 200 with correct body via `TestClient`
- `test_stream.py` (integration): 404 on unknown session, 429 on limit exceeded, 403 on email mismatch, successful stream returns `text/event-stream` content type

### Property-Based Tests

Property-based tests verify universal invariants across generated inputs. Use `hypothesis` as the PBT library.

Each property test must run a minimum of 100 iterations and be tagged with a comment referencing the design property.

**Property tests to implement:**

1. **Feature: 020_a2a-backend-core-sse, Property 1: SSE event format compliance**
   - Generate random valid instances of each SSE event model using `hypothesis` strategies
   - Assert `format_sse_event()` output starts with `data: `, ends with `\n\n`, contains valid JSON with correct `event_type`

2. **Feature: 020_a2a-backend-core-sse, Property 2: Pydantic model round-trip serialization**
   - Generate random valid `NegotiationStateModel` instances (random strings for IDs, random ints for counts, random floats for offers, random deal_status from valid set)
   - Assert `model_dump_json()` → `model_validate_json()` round-trip produces equal objects
   - Same for all four SSE event models

3. **Feature: 020_a2a-backend-core-sse, Property 3: SSE connection tracker invariant**
   - Generate random sequences of `(acquire, email)` and `(release, email)` operations
   - Replay the sequence against an `SSEConnectionTracker` instance
   - Assert active count never exceeds `MAX_CONNECTIONS_PER_EMAIL` and never goes below 0

4. **Feature: 020_a2a-backend-core-sse, Property 5: deal_status constraint enforcement**
   - Generate random strings
   - Assert `NegotiationStateModel(session_id=..., scenario_id=..., deal_status=random_string)` raises `ValidationError` for any string not in the valid set

**Configuration:**
- Library: `hypothesis`
- Min iterations: 100 per property (`@settings(max_examples=100)`)
- Each test tagged: `# Feature: 020_a2a-backend-core-sse, Property N: <title>`
