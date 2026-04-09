import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Release Notes | JuntoAI A2A Protocol Sandbox",
  description:
    "A continuous stream of features shipped in the JuntoAI A2A Protocol Sandbox.",
};

const FEATURES = [
  {
    title: "LLM Availability Checker",
    specId: "310",
    date: "2026-04-09",
    items: [
      "Model registry extended with gemini-3.1-pro-preview and gemini-3.1-flash-lite-preview — VALID_MODEL_IDS, MODELS_PROMPT_BLOCK, and DEFAULT_MODEL_MAP derive automatically",
      "Startup availability probe: concurrent asyncio.gather probes of all registered models via Vertex AI (cloud) or LiteLLM (local) with configurable 15s timeout",
      "ProbeResult and AllowedModels frozen dataclasses — immutable after construction, stored in app.state.allowed_models for dependency injection",
      "Zero-model degraded mode: application starts with empty allowed list and degraded health status instead of crashing",
      "/api/v1/models endpoint returns only verified-working models from the Allowed Models List",
      "Scenario registry available boolean flag: validates each agent's model_id and fallback_model_id against allowed set at load time",
      "Builder prompt block filtered to allowed models only — generated scenarios reference only reachable LLMs",
      "Health endpoint enhanced with models object (total_registered, total_available), unavailable_models list, and degraded status when zero models available",
      "GET /admin/models endpoint: per-model probe status, error reason, latency_ms, summary counts, 503 if probes not yet complete",
      "Standalone CLI script (python -m scripts.check_models): formatted table output, summary line, exit code 0 (all pass) or 1 (any fail)",
      "Probe mechanism: deterministic minimal prompt, exception-safe per probe, idempotent given identical external conditions",
      "Property tests (11 Hypothesis properties): registry derivation, probe safety, allowed list correctness, immutability, endpoint filtering, scenario availability, builder filtering, count consistency, idempotence, CLI output, CLI exit code",
    ],
  },
  {
    title: "GCP Telegram Alerting Pipeline",
    specId: "300",
    date: "2026-04-08",
    items: [
      "Terraform alerting module at infra/modules/alerting/ with Terragrunt wrapper, GCS backend, and GCP API enablement",
      "Pub/Sub notification topic (juntoai-alerting-notifications) with monitoring service account publisher grant and Cloud Function subscription",
      "Dedicated alerting-notifier-sa service account with least-privilege IAM: pubsub.subscriber, cloudfunctions.invoker, secretmanager.secretAccessor",
      "Secret Manager secrets for telegram-bot-token and telegram-chat-id with scoped IAM bindings",
      "Log-based metrics for backend error/fatal and frontend error log counts from Cloud Run structured logs",
      "Log-based alerting policies: Backend Error Log Rate (>5/5min), Backend Fatal Log (>0/1min), Frontend Error Log Rate (>5/5min) with severity labels",
      "Cloud Run metric alerting policies: Backend High CPU (>80%), Backend High Memory (>85%), Backend/Frontend High Error Rate (5xx >10), Backend Instance Count Spike",
      "All policies: configurable thresholds via Terraform variables, auto_close 1800s, notification rate limit 300s, absent data = not firing, open + close notifications",
      "Cloud Function (2nd gen, Python 3.11+, 256MB, 60s timeout) with Pub/Sub event trigger and message type detection",
      "Telegram notifier: alarm/resolved emoji prefixes for alerting incidents, build failed prefix for CI/CD failures, HTML formatting via sendMessage API",
      "Cloud Build failure notifications from cloud-builds topic — SUCCESS events discarded, failures include trigger, branch, commit SHA, duration, log URL",
      "Secret caching, non-2xx retry via exception, unknown schema discarding with warning log",
      "Structural tests for module files, variables, outputs, and Terragrunt config",
      "Unit tests for message type detection, parse/format functions, send_telegram_message (mocked HTTP), SUCCESS discarding, unknown schema handling",
      "Property tests (6 Hypothesis properties): detection correctness, SUCCESS discarding, alerting/Cloud Build parse round-trip, format completeness",
    ],
  },
  {
    title: "Negotiation Completion Notification",
    specId: "290",
    date: "2026-04-08",
    items: [
      "Browser notification via Web Notification API when a negotiation reaches a terminal state (Agreed, Blocked, Failed) while the tab is hidden",
      "buildNotificationContent pure function: status-to-title mapping (Deal Agreed, Deal Blocked, Negotiation Failed) with body from finalSummary fields and fallback strings",
      "useNotification React hook: permission request on mount when default, visibility gate (document.hidden), deduplication via useRef keyed by session ID",
      "Click handler: window.focus() then notification.close() to bring user back to the Glass Box page",
      "Notification tag set to session ID to prevent duplicate OS-level notifications for the same session",
      "JuntoAI application icon (icon-192.png) included in notification payload",
      "Graceful degradation: Notification API unavailable or permission denied — all notification logic skipped, zero errors or visual changes",
      "Error handling: try/catch around requestPermission() and new Notification() — failures logged to console, never break app",
      "Dedup tracking reset on component unmount to allow re-notification on page revisit",
      "Frontend-only feature — hooks into existing NegotiationCompleteEvent SSE dispatch, no backend changes",
      "Property tests (fast-check): status-specific content mapping, visibility gate, deduplication invariant",
      "Unit tests: permission request, skip when granted/denied, rejection handling, API unavailable, click handler, constructor throws, unmount reset",
    ],
  },
  {
    title: "Social Sharing",
    specId: "192",
    date: "2026-04-08",
    items: [
      "Completed negotiation replay: terminal sessions stream reconstructed SSE events from persisted history without re-running the orchestrator",
      "Glass Box replay mode (?mode=replay): hides Stop Negotiation button and warm-up spinner, shows Loading negotiation instead of Connecting",
      "SharePayload Pydantic V2 model with 8-char alphanumeric slug, session metadata, participant summaries, and deal outcome — excludes raw history and sensitive data",
      "ShareStore protocol with FirestoreShareClient and SQLiteShareClient — idempotent creation returns existing slug for same session_id",
      "Share image generation via Vertex AI Imagen with 15s timeout; fallback to static branded placeholder on failure",
      "SocialPostText model: Twitter ≤280 chars (truncated preserving URL + branding + hashtags), LinkedIn/Facebook ≤3000 chars",
      "Social post composition: one-sentence summary, participant roles, share URL, Created with @JuntoAI A2A branding, and hashtags",
      "Share API: POST /api/v1/share (session ownership validation, lazy creation) and GET /api/v1/share/{slug} (public, no auth)",
      "SharePanel on Outcome Receipt: LinkedIn, X/Twitter, Facebook, Copy Link (clipboard with selectable text fallback), and Email (mailto with pre-filled subject/body)",
      "Lazy share creation: first button click triggers API call, caches response; loading state disables all buttons during creation",
      "Public share page at /share/{slug}: unauthenticated, server-rendered with Open Graph and Twitter Card meta tags",
      "JuntoAI branded header on share page with Try JuntoAI A2A CTA linking to landing page",
      "Responsive layout: horizontal share buttons at 1024px+, 2-column grid on mobile; share page renders 320px to 1920px",
      "Property tests (8 Hypothesis/fast-check properties): SharePayload round-trip, slug uniqueness, idempotent creation, sensitive data exclusion, social post constraints, mailto composition, meta tags",
    ],
  },
  {
    title: "LLM Usage Summary",
    specId: "190",
    date: "2026-04-07",
    items: [
      "compute_usage_summary(agent_calls) pure aggregator: groups by agent_role and model_id, computes per-persona stats, per-model stats, session-wide totals, and negotiation_duration_ms",
      "PersonaUsageStats, ModelUsageStats, UsageSummary Pydantic V2 models with ge=0 constraints and JSON round-trip property",
      "Edge cases: empty list → zero-valued summary, all-error persona → tokens_per_message = 0, single record → duration 0",
      "usage_summary key added to final_summary in NegotiationCompleteEvent at all terminal-state code paths",
      "Existing ai_tokens_used field preserved — usage summary is additive, not a replacement",
      "Collapsible LLM Usage section on Outcome Receipt, collapsed by default with toggle button",
      "Per-persona breakdown table sorted by total_tokens descending: agent_role, model_id, total_tokens, call_count, avg_latency_ms, tokens_per_message, input:output ratio",
      "Per-model breakdown table: model_id, total_tokens, call_count, avg_latency_ms, tokens_per_message",
      "Session-wide totals: total_tokens, total_calls, total_errors (only if > 0), avg_latency_ms, negotiation_duration_ms formatted as seconds",
      "Most-verbose badge on persona with highest tokens_per_message when 2+ personas exist",
      "Responsive layout: stacked tables on mobile, side-by-side at 1024px+ breakpoint",
      "Backward compatibility: missing agent_calls treated as empty list, absent usage_summary hides section",
      "Property tests (Hypothesis + fast-check): JSON round-trip, aggregation correctness, persona sorting, ratio string, most-verbose-badge placement",
    ],
  },
  {
    title: "Negotiation History Panel",
    specId: "197",
    date: "2026-04-07",
    items: [
      "GET /api/v1/negotiation/history endpoint returning completed sessions grouped by UTC day with configurable days parameter (1–90, default 7)",
      "SessionHistoryItem, DayGroup, SessionHistoryResponse Pydantic V2 models with field constraints and round-trip serialization",
      "Shared compute_token_cost utility: max(1, ceil(total_tokens_used / 1000)) — replaces inline formula in stream_negotiation",
      "list_sessions_by_owner on both FirestoreSessionClient and SQLiteSessionClient with date filtering and descending sort",
      "Day groups sorted descending by date, sessions within groups sorted descending by created_at, terminal sessions only (Agreed, Blocked, Failed)",
      "NegotiationHistory panel below InitializeButton on /arena page: collapsible day groups, colored status badges, daily token cost as fraction of daily limit",
      "Today group expanded by default, others collapsed; Today / Yesterday labels for recent dates",
      "Session replay navigation: View link to /arena/session/{session_id} loads read-only Glass Box replay for terminal sessions",
      "Loading skeleton, error state with retry, empty state messaging",
      "Local mode: SQLite query with JSON column owner_email extraction, ∞ for unlimited daily token display",
      "Responsive layout: single-column below 1024px, max-w-4xl container at 1024px+",
      "Property tests (Hypothesis): token cost formula, response round-trip, grouping/sorting correctness, date range filtering, DayGroup token cost sum invariant",
    ],
  },
  {
    title: "AI Scenario Builder",
    specId: "130",
    date: "2026-04-06",
    items: [
      "AI-powered interactive scenario builder: guided chatbot (Claude Opus 4.6 via Vertex AI) produces validated ArenaScenario JSON configs",
      "Build Your Own Scenario entry point in ScenarioSelector with My Scenarios group for saved custom scenarios",
      "Split-screen Builder Modal: chatbot on left, live JSON preview with syntax highlighting on right, progress indicator at top",
      "Structured collection order: scenario metadata → agents → toggles → negotiation params → outcome receipt",
      "Builder SSE streaming: builder_token, builder_json_delta, builder_complete, builder_error event types",
      "LinkedIn Persona Generator: paste a LinkedIn URL during agent definition to auto-generate persona, role, goals, and tone",
      "Scenario Health Check Analyzer: AI-powered readiness analysis for prompt quality, goal tension, budget overlap, toggle effectiveness, turn sanity, stall risk, regulator feasibility",
      "Readiness score 0-100 with weighted composite and tier classification (Ready / Needs Work / Not Ready)",
      "Health check SSE streaming with progressive rendering of findings and full report",
      "Gold-standard scenarios (talent-war, b2b-sales, ma-buyout, freelance-gig, urban-development) as few-shot references in health check prompts",
      "Budget overlap analysis: overlap zone computation, no_overlap/excessive_overlap flagging, agreement_threshold vs target gap ratio",
      "Turn order validation: missing negotiator detection, insufficient turns warning, regulator interval check",
      "Stall risk assessment: instant_convergence_risk, price_stagnation_risk, repetition_risk with composite score",
      "Custom scenario persistence: Firestore sub-collection profiles/{email}/custom_scenarios with 20-scenario limit and profile verification",
      "SQLiteCustomScenarioStore for local mode — full builder functionality without cloud dependencies",
      "Builder API: POST /builder/chat (SSE), POST /builder/save (validate + health check + persist), GET and DELETE /builder/scenarios",
      "Token budget enforcement: 1 token per builder message, tier-aware daily limits, HTTP 429 on exhaustion",
      "ArenaScenario round-trip validation via pretty_print and load_scenario_from_dict before persistence",
      "Builder session management: in-memory conversation history, 50-message limit, 60-minute stale session cleanup",
      "Responsive Builder Modal: split-screen ≥1024px, stacked below; close confirmation for unsaved progress",
      "JSON preview: 2-space indentation, placeholder markers for unpopulated sections, 2-second highlight on updates",
      "Property tests (22 Hypothesis/fast-check properties): SSE wire format, round-trip, progress, agent validation, budget overlap, stall risk, readiness scoring",
    ],
  },
  {
    title: "Admin Dashboard",
    specId: "150",
    date: "2026-04-06",
    items: [
      "Cloud-only internal admin dashboard at /admin with shared-password authentication (ADMIN_PASSWORD env var)",
      "Admin login with itsdangerous signed HTTP-only session cookie (8h TTL), constant-time password comparison, IP-based rate limiting",
      "Dashboard overview: total users, simulations today, active SSE connections, aggregate AI token consumption, scenario analytics",
      "Model performance metrics: average latency, token usage, and error count per model from Spec 145 agent_calls telemetry",
      "User management: paginated user list joined from waitlist + profiles collections with tier/status filtering",
      "User actions: token balance adjustment and account status changes (active, suspended, banned)",
      "user_status field on waitlist documents — suspended/banned users blocked at POST /api/v1/negotiation/start with 403",
      "Simulation list: paginated sessions with filtering by scenario_id, deal_status, owner_email and cursor-based pagination",
      "Simulation transcript download: plain text reconstruction from history array with agent role, turn number, and messages",
      "Raw JSON session download and CSV export endpoints for users and simulations with RFC 4180 escaping",
      "Session metadata: created_at, completed_at, and duration_seconds fields on session documents for analytics",
      "Admin API security: HTTP-only/Secure/SameSite=Strict cookie, Pydantic V2 validation, INFO-level audit logging",
      "Server-side rendered admin pages — no admin data in client JavaScript bundles",
      "RUN_MODE=local returns HTTP 503 for all admin endpoints; missing user_status treated as active for backward compatibility",
    ],
  },
  {
    title: "Test Coverage Hardening",
    specId: "155",
    date: "2026-04-06",
    items: [
      "Backend coverage gate: pytest --cov=app --cov-fail-under=70 enforced — passes 70% threshold, completes under 120s",
      "pytest.ini markers (unit, integration, property, slow) for selective test runs via pytest -m",
      "SSE event formatting tests: _snapshot_to_events() for negotiator, regulator, observer, dispatcher with data: JSON format validation",
      "Participant summary tests: _build_participant_summaries(), _build_block_advice(), _format_outcome_value() for multi-agent scenarios",
      "Model mapping tests: resolve_model_id() for all 4 resolution paths across openai, anthropic, and ollama providers",
      "SQLite and Firestore session client tests: in-memory round-trip, mocked SDK, create/get/update/not-found coverage",
      "Profile client tests: mocked Firestore for get_or_create_profile, get_profile, update_profile",
      "SSE middleware tests: SSEEventBuffer (append, replay_after, terminal events, session isolation) and SSEConnectionTracker (acquire/release, limits)",
      "Auth service tests: bcrypt hash/verify round-trip with 72-byte truncation, validate_google_token, check_google_oauth_id_unique",
      "Negotiation router integration tests: POST /api/v1/negotiation/start (200, 404, 422), SSE event replay via Last-Event-ID",
      "Evaluator and orchestrator tests: evaluation logic with mocked LLM, prompt construction, confirmation node, milestone generator",
      "Scenario module tests: toggle injector (multi-toggle, non-existent agent), pretty printer, loader/registry error paths",
      "Frontend API client tests: lib/auth.ts (7 functions) and lib/profile.ts (3 functions) with mocked fetch and error handling",
      "Frontend component tests: WaitlistForm, TokenDisplay, StartNegotiationButton with validation, edge cases, and interaction testing",
      "Property tests: SSE format compliance, model mapping determinism, SQLite round-trip, password hash round-trip, event buffer replay",
    ],
  },
  {
    title: "Negotiation Evaluator",
    specId: "170",
    date: "2026-04-05",
    items: [
      "Deal closure protocol: price convergence triggers a Confirmation Round — each negotiator explicitly accepts or rejects proposed terms",
      "ConfirmationOutput Pydantic V2 model with accept, final_statement, conditions — parse retry + fallback rejection on invalid JSON",
      "deal_status = Confirming state with closure_status and confirmation_pending fields on NegotiationState",
      "Confirmation resolution: all accept + no conditions → Confirmed, any reject → resume Negotiating, conditions → resume Negotiating",
      "Confirmation node runs as LangGraph node without incrementing turn_count; final_statement streamed as agent_message SSE events",
      "Post-negotiation Evaluator Agent: standalone async generator running after run_negotiation(), before negotiation_complete SSE event",
      "Independent Evaluation Interview per negotiator: 5 probing questions on satisfaction, respect, win-win, criticism, and self-rated score",
      "EvaluationReport: per-participant interviews, four Score Dimensions (fairness, mutual_respect, value_creation, satisfaction), overall score 1-10, verdict",
      "Anti-rubber-stamp scoring: default 5, cap at 6 if dissatisfaction, penalize simple splits by 2 points, reserve 9-10 for genuine enthusiasm",
      "Cross-referencing: scoring prompt includes objective deal metrics (final price vs budget) to flag inconsistencies",
      "evaluation_interview and evaluation_complete SSE event types for real-time Glass Box streaming",
      "Configurable evaluator model via evaluator_config on ArenaScenario — defaults to first negotiator's model_id",
      "Outcome Receipt: prominent X / 10 score with color coding (red/amber/green), dimension bars, verdict, per-participant satisfaction",
      "Graceful degradation: evaluator disabled or failure → existing outcome layout, negotiation_complete always emitted",
      "N-agent compatible: confirmation round and evaluator iterate over all negotiator agents from scenario config",
      "Property tests (11 Hypothesis properties): model round-trip, convergence, resolution determinism, interview isolation, scoring metrics",
    ],
  },
  {
    title: "Per-Model Telemetry",
    specId: "145",
    date: "2026-04-05",
    items: [
      "AgentCallRecord Pydantic V2 model: agent_role, agent_type, model_id, latency_ms, input_tokens, output_tokens, error, turn_number, timestamp",
      "agent_calls append-only list on NegotiationState using LangGraph add reducer — same merge pattern as history",
      "Agent node instrumentation: wall-clock timing and usage_metadata token extraction for every model.invoke() call",
      "Retry calls recorded as separate AgentCallRecord entries with independent latency/tokens; fallback sets error=True",
      "_extract_tokens() helper handling dict, object, and None usage_metadata shapes",
      "Converter round-trip: to_pydantic() / from_pydantic() map agent_calls with backward-compatible default for pre-existing sessions",
      "All telemetry wrapped in try/except — failures log WARNING, never break negotiation logic",
      "Property tests (Hypothesis): AgentCallRecord round-trip, converter round-trip, token extraction correctness",
      "Prerequisite for Spec 150 (Admin Dashboard) per-model performance metrics",
    ],
  },
  {
    title: "Developer Community Infrastructure",
    specId: "160",
    date: "2026-04-04",
    items: [
      "GitHub Actions PR CI pipeline: parallel backend pytest + frontend Vitest jobs on every PR to main, 70% coverage enforced",
      "CONTRIBUTING.md with fork-and-PR workflow, local dev setup, test commands, and scenario contribution guide (JSON-only)",
      "CODE_OF_CONDUCT.md based on Contributor Covenant v2.1 with enforcement contact and community scope",
      "GitHub issue templates: structured YAML forms for bug reports and feature requests, blank issues disabled",
      "Pull request template with change-type checkboxes, related-issue linking, and pre-merge checklist",
      "Contributor onboarding labels documented: good first issue, scenario-contribution, help wanted",
      "README community section updated with links to CONTRIBUTING.md, CODE_OF_CONDUCT.md, WhatsApp channel, and good first issue view",
      "Branch protection guidance: main protected, CI must pass before merge, no direct pushes",
    ],
  },
  {
    title: "User Profile & Token Upgrade",
    specId: "140",
    date: "2026-04-04",
    items: [
      "3-tier daily token system: Tier 1 (20/day) on signup, Tier 2 (50) on email verification, Tier 3 (100) on full profile completion",
      "Profile page accessible via email link in header: display name, GitHub URL, LinkedIn URL, country dropdown",
      "Email verification via Amazon SES with UUID tokens, 24h TTL, and automatic Tier 2 upgrade on click-through",
      "Tier 3 is permanent once earned — profile_completed_at timestamp is write-once",
      "Password-based account protection with bcrypt hashing and conditional password prompt on login",
      "Google OAuth account linking: link/unlink on profile page, Google sign-in on login form",
      "Auth endpoints: set-password, login, check-email, google/link, google/login, google/unlink",
      "Profile endpoints: GET/PUT profile, POST verify-email, GET verify token with Pydantic V2 validation",
      "Country field (ISO 3166-1 alpha-2) for upcoming leaderboard — validated via pycountry",
      "Tier-aware token reset at midnight UTC uses profile tier instead of hardcoded 100",
      "Frontend SessionContext updated with tier/dailyLimit; TokenDisplay shows dynamic X / {dailyLimit}",
      "Dual-mode support: SQLiteProfileClient for local, FirestoreProfileClient for cloud",
      "18 property tests (Hypothesis + fast-check): profile validation, tier logic, bcrypt, URLs, country codes, OAuth uniqueness",
    ],
  },
  {
    title: "Landing Page Redesign",
    specId: "180",
    date: "2026-04-04",
    items: [
      "Shared Header component: persistent sticky header with logo, nav links, auth-aware state (email/tokens/logout vs Join Waitlist CTA)",
      "Header integrated into root layout; inline header bar removed from protected layout — auth-guard logic preserved",
      "Landing page restructured: Hero → ScenarioBanner → Value Props → GitHub CTA in centered max-w-[1200px] container",
      "Value proposition cards redesigned with Lucide React icons, brand color tinted backgrounds, responsive 3-column grid",
      "GitHub community CTA section with gradient accent, GitHub icon, and external link to public repo",
      "All color references use brand-* Tailwind tokens or CSS custom properties — zero inline hex values",
      "Mobile-responsive: compact header below 768px, stacked cards below 640px, no horizontal overflow at 320px minimum",
      "Unit tests for Header component (logo, nav links, auth states) and landing page (section order, value props, GitHub CTA, brand colors)",
    ],
  },
  {
    title: "Hybrid Agent Memory",
    specId: "110",
    date: "2026-04-04",
    items: [
      "Milestone summary generator: lightweight LLM call per agent at configurable turn intervals produces ≤300-token strategic summaries",
      "Configurable sliding window: sliding_window_size scenario parameter (default 3) replaces hardcoded window from spec 100",
      "Full history elimination: after first milestone, prompt excludes all raw history beyond the sliding window — bounded token cost per turn",
      "milestone_interval scenario parameter (default 4) controls turn cycles between summary generations",
      "Milestone summaries include agent-private reasoning context for perspective-aware compression",
      "Non-blocking failure: LLM failure for one agent's summary does not block others or the negotiation",
      "Dispatcher integration: milestone generation triggers after turn advancement, before next agent node",
      "Milestone Summaries toggle in Advanced Options — auto-enables structured memory, visually disabled when structured memory is off",
      "Server-side dependency enforcement: milestone_summaries_enabled=True forces structured_memory_enabled=True",
      "Full backward compatibility: disabled by default, missing fields default safely, existing sessions unaffected",
      "Property tests: NegotiationParams round-trip, state initialization, milestone serialization round-trip, prompt token boundedness",
    ],
  },
  {
    title: "Structured Agent Memory",
    specId: "100",
    date: "2026-04-03",
    items: [
      "Per-agent AgentMemory Pydantic V2 model with typed fields for offers, concessions, tactics, red lines, and compliance",
      "Memory-aware prompt builder: structured memory + sliding window of last 3 messages replaces full history",
      "Deterministic memory extraction after each turn — no extra LLM calls",
      "Stall detector reads my_offers directly from agent_memories when enabled",
      "structured_memory_enabled flag threaded through NegotiationState, Firestore persistence, and API layer",
      "Per-agent structured memory toggle in Advanced Config modal — enable memory independently for each agent",
      "Full backward compatibility: disabled by default, missing fields default safely, existing sessions unaffected",
      "Property tests: round-trip serialization, prompt format, memory extraction, stall detector equivalence",
    ],
  },
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
