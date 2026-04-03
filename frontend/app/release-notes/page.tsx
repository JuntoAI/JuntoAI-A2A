import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Release Notes — JuntoAI A2A Protocol Sandbox",
  description:
    "A continuous stream of features shipped in the JuntoAI A2A Protocol Sandbox.",
};

const FEATURES = [
  {
    title: "A2A Local Battle Arena",
    specId: "080",
    date: "2026-04-03",
    items: [
      "Dual-mode architecture: single RUN_MODE env var switches between cloud (GCP) and local (Docker)",
      "SessionStore protocol abstracting Firestore and SQLite — swappable at runtime",
      "SQLiteSessionClient with aiosqlite for zero-cloud-config local persistence",
      "LiteLLM-based model router for local mode — supports OpenAI, Anthropic, and Ollama",
      "Ollama Docker Compose sidecar with auto-pull init service — no API keys needed",
      "Transparent model mapping: scenario model_id values resolve to local provider equivalents",
      "LLM_MODEL_OVERRIDE and MODEL_MAP env vars for full model routing control",
      "Auth gate bypass in local mode — no waitlist, no token limits, no email validation",
      "Lazy GCP imports — local mode starts without Google Cloud SDK packages",
      "docker-compose.yml with backend, frontend, ollama, and ollama-pull services",
      "Frontend NEXT_PUBLIC_RUN_MODE detection — skips landing page in local mode",
      ".env.example with grouped variables, inline docs, and zero-config Ollama defaults",
    ],
  },
  {
    title: "World-Class README & Contributor Hub",
    specId: "120",
    date: "2026-04-02",
    items: [
      "Monorepo root README with badges, Kiro callout, hero description, and anchor-linked TOC",
      "Mermaid architecture diagram showing scenario config → orchestrator → agents → SSE → Glass Box UI",
      "Quick Start guide: clone, .env.example, docker compose up, localhost:3000 in under 5 minutes",
      "Local Battle Arena section with cloud-vs-local comparison table and model mapping docs",
      "Environment configuration reference table grouped by category with provider-specific examples",
      "Connect Your Own Agents guide: scenario JSON schema, agent object schema, copyable example, LiteLLM routing",
      "Developing with Kiro section documenting .kiro/ directory structure (steering, specs, hooks)",
      "GitHub CTA on landing page and GitHub icon in footer social icons row",
      "Property tests: README structure validation (pytest) and frontend accessibility (Vitest/fast-check)",
    ],
  },
  {
    title: "Agent Advanced Configuration",
    specId: "090",
    date: "2026-04-02",
    items: [
      "Advanced Config button on each agent card with settings icon and active-state indicator",
      "Modal interface for per-agent custom prompt injection (free-text, 500 char limit with live counter)",
      "Model Selector dropdown populated from GET /api/v1/models — override any agent's default LLM",
      "Custom prompts appended to agent system messages with clear delimiter, model overrides routed through Model Router",
      "Backend validation: 422 on oversized prompts or unrecognized model IDs",
      "State management: overrides persist within a session, reset on scenario change",
      "Responsive modal layout — bottom sheet on mobile, centered dialog on desktop",
    ],
  },
  {
    title: "Glass Box Simulation UI",
    specId: "060",
    date: "2026-04-01",
    items: [
      "Arena Selector with scenario dropdown, agent cards, and information toggles",
      "Terminal Panel — dark monospace display for agent inner thoughts",
      "Chat Panel — color-coded bubbles for public messages (N-agent compatible)",
      "Metrics Dashboard — live current offer, regulator traffic lights, turn counter, token balance",
      "SSE client with auto-reconnect and typed event dispatch",
      "Outcome Receipt with deal summary, ROI metrics, and replay CTAs",
      "Responsive layout: side-by-side ≥1024px, stacked on mobile",
    ],
  },
  {
    title: "CI/CD Pipelines",
    specId: "070",
    date: "2026-04-01",
    items: [
      "Google Cloud Build pipeline (cloudbuild.yaml) with substitution variables",
      "Parallel Docker builds for backend and frontend",
      "Automatic push to Artifact Registry (commit SHA + latest tags)",
      "Cloud Run deployment for both services with service account identity",
      "Cloud Build trigger on main branch (Terragrunt-managed)",
      "Least-privilege Cloud Build SA (artifactregistry.writer, run.admin, iam.serviceAccountUser)",
    ],
  },
  {
    title: "Frontend Gate & Waitlist",
    specId: "050",
    date: "2026-04-01",
    items: [
      "Next.js 14 App Router with Tailwind CSS and Lucide React",
      "High-conversion landing page with value proposition and scenario banner",
      "Email waitlist form with Firestore persistence",
      "Access gate — all sandbox routes protected behind email capture",
      "Token system: 100 tokens/day per email, midnight UTC reset",
      "Server-side token deduction via atomic Firestore operations",
      "Firestore security rules preventing client-side token manipulation",
    ],
  },
  {
    title: "Scenario Config Engine",
    specId: "040",
    date: "2026-04-01",
    items: [
      "JSON schema for Arena Scenarios with full validation",
      "Scenario loader with typed error hierarchy (parse, validation, not-found)",
      "Auto-discovery registry — drop a .scenario.json file, zero code changes",
      "Toggle injector for information asymmetry (hidden context per agent role)",
      "Pretty printer with round-trip integrity",
      "3 MVP scenarios: Talent War, M&A Buyout, Enterprise B2B Sales",
      "REST endpoints: GET /api/v1/scenarios, GET /api/v1/scenarios/{id}",
    ],
  },
  {
    title: "LangGraph Orchestration",
    specId: "030",
    date: "2026-04-01",
    items: [
      "LangGraph state machine with config-driven N-agent turn-based protocol",
      "Generic AgentNode factory — zero code changes to add new agent roles",
      "Dynamic graph construction from scenario JSON (no hardcoded role names)",
      "Dispatcher-based routing with conditional edges",
      "Vertex AI Model Router supporting Gemini 2.5 Flash, Claude 3.5 Sonnet, Claude Sonnet 4, Gemini 2.5 Pro",
      "Fallback model support with configurable timeouts",
      "Typed output parsing by agent type: NegotiatorOutput, RegulatorOutput, ObserverOutput",
      "N-agent termination: price convergence, max turns, regulator block (3 warnings = blocked)",
      "Bidirectional state conversion between LangGraph TypedDict and Pydantic models",
    ],
  },
  {
    title: "Backend Core & SSE Streaming",
    specId: "020",
    date: "2026-04-01",
    items: [
      "FastAPI application with Pydantic V2 validation and versioned /api/v1 prefix",
      "CORS middleware with configurable origins",
      "Health check endpoint (GET /api/v1/health) for Cloud Run probes",
      "NegotiationState Pydantic model with N-agent support and round-trip serialization",
      "Firestore client module for session CRUD with typed error handling",
      "SSE streaming endpoint (GET /api/v1/negotiation/stream/{session_id})",
      "Typed SSE event models: agent_thought, agent_message, negotiation_complete, error",
      "Rate limiting — max 3 concurrent SSE connections per email",
    ],
  },
  {
    title: "GCP Infrastructure",
    specId: "010",
    date: "2026-03-31",
    items: [
      "Monorepo scaffolding with /infra, /backend, /frontend, /docs directories",
      "Terragrunt-managed remote state on GCS with native locking",
      "Cloud Run services provisioned for backend (FastAPI) and frontend (Next.js)",
      "Artifact Registry Docker repository for container images",
      "Firestore Native mode database for sessions and waitlist",
      "Vertex AI API enabled for foundation model access",
      "Least-privilege IAM service accounts (Backend_SA, Frontend_SA)",
      "All resource identifiers exported as Terragrunt module outputs",
    ],
  },
] as const;

