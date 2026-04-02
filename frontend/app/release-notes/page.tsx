import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Release Notes — JuntoAI A2A Protocol Sandbox",
  description:
    "What shipped in JuntoAI A2A v1.0 — infrastructure, backend, orchestration, scenarios, frontend, and CI/CD.",
};

const RELEASES = [
  {
    version: "1.0.0",
    date: "2026-04-01",
    summary:
      "First production release of the JuntoAI A2A Protocol Sandbox — a config-driven scenario engine where autonomous AI agents negotiate in real time.",
    sections: [
      {
        title: "GCP Infrastructure",
        specId: "010",
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
      {
        title: "Backend Core & SSE Streaming",
        specId: "020",
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
        title: "LangGraph Orchestration",
        specId: "030",
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
        title: "Scenario Config Engine",
        specId: "040",
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
        title: "Frontend Gate & Waitlist",
        specId: "050",
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
        title: "Glass Box Simulation UI",
        specId: "060",
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
        items: [
          "Google Cloud Build pipeline (cloudbuild.yaml) with substitution variables",
          "Parallel Docker builds for backend and frontend",
          "Automatic push to Artifact Registry (commit SHA + latest tags)",
          "Cloud Run deployment for both services with service account identity",
          "Cloud Build trigger on main branch (Terragrunt-managed)",
          "Least-privilege Cloud Build SA (artifactregistry.writer, run.admin, iam.serviceAccountUser)",
        ],
      },
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
          What shipped in the JuntoAI A2A Protocol Sandbox.
        </p>

        <div className="mt-10 space-y-12">
          {RELEASES.map((release) => (
            <article key={release.version}>
              <div className="flex items-baseline gap-3">
                <h2 className="text-2xl font-semibold text-brand-charcoal">
                  v{release.version}
                </h2>
                <time
                  dateTime={release.date}
                  className="text-sm text-brand-charcoal/50"
                >
                  {new Date(release.date + "T00:00:00").toLocaleDateString(
                    "en-US",
                    { year: "numeric", month: "long", day: "numeric" }
                  )}
                </time>
              </div>

              <p className="mt-2 text-brand-charcoal/70">{release.summary}</p>

              <div className="mt-6 space-y-6">
                {release.sections.map((section) => (
                  <div key={section.specId}>
                    <h3 className="text-lg font-medium text-brand-charcoal">
                      {section.title}
                    </h3>
                    <ul className="mt-2 space-y-1 text-sm text-brand-charcoal/70">
                      {section.items.map((item, i) => (
                        <li key={i} className="flex items-start gap-2">
                          <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-brand-green" />
                          {item}
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
            </article>
          ))}
        </div>
      </div>
    </main>
  );
}
