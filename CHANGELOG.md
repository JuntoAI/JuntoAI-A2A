# Changelog

All notable changes to the JuntoAI A2A Protocol Sandbox are documented here.

Each entry corresponds to a completed spec — shipped when the last task was finished.

---

## Hybrid Agent Memory (Spec 110) — 2026-04-04

- Milestone summary generator: lightweight LLM call per agent at configurable turn intervals produces ≤300-token strategic summaries capturing key positions, concessions, disputes, and trajectory
- Configurable sliding window: `sliding_window_size` scenario parameter (default 3) replaces hardcoded window from spec 100
- Full history elimination: after first milestone, prompt builder excludes all raw history beyond the sliding window — token cost per turn becomes bounded regardless of negotiation length
- `milestone_interval` scenario parameter (default 4) controls turn cycles between summary generations
- Milestone summaries include agent-private reasoning context (inner thoughts, strategy) for perspective-aware compression
- Non-blocking failure: LLM failure for one agent's summary does not block other agents or the negotiation
- Dispatcher integration: milestone generation triggers after turn advancement, before next agent node runs
- "Milestone Summaries" toggle in Advanced Options — visually disabled when structured memory is off, auto-enables structured memory when toggled on
- Server-side dependency enforcement: `milestone_summaries_enabled=True` forces `structured_memory_enabled=True` regardless of request payload
- Full backward compatibility: disabled by default, missing fields default safely, existing sessions and scenario JSONs unaffected
- Property tests: NegotiationParams round-trip, state initialization invariants, milestone serialization round-trip, prompt token boundedness

## Structured Agent Memory (Spec 100) — 2026-04-03

- Per-agent `AgentMemory` Pydantic V2 model: typed fields for offer history, concessions, open items, tactics, red lines, compliance status, and turn count
- Memory-aware prompt builder: structured memory + sliding window of last 3 messages replaces full history transcript when enabled
- Deterministic memory extraction in `_update_state`: appends offers, tracks opposing offers, increments turn count — no extra LLM calls
- Stall detector reads `my_offers` directly from `agent_memories` when enabled, bypassing full history re-parsing
- `structured_memory_enabled` flag threaded through `NegotiationState`, `NegotiationStateModel`, `StartNegotiationRequest`, and Firestore persistence
- Collapsible "Advanced Options" section on Arena Selector with labeled toggle for structured agent memory
- Full backward compatibility: disabled by default, missing fields default to `False`/`{}`, existing sessions unaffected
- Property tests: AgentMemory round-trip, JSON serializability, state initialization, converter round-trip, prompt format, memory extraction, opposing offer capture, stall detector equivalence

## A2A Local Battle Arena (Spec 080) — 2026-04-03

- Dual-mode architecture: single `RUN_MODE` env var switches between cloud (GCP) and local (Docker) with zero code changes
- `SessionStore` protocol abstracting Firestore and SQLite — implementations swappable at runtime
- `SQLiteSessionClient` with aiosqlite for zero-cloud-config local persistence
- LiteLLM-based model router for local mode — supports OpenAI, Anthropic, and Ollama providers
- Ollama Docker Compose sidecar with auto-pull init service — working LLM out of the box, no API keys needed
- Transparent model mapping: scenario `model_id` values (e.g., `gemini-2.5-flash`) resolve to local provider equivalents
- `LLM_MODEL_OVERRIDE` and `MODEL_MAP` env vars for full model routing control
- Auth gate bypass in local mode — no waitlist, no token limits, no email validation
- Lazy GCP imports — local mode starts without any Google Cloud SDK packages installed
- `docker-compose.yml` with backend, frontend, ollama, and ollama-pull services (health checks, named volumes)
- Frontend `NEXT_PUBLIC_RUN_MODE` detection — skips landing page and hides token counter in local mode
- `.env.example` with grouped variables, inline docs, and zero-config Ollama defaults
- Property tests: session round-trip, missing session errors, update merge, model mapping validity, override precedence, Ollama model resolution, Ollama no-API-key requirement, RUN_MODE validation, HTTP 503 on DatabaseConnectionError, scenario state identity across modes

## World-Class README & Contributor Hub (Spec 120) — 2026-04-02

- Monorepo root README (~800 lines) with badges, Kiro callout, hero description, and anchor-linked TOC
- Mermaid architecture diagram showing scenario config → orchestrator → agents → SSE → Glass Box UI data flow
- Quick Start guide: clone, `.env.example`, `docker compose up`, localhost:3000 in under 5 minutes
- Local Battle Arena section with cloud-vs-local comparison table and model mapping docs (`LLM_PROVIDER`, `LLM_MODEL_OVERRIDE`, `MODEL_MAP`)
- Environment configuration reference table grouped by category with provider-specific examples (OpenAI, Anthropic, Ollama)
- "Connect Your Own Agents" guide: scenario JSON schema, agent object schema, copyable example config, LiteLLM routing
- Leaderboard teaser (Coming Soon) with evaluation dimensions: deal outcome, efficiency, humanization, compliance
- "Developing with Kiro" section documenting `.kiro/` directory structure (steering, specs, hooks)
- Contributing guidelines: fork → `feature/*` → PR to `main`, JSON-only scenario contributions
- GitHub CTA section on landing page with accessible link to GitHub org
- GitHub icon added to footer social icons row (LinkedIn, GitHub, X)
- Property tests: README structure validation (Python/pytest), frontend accessibility (Vitest/fast-check)

