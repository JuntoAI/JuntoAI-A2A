# Changelog

All notable changes to the JuntoAI A2A Protocol Sandbox are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.0.0] — 2026-04-01

First production release of the JuntoAI A2A Protocol Sandbox — a config-driven scenario engine where autonomous AI agents negotiate in real time.

### Added

#### GCP Infrastructure (Spec 010)
- Monorepo scaffolding with `/infra`, `/backend`, `/frontend`, `/docs` directories
- Terragrunt-managed remote state on GCS with native locking
- Cloud Run services for backend (FastAPI) and frontend (Next.js)
- Artifact Registry Docker repository for container images
- Firestore Native mode database for sessions and waitlist
- Vertex AI API enabled for foundation model access
- Least-privilege IAM service accounts (Backend_SA, Frontend_SA)

#### Backend Core & SSE Streaming (Spec 020)
- FastAPI application with Pydantic V2 validation and `/api/v1` prefix
- CORS middleware with configurable origins
- Health check endpoint (`GET /api/v1/health`) for Cloud Run probes
- NegotiationState Pydantic model with N-agent support
- Firestore client module for session CRUD with typed errors
- SSE streaming endpoint (`GET /api/v1/negotiation/stream/{session_id}`)
- Typed SSE event models: `agent_thought`, `agent_message`, `negotiation_complete`, `error`
- Rate limiting — max 3 concurrent SSE connections per email

#### LangGraph Orchestration (Spec 030)
- LangGraph state machine with config-driven N-agent turn-based protocol
- Generic AgentNode factory — zero code changes to add new agent roles
- Dynamic graph construction from scenario JSON (no hardcoded role names)
- Dispatcher-based routing with conditional edges
- Vertex AI Model Router: Gemini 2.5 Flash, Claude 3.5 Sonnet, Claude Sonnet 4, Gemini 2.5 Pro
- Fallback model support with configurable timeouts
- Typed output parsing: `NegotiatorOutput`, `RegulatorOutput`, `ObserverOutput`
- N-agent termination: price convergence, max turns, regulator block
- Bidirectional state conversion (LangGraph TypedDict ↔ Pydantic)

#### Scenario Config Engine (Spec 040)
- JSON schema for Arena Scenarios with full validation
- Scenario loader with typed error hierarchy
- Auto-discovery registry — drop a `.scenario.json` file, zero code changes
- Toggle injector for information asymmetry (hidden context per agent role)
- Pretty printer with round-trip integrity
- 3 MVP scenarios: Talent War, M&A Buyout, Enterprise B2B Sales
- REST endpoints: `GET /api/v1/scenarios`, `GET /api/v1/scenarios/{id}`

#### Frontend Gate & Waitlist (Spec 050)
- Next.js 14 App Router with Tailwind CSS and Lucide React
- High-conversion landing page with value proposition
- Email waitlist form with Firestore persistence
- Access gate — sandbox routes protected behind email capture
- Token system: 100 tokens/day per email, midnight UTC reset
- Server-side token deduction via atomic Firestore operations
- Firestore security rules preventing client-side token manipulation

#### Glass Box Simulation UI (Spec 060)
- Arena Selector with scenario dropdown, agent cards, and information toggles
- Terminal Panel — dark monospace display for agent inner thoughts
- Chat Panel — color-coded bubbles for public messages (N-agent compatible)
- Metrics Dashboard — live current offer, regulator traffic lights, turn counter
- SSE client with auto-reconnect and typed event dispatch
- Outcome Receipt with deal summary, ROI metrics, and replay CTAs
- Responsive layout: side-by-side ≥1024px, stacked on mobile

#### CI/CD Pipelines (Spec 070)
- Google Cloud Build pipeline (`cloudbuild.yaml`) with substitution variables
- Parallel Docker builds for backend and frontend
- Automatic push to Artifact Registry (commit SHA + `latest` tags)
- Cloud Run deployment with service account identity
- Cloud Build trigger on `main` branch (Terragrunt-managed)
- Least-privilege Cloud Build SA permissions
