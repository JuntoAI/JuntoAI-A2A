# JuntoAI A2A MVP — Testing Guidelines

## Coverage Target
70% minimum (lines, functions, branches, statements).
Current: Backend ~92%, Frontend ~74% across all metrics.

## Backend (Python)
- **Framework**: pytest + pytest-asyncio
- **Property tests**: Hypothesis (`@given`, `@settings`)
- **Coverage**: pytest-cov with 70% threshold
- **Mocking**: `unittest.mock` for Firestore SDK, Vertex AI SDK, LiteLLM
- **Markers**: `unit`, `integration`, `property`, `slow` — run selectively via `pytest -m unit`
- **Key test areas**: SSE event formatting, model mapping, auth service, database clients (SQLite + Firestore), profile client, middleware (event buffer, SSE limiter), evaluator/evaluator prompts, confirmation node, milestone generator, scenario loader/registry/toggle injector, Pydantic model validation, LangGraph state transitions
- **Run**: `cd backend && pytest --cov=app --cov-fail-under=70`
- **Selective**: `pytest -m unit` (fast), `pytest -m "not slow"` (skip Hypothesis-heavy tests)

## Frontend (Next.js)
- **Framework**: Vitest + React Testing Library
- **Coverage**: @vitest/coverage-v8 with 70% threshold
- **Environment**: jsdom for component tests
- **Key test areas**: Auth API client, profile API client, waitlist form, token display, start negotiation button, cookie banner, scenario banner, arena components, Glass Box panels, SSE client parsing, middleware, admin pages, session context
- **Run**: `cd frontend && npx vitest run --coverage`

## Test Structure
```
backend/tests/
├── unit/               # Pure logic, mocked deps
│   └── orchestrator/   # Evaluator, confirmation, milestones, agent node, state
├── integration/        # FastAPI endpoints (httpx AsyncClient)
├── property/           # Hypothesis property-based tests
└── conftest.py         # Shared fixtures (mock Firestore, sample payloads, history)

frontend/__tests__/
├── components/         # React component tests (RTL)
│   ├── arena/          # Arena selector, agent cards, toggles
│   └── glassbox/       # Chat panel, metrics, outcome receipt
├── context/            # SessionContext tests
├── lib/                # API clients (auth, profile, waitlist, tokens, SSE)
├── middleware/          # Next.js middleware tests
└── setup.ts            # Vitest setup
```

## Principles
- Mock only external services (Firestore SDK, Vertex AI SDK, LiteLLM, Firebase JS SDK, `global.fetch`)
- Import actual business logic modules, not mocks
- Zero-flake policy — tests must be deterministic
- Use `--hypothesis-seed` for reproducible property tests in CI
- Use round-trip property tests for Pydantic models, SQLite sessions, password hashing, event buffer replay
- SSE tests must verify `data: <JSON>\n\n` format compliance
- Use in-memory SQLite (`:memory:`) for database client tests
- Mark slow tests with `@pytest.mark.slow`

## CI Integration
- PR tests run via GitHub Actions (`.github/workflows/pr-tests.yml`)
- Backend: `pytest --cov=app --cov-fail-under=70 -x -q`
- Frontend: `npx vitest run --coverage`
- All tests must pass before merge
