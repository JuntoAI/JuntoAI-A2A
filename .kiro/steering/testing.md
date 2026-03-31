# JuntoAI A2A MVP — Testing Guidelines

## Coverage Target
70% minimum (lines, functions, branches, statements).

## Backend (Python)
- **Framework**: pytest + pytest-asyncio
- **Coverage**: pytest-cov with 70% threshold
- **Mocking**: `unittest.mock` for Firestore SDK, Vertex AI SDK
- **Key test areas**: Pydantic model validation, Firestore CRUD, SSE event formatting, LangGraph state transitions, scenario JSON parsing, toggle injection
- **Run**: `cd backend && pytest --cov=app --cov-fail-under=70`

## Frontend (Next.js)
- **Framework**: Vitest + React Testing Library
- **Coverage**: @vitest/coverage-v8 with 70% threshold
- **Environment**: jsdom for component tests
- **Key test areas**: Waitlist form validation, token system logic, SSE client parsing, scenario selector, Glass Box event rendering
- **Run**: `cd frontend && npx vitest run --coverage`

## Test Structure
```
backend/tests/
├── unit/           # Pydantic models, scenario parser, toggle injector
├── integration/    # FastAPI endpoints (TestClient), Firestore operations
└── conftest.py     # Shared fixtures

frontend/__tests__/
├── components/     # React component tests
├── lib/            # Firebase client, SSE client, token system
└── setup.ts        # Vitest setup
```

## Principles
- Mock only external services (Firestore SDK, Vertex AI SDK, Firebase JS SDK)
- Import actual business logic modules, not mocks
- Zero-flake policy — tests must be deterministic
- Use round-trip property tests for Pydantic models and JSON serialization
- SSE tests should verify `data: <JSON>\n\n` format compliance

## CI Integration
- Tests run in Cloud Build pipeline before deploy
- Coverage reports uploaded as build artifacts
- All tests must pass before deployment proceeds