## Agent Advanced Configuration (Spec 090) — 2026-04-02

- "Advanced Config" button on each agent card with settings icon and active-state indicator
- Modal interface for per-agent custom prompt injection (free-text, 500 char limit with live counter)
- Model Selector dropdown populated from `GET /api/v1/models` — override any agent's default LLM
- Custom prompts appended to agent system messages with clear delimiter; model overrides routed through Model Router
- Backend validation: HTTP 422 on oversized prompts or unrecognized model IDs
- State management: overrides persist within a session, reset on scenario change
- Responsive modal layout — bottom sheet on mobile, centered dialog on desktop

## Glass Box Simulation UI (Spec 060) — 2026-04-01

- Arena Selector with scenario dropdown, agent cards, and information toggles
- Terminal Panel — dark monospace display for agent inner thoughts
- Chat Panel — color-coded bubbles for public messages (N-agent compatible)
- Metrics Dashboard — live current offer, regulator traffic lights, turn counter
- SSE client with auto-reconnect and typed event dispatch
- Outcome Receipt with deal summary, ROI metrics, and replay CTAs
- Responsive layout: side-by-side ≥1024px, stacked on mobile

## CI/CD Pipelines (Spec 070) — 2026-04-01

- Google Cloud Build pipeline (`cloudbuild.yaml`) with substitution variables
- Parallel Docker builds for backend and frontend
- Automatic push to Artifact Registry (commit SHA + `latest` tags)
- Cloud Run deployment with service account identity
- Cloud Build trigger on `main` branch (Terragrunt-managed)
- Least-privilege Cloud Build SA permissions

## Frontend Gate & Waitlist (Spec 050) — 2026-04-01

- Next.js 14 App Router with Tailwind CSS and Lucide React
- High-conversion landing page with value proposition
- Email waitlist form with Firestore persistence
- Access gate — sandbox routes protected behind email capture
- Token system: 100 tokens/day per email, midnight UTC reset
- Server-side token deduction via atomic Firestore operations
- Firestore security rules preventing client-side token manipulation

## Scenario Config Engine (Spec 040) — 2026-04-01

- JSON schema for Arena Scenarios with full validation
- Scenario loader with typed error hierarchy
- Auto-discovery registry — drop a `.scenario.json` file, zero code changes
- Toggle injector for information asymmetry (hidden context per agent role)
- Pretty printer with round-trip integrity
- 3 MVP scenarios: Talent War, M&A Buyout, Enterprise B2B Sales
- REST endpoints: `GET /api/v1/scenarios`, `GET /api/v1/scenarios/{id}`

## LangGraph Orchestration (Spec 030) — 2026-04-01

- LangGraph state machine with config-driven N-agent turn-based protocol
- Generic AgentNode factory — zero code changes to add new agent roles
- Dynamic graph construction from scenario JSON (no hardcoded role names)
- Dispatcher-based routing with conditional edges
- Vertex AI Model Router: Gemini 2.5 Flash, Claude 3.5 Sonnet, Claude Sonnet 4, Gemini 2.5 Pro
- Fallback model support with configurable timeouts
- Typed output parsing: `NegotiatorOutput`, `RegulatorOutput`, `ObserverOutput`
- N-agent termination: price convergence, max turns, regulator block
- Bidirectional state conversion (LangGraph TypedDict ↔ Pydantic)

## Backend Core & SSE Streaming (Spec 020) — 2026-04-01

- FastAPI application with Pydantic V2 validation and `/api/v1` prefix
- CORS middleware with configurable origins
- Health check endpoint (`GET /api/v1/health`) for Cloud Run probes
- NegotiationState Pydantic model with N-agent support
- Firestore client module for session CRUD with typed errors
- SSE streaming endpoint (`GET /api/v1/negotiation/stream/{session_id}`)
- Typed SSE event models: `agent_thought`, `agent_message`, `negotiation_complete`, `error`
- Rate limiting — max 3 concurrent SSE connections per email

## GCP Infrastructure (Spec 010) — 2026-03-31

- Monorepo scaffolding with `/infra`, `/backend`, `/frontend`, `/docs` directories
- Terragrunt-managed remote state on GCS with native locking
- Cloud Run services for backend (FastAPI) and frontend (Next.js)
- Artifact Registry Docker repository for container images
- Firestore Native mode database for sessions and waitlist
- Vertex AI API enabled for foundation model access
- Least-privilege IAM service accounts (Backend_SA, Frontend_SA)