export default function ReleaseNotesPage() {
  return (
    <main className="min-h-screen bg-brand-offwhite px-4 py-16 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-3xl">
        <Link
          href="/"
          className="mb-8 inline-flex items-center text-sm text-brand-blue hover:underline"
        >
          ← Back to Home
        </Link>

        <h1 className="text-3xl font-bold tracking-tight text-brand-charcoal sm:text-4xl">
          Release Notes
        </h1>
        <p className="mt-2 text-brand-charcoal/60">
          A continuous stream of features shipped in the JuntoAI A2A Protocol
          Sandbox.
        </p>

        <div className="mt-10 space-y-10">
          {FEATURES.map((feature) => (
            <article key={feature.specId}>
              <div className="flex items-baseline gap-3">
                <h2 className="text-xl font-semibold text-brand-charcoal">
                  {feature.title}
                </h2>
                <time
                  dateTime={feature.date}
                  className="text-sm text-brand-charcoal/50"
                >
                  {new Date(feature.date + "T00:00:00").toLocaleDateString(
                    "en-US",
                    { year: "numeric", month: "long", day: "numeric" }
                  )}
                </time>
              </div>

              <ul className="mt-3 space-y-1 text-sm text-brand-charcoal/70">
                {feature.items.map((item, i) => (
                  <li key={i} className="flex items-start gap-2">
                    <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-brand-green" />
                    {item}
                  </li>
                ))}
              </ul>
            </article>
          ))}
        </div>
      </div>
    </main>
  );
}
