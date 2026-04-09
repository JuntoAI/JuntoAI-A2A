# Changelog

All notable changes to the JuntoAI A2A Protocol Sandbox are documented here.

Each entry corresponds to a completed spec - shipped when the last task was finished.

---

## LLM Availability Checker (Spec 310) — 2026-04-09

- Model registry extended with `gemini-3.1-pro-preview` and `gemini-3.1-flash-lite-preview` entries — `VALID_MODEL_IDS`, `MODELS_PROMPT_BLOCK`, and `DEFAULT_MODEL_MAP` derive automatically
- Startup availability probe: concurrent `asyncio.gather` probes of all registered models via Vertex AI (cloud) or LiteLLM (local) with configurable 15s timeout per probe
- `ProbeResult` and `AllowedModels` frozen dataclasses — immutable after construction, stored in `app.state.allowed_models` for dependency injection
- Zero-model degraded mode: application starts with empty allowed list and `"degraded"` health status instead of crashing
- `/api/v1/models` endpoint returns only verified-working models from the Allowed_Models_List
- Scenario registry `available` boolean flag: validates each agent's `model_id` and `fallback_model_id` against allowed set at load time, logs WARNING for unavailable models
- Builder prompt block filtered to allowed models only — generated scenarios reference only reachable LLMs
- Health endpoint enhanced with `models` object (`total_registered`, `total_available`), `unavailable_models` list, and `"degraded"` status when zero models available
- `GET /admin/models` endpoint: per-model probe status, error reason, latency_ms, summary counts, 503 if probes not yet complete, gated behind admin session auth
- Standalone CLI script (`python -m scripts.check_models`): formatted table output, summary line (`X/Y models available`), exit code 0 (all pass) or 1 (any fail)
- Probe mechanism: deterministic minimal prompt ("Respond with OK"), exception-safe per probe, idempotent given identical external conditions
- Property tests (11 Hypothesis properties): registry derivation consistency, probe exception safety, allowed list correctness, immutability, models endpoint filtering, scenario availability flag, builder prompt filtering, health/admin count consistency, probe idempotence, CLI output completeness, CLI exit code

## GCP Telegram Alerting Pipeline (Spec 300) — 2026-04-08

- Terraform alerting module at `infra/modules/alerting/` with Terragrunt wrapper, GCS backend, and GCP API enablement (monitoring, cloudfunctions, pubsub, cloudbuild)
- Pub/Sub notification topic (`juntoai-alerting-notifications`) with monitoring service account publisher grant and Cloud Function subscription
- Dedicated `alerting-notifier-sa` service account with least-privilege IAM: pubsub.subscriber, cloudfunctions.invoker, secretmanager.secretAccessor scoped to Telegram secrets
- Secret Manager secrets for `telegram-bot-token` and `telegram-chat-id` with IAM bindings
- Log-based metrics: `backend/error-log-count` (severity >= ERROR), `backend/fatal-log-count` (severity = CRITICAL), `frontend/error-log-count` (severity >= ERROR)
- Log-based alerting policies: Backend Error Log Rate (>5/5min, medium), Backend Fatal Log (>0/1min, critical), Frontend Error Log Rate (>5/5min, medium)
- Cloud Run metric alerting policies: Backend High CPU (>80%, 2 consecutive periods), Backend High Memory (>85%), Backend/Frontend High Error Rate (5xx >10), Backend Instance Count Spike (>10)
- All policies: configurable thresholds via Terraform variables, auto_close 1800s, notification rate limit 300s, absent data = not firing, notifications on open and close
- Cloud Function (2nd gen, Python 3.11+, 256MB, 60s timeout): Pub/Sub event trigger with message type detection (alerting_policy, cloud_build, unknown)
- Telegram notifier: 🚨 ALARM / ✅ RESOLVED for alerting incidents, 🔴 Build FAILED for CI/CD failures, HTML formatting via sendMessage API
- Cloud Build failure notifications from `cloud-builds` topic — SUCCESS events discarded, failures include trigger name, branch, commit SHA, duration, log URL
- Secret caching, non-2xx retry via exception, unknown schema discarding with warning log
- Structural tests for module files, variables, outputs, and Terragrunt config
- Unit tests for detect_message_type, parse/format functions, send_telegram_message (mocked HTTP), SUCCESS discarding, unknown schema handling
- Property tests (6 Hypothesis properties): message type detection correctness, SUCCESS event discarding, alerting parse round-trip, Cloud Build parse round-trip, alerting format completeness, Cloud Build format completeness

## Negotiation Completion Notification (Spec 290) — 2026-04-08

- Browser notification via Web Notification API when a negotiation reaches a terminal state (Agreed, Blocked, Failed) while the user's tab is hidden
- `buildNotificationContent` pure function: status-to-title mapping ("Deal Agreed", "Deal Blocked", "Negotiation Failed") with body extracted from `finalSummary` fields (`current_offer`, `blocked_by`, `reason`) and fallback strings
- `useNotification` React hook: permission request on mount when "default", visibility gate (`document.hidden`), deduplication via `useRef<Set<string>>` keyed by session ID, click handler (`window.focus()` + `notification.close()`)
- Notification tag set to session ID to prevent duplicate OS-level notifications for the same session
- JuntoAI application icon (`icon-192.png`) included in notification payload
- Graceful degradation: Notification API unavailable or permission denied → all notification logic skipped, zero errors or visual changes
- Error handling: try/catch around `requestPermission()` and `new Notification()` constructor — failures logged to console, never break app
- Dedup tracking reset on component unmount to allow re-notification on page revisit
- Frontend-only feature — hooks into existing `NegotiationCompleteEvent` SSE dispatch flow, no backend changes
- Property tests (fast-check): status-specific content mapping, visibility gate, deduplication invariant
- Unit tests: permission request on mount, skip when granted/denied, requestPermission rejection, API unavailable, click handler, constructor throws, unmount resets tracking

## Social Sharing (Spec 192) — 2026-04-08

- Completed negotiation replay: terminal sessions stream reconstructed SSE events from persisted history without re-running the LangGraph orchestrator
- Glass Box replay mode (`?mode=replay`): hides Stop Negotiation button and warm-up spinner, shows "Loading negotiation…" instead of "Connecting…"
- `SharePayload` Pydantic V2 model with 8-char alphanumeric slug, session metadata, participant summaries, and deal outcome — excludes raw history, hidden context, and custom prompts
- `ShareStore` protocol with `FirestoreShareClient` (`shared_negotiations` collection) and `SQLiteShareClient` implementations — idempotent creation returns existing slug for same session_id
- Share image generation via Vertex AI Imagen with 15s timeout; fallback to static branded placeholder on failure or timeout
- `SocialPostText` model with platform-specific variants: Twitter ≤280 chars (truncated preserving URL + branding + hashtags), LinkedIn/Facebook ≤3000 chars
- Social post composition: one-sentence summary, participant roles, public share URL, "Created with @JuntoAI A2A" branding, #JuntoAI #A2A #AIAgents #Negotiation hashtags
- Share API: `POST /api/v1/share` (session ownership validation, lazy payload creation) and `GET /api/v1/share/{slug}` (public, no auth)
- SharePanel on Outcome Receipt (`data-testid="share-panel"`): LinkedIn, X/Twitter, Facebook, Copy Link (clipboard API with selectable text fallback), and Email (mailto with pre-filled subject/body)
- Lazy share creation: first button click triggers API call, caches response; loading state disables all buttons during creation
- Public share page at `/share/{slug}`: unauthenticated, server-rendered with Open Graph and Twitter Card meta tags (og:title, og:description ≤200 chars, og:image, twitter:card=summary_large_image)
- JuntoAI branded header on share page with "Try JuntoAI A2A" CTA linking to landing page
- Responsive layout: horizontal share buttons ≥1024px, 2-column grid on mobile; share page renders 320px–1920px
- Property tests (8 Hypothesis/fast-check properties): SharePayload round-trip, slug format/uniqueness, idempotent creation, sensitive data exclusion, social post required elements, length constraints, mailto composition, meta tag generation

## LLM Usage Summary (Spec 190) — 2026-04-07

- `compute_usage_summary(agent_calls)` pure aggregator: groups by `agent_role` and `model_id`, computes per-persona stats, per-model stats, session-wide totals, and `negotiation_duration_ms` from timestamp range
- `PersonaUsageStats`, `ModelUsageStats`, `UsageSummary` Pydantic V2 models with `ge=0` constraints and JSON round-trip property
- Edge cases: empty list → zero-valued summary, all-error persona → `tokens_per_message = 0`, single record → `negotiation_duration_ms = 0`, missing timestamps → duration 0
- Integration into `_snapshot_to_events`: `usage_summary` key added to `final_summary` dict in `NegotiationCompleteEvent` at all terminal-state code paths
- Existing `ai_tokens_used` field continues to be populated — usage summary is additive, not a replacement
- Collapsible "LLM Usage" section on Outcome Receipt (`data-testid="usage-summary-section"`), collapsed by default with toggle button
- Per-persona breakdown table sorted by `total_tokens` descending: agent_role, model_id, total_tokens, call_count, avg_latency_ms, tokens_per_message, input:output ratio ("X.Y:1")
- Per-model breakdown table: model_id, total_tokens, call_count, avg_latency_ms, tokens_per_message
- Session-wide totals: total_tokens, total_calls, total_errors (only if > 0), avg_latency_ms, negotiation_duration_ms formatted as seconds
- Most-verbose badge (`data-testid="most-verbose-badge"`) on persona with highest `tokens_per_message` when 2+ personas exist
- Responsive layout: stacked tables on mobile, side-by-side at ≥1024px (`lg:` breakpoint)
- Backward compatibility: missing `agent_calls` treated as empty list, absent `usage_summary` → section not rendered
- Property tests (Hypothesis + fast-check): UsageSummary JSON round-trip, aggregation correctness, persona sorting, input:output ratio string, most-verbose-badge placement

## Negotiation History Panel (Spec 197) — 2026-04-07

- `GET /api/v1/negotiation/history` endpoint returning completed sessions grouped by UTC day with configurable `days` parameter (1–90, default 7)
- `SessionHistoryItem`, `DayGroup`, `SessionHistoryResponse` Pydantic V2 models with field constraints and round-trip serialization
- Shared `compute_token_cost` utility: `max(1, ceil(total_tokens_used / 1000))` — replaces inline formula in `stream_negotiation`
- `list_sessions_by_owner` on both `FirestoreSessionClient` and `SQLiteSessionClient` with date filtering and descending sort
- Day groups sorted descending by date, sessions within groups sorted descending by `created_at`, terminal sessions only (Agreed, Blocked, Failed)
- `NegotiationHistory` panel below InitializeButton on `/arena` page: collapsible day groups, colored status badges, daily token cost as fraction of daily limit
- Today group expanded by default, others collapsed; "Today" / "Yesterday" labels for recent dates
- Session replay navigation: "View" link to `/arena/session/{session_id}` loads read-only Glass Box replay for terminal sessions
- Loading skeleton, error state with retry, empty state messaging
- Local mode: SQLite query with JSON column `owner_email` extraction, "∞" for unlimited daily token display
- Responsive layout: single-column below 1024px, `max-w-4xl` container at 1024px+
- Property tests (Hypothesis): token cost formula correctness, response round-trip serialization, grouping/sorting correctness, date range filtering, DayGroup token cost sum invariant

## AI Scenario Builder (Spec 130) — 2026-04-06

- AI-powered interactive scenario builder: guided chatbot conversation (Claude Opus 4.6 via Vertex AI) produces validated ArenaScenario JSON configs
- "Build Your Own Scenario" entry point in ScenarioSelector with "My Scenarios" group for saved custom scenarios
- Split-screen Builder Modal: chatbot on left, live JSON preview with syntax highlighting on right, progress indicator at top
- Structured collection order: scenario metadata → agents (one at a time) → toggles → negotiation params → outcome receipt
- Builder SSE streaming: `builder_token`, `builder_json_delta`, `builder_complete`, `builder_error` event types with `data: <JSON>\n\n` format
- LinkedIn Persona Generator: paste a LinkedIn URL during agent definition and the AI generates a persona_prompt, role, goals, and tone from the profile
- Scenario Health Check Analyzer: AI-powered simulation readiness analysis evaluating prompt quality, goal tension, budget overlap, toggle effectiveness, turn sanity, stall risk, and regulator feasibility
- Readiness score 0-100 with weighted composite (prompt quality 25%, tension 20%, budget overlap 20%, toggle effectiveness 15%, turn sanity 10%, inverse stall risk 10%) and tier classification (Ready/Needs Work/Not Ready)
- Health check SSE streaming: `builder_health_check_start`, `builder_health_check_finding`, `builder_health_check_complete` events with progressive rendering
- Gold-standard scenario files (talent-war, b2b-sales, ma-buyout, freelance-gig, urban-development) used as few-shot reference examples in health check prompts
- Budget overlap analysis: overlap zone computation, no_overlap/excessive_overlap flagging, agreement_threshold vs target gap ratio check
- Turn order validation: missing negotiator detection (critical), insufficient turns warning, regulator interval check
- Stall risk assessment: instant_convergence_risk, price_stagnation_risk, repetition_risk detection with composite stall_risk_score
- Custom scenario persistence: Firestore sub-collection `profiles/{email}/custom_scenarios` with 20-scenario-per-user limit, profile existence verification (403 if no profile)
- SQLiteCustomScenarioStore for local mode (`RUN_MODE=local`) — full builder functionality without cloud dependencies
- Builder API: `POST /builder/chat` (SSE streaming), `POST /builder/save` (validate + health check + persist), `GET /builder/scenarios`, `DELETE /builder/scenarios/{id}`
- Token budget enforcement: 1 token per builder message, tier-aware daily limits (20/50/100 from Spec 140), HTTP 429 on exhaustion
- ArenaScenario round-trip validation: `pretty_print` → JSON parse → `model_validate` and `load_scenario_from_dict` equivalence checks before persistence
- Builder session management: in-memory conversation history, 50-message limit per session, stale session cleanup (60min TTL)
- Responsive Builder Modal: split-screen ≥1024px, stacked below; close confirmation dialog for unsaved progress
- JSON preview: 2-space indentation, placeholder markers for unpopulated sections, 2-second highlight animation on section updates
- Property tests (22 Hypothesis/fast-check properties): SSE wire format, round-trip serialization, progress computation, agent minimum validation, validation error specificity, session limits, budget overlap, turn sanity, stall risk, readiness scoring, scenario persistence, token enforcement, JSON preview rendering

## Admin Dashboard (Spec 150) — 2026-04-06

- Cloud-only internal admin dashboard at `/admin` with shared-password authentication (`ADMIN_PASSWORD` env var)
- Admin login with `itsdangerous` signed HTTP-only session cookie (8h TTL), constant-time password comparison, IP-based rate limiting (10 attempts / 5 min)
- Dashboard overview: total users, simulations today, active SSE connections, aggregate AI token consumption, scenario analytics, model performance metrics (latency, tokens, errors from Spec 145 `agent_calls`)
- User management: paginated user list joined from `waitlist` + `profiles` collections, cursor-based pagination, tier/status filtering
- User actions: token balance adjustment (`PATCH /admin/users/{email}/tokens`), account status changes (`active`, `suspended`, `banned`)
- `user_status` field on waitlist documents — `suspended`/`banned` users blocked at `POST /api/v1/negotiation/start` with 403
- Simulation list: paginated sessions with filtering by scenario_id, deal_status, owner_email and cursor-based pagination
- Simulation transcript download: plain text reconstruction from history array with agent role, turn number, inner thought, and public message
- Raw JSON session download with `Content-Disposition` attachment headers
- CSV export endpoints for users and simulations with RFC 4180 escaping and date-stamped filenames
- Session metadata: `created_at`, `completed_at`, and `duration_seconds` fields added to session documents for analytics
- Admin API security: HTTP-only/Secure/SameSite=Strict cookie, Pydantic V2 validation on all params, INFO-level audit logging for all admin actions
- Server-side rendered admin pages — no admin data in client JavaScript bundles
- `RUN_MODE=local` returns HTTP 503 for all admin endpoints
- Backward compatibility: missing `user_status` treated as `active`

## Test Coverage Hardening (Spec 155) — 2026-04-06

- Backend coverage gate: `pytest --cov=app --cov-fail-under=70` enforced — test suite passes 70% threshold and completes under 120s
- `pytest.ini` markers (`unit`, `integration`, `property`, `slow`) for selective test runs via `pytest -m <marker>`
- SSE event formatting tests: `_snapshot_to_events()` coverage for negotiator, regulator, observer, and dispatcher snapshots with `data: <valid JSON>\n\n` format validation
- Participant summary tests: `_build_participant_summaries()`, `_build_block_advice()`, `_format_outcome_value()`, `_format_price_for_summary()` for multi-agent scenarios
- Model mapping tests: `resolve_model_id()` coverage for all 4 resolution paths (global override, MODEL_MAP JSON, default mapping, provider fallback) across openai, anthropic, and ollama providers
- SQLite session client tests: in-memory round-trip for `create_session`, `get_session`, `get_session_doc`, `update_session`, and `SessionNotFoundError`
- Firestore session client tests: mocked SDK covering `create_session`, `get_session`, `get_session_doc`, and document-not-found error
- Profile client tests: mocked Firestore for `get_or_create_profile`, `get_profile`, `update_profile`
- SSE middleware tests: `SSEEventBuffer` (append, replay_after, terminal events, session isolation) and `SSEConnectionTracker` (acquire/release, limit enforcement)
- Auth service tests: bcrypt hash/verify round-trip with 72-byte truncation edge case, `validate_google_token` with mocked HTTP, `check_google_oauth_id_unique`
- Negotiation router integration tests: `POST /api/v1/negotiation/start` (200, 404, 422), SSE event replay via `Last-Event-ID`, auth and profile endpoint coverage
- Evaluator and orchestrator tests: evaluation logic with mocked LLM, prompt construction for 2-agent and 4-agent scenarios, confirmation node, milestone generator
- Scenario module tests: toggle injector (multi-toggle, non-existent agent), pretty printer, scenario loader/registry error paths
- Frontend API client tests: `lib/auth.ts` (7 functions) and `lib/profile.ts` (3 functions) with mocked fetch — success, specific error codes, and generic error handling
- Frontend component tests: WaitlistForm (validation, submission, errors), TokenDisplay (count, zero, null), StartNegotiationButton (enabled/disabled, click handler)
- Property tests: SSE format compliance, model mapping determinism, SQLite session round-trip, password hash round-trip, event buffer replay correctness

## Negotiation Evaluator (Spec 170) — 2026-04-05

- Deal closure protocol: price convergence triggers a Confirmation_Round instead of immediately marking "Agreed" — each negotiator explicitly accepts or rejects the proposed terms
- `ConfirmationOutput` Pydantic V2 model: `accept` (bool), `final_statement` (str), `conditions` (list[str]) with parse retry + fallback rejection
- `deal_status = "Confirming"` state with `closure_status` and `confirmation_pending` fields on NegotiationState
- Confirmation resolution: all accept + no conditions → Confirmed, any reject → resume Negotiating, all accept + conditions → resume Negotiating
- Confirmation node runs as a LangGraph node that does NOT increment `turn_count`; final_statement streamed as `agent_message` SSE events
- Post-negotiation Evaluator Agent ("JuntoAI Evaluator"): standalone async generator running AFTER `run_negotiation()` completes, BEFORE `negotiation_complete` SSE event
- Independent Evaluation_Interview per negotiator: 5 probing questions on satisfaction, respect, win-win perception, criticism, and self-rated score (1-10)
- `EvaluationInterview` model: `feels_served`, `felt_respected`, `is_win_win`, `criticism`, `satisfaction_rating` with parse retry + neutral fallback (rating=5)
- `EvaluationReport` model: per-participant interviews, four Score_Dimensions (fairness, mutual_respect, value_creation, satisfaction — each 1-10), overall_score (1-10), verdict
- Anti-rubber-stamp scoring: default 5, cap at 6 if any dissatisfaction, penalize simple price splits by 2 points, reserve 9-10 for genuine enthusiasm + novel value creation
- Cross-referencing: scoring prompt includes objective deal metrics (final price vs each agent's target/budget) to flag inconsistencies
- Interview isolation: no participant sees other participants' responses
- `evaluation_interview` and `evaluation_complete` SSE event types for real-time Glass Box streaming
- Configurable evaluator model via `evaluator_config` on ArenaScenario (model_id, fallback_model_id, enabled) — defaults to first negotiator's model_id
- Evaluator respects `LLM_MODEL_OVERRIDE` and `MODEL_MAP` env vars for local mode model routing
- Outcome Receipt extended: prominent "X / 10" score with color coding (1-3 red, 4-6 amber, 7-8 green, 9-10 bright green), dimension progress bars, verdict summary, per-participant satisfaction
- Graceful degradation: evaluator disabled or failure → existing outcome layout, `negotiation_complete` always emitted
- N-agent compatible: confirmation round and evaluator iterate over all `type == "negotiator"` agents from scenario config — no hardcoded role names
- Property tests (11 Hypothesis properties): model round-trip, convergence triggers Confirming, confirmation_pending correctness, resolution determinism, history entries, interview count/isolation, prompt context, model resolution, scoring metrics, confirmation prompt terms

## Per-Model Telemetry (Spec 145) — 2026-04-05

- `AgentCallRecord` Pydantic V2 model capturing `agent_role`, `agent_type`, `model_id`, `latency_ms`, `input_tokens`, `output_tokens`, `error`, `turn_number`, and `timestamp` per LLM invocation
- `agent_calls` append-only list on `NegotiationState` using LangGraph `add` reducer — same merge pattern as `history`
- Agent node instrumentation: `time.perf_counter()` wall-clock timing and `usage_metadata` token extraction for every `model.invoke()` call
- Retry calls recorded as separate `AgentCallRecord` entries with independent latency/tokens; fallback sets `error=True`
- `_extract_tokens()` helper handling dict, object, and `None` `usage_metadata` shapes
- Converter round-trip: `to_pydantic()` / `from_pydantic()` map `agent_calls` with backward-compatible default for pre-existing sessions
- All telemetry wrapped in try/except — failures log WARNING, never break negotiation logic
- Property tests (Hypothesis): AgentCallRecord round-trip serialization, converter round-trip preserves agent_calls, token extraction correctness
- Prerequisite for Spec 150 (Admin Dashboard) per-model performance metrics

## Developer Community Infrastructure (Spec 160) — 2026-04-04

- GitHub Actions PR CI pipeline (`.github/workflows/pr-tests.yml`): parallel backend pytest + frontend Vitest jobs on every PR to `main`, 70% coverage enforced
- `CONTRIBUTING.md`: fork-and-PR workflow, local dev setup (Docker, Python 3.11, Node 20), test commands, scenario contribution guide (JSON-only, no code changes)
- `CODE_OF_CONDUCT.md` based on Contributor Covenant v2.1 with enforcement contact and community scope
- GitHub issue templates: structured YAML forms for bug reports (repro steps, environment) and feature requests (problem, proposed solution), blank issues disabled
- Pull request template with change-type checkboxes, related-issue linking, and pre-merge checklist (tests, coverage, CONTRIBUTING.md read)
- Contributor onboarding labels documented: `good first issue`, `scenario-contribution`, `help wanted`
- README community section updated: links to CONTRIBUTING.md, CODE_OF_CONDUCT.md, WhatsApp channel, and `good first issue` filtered view
- Branch protection guidance: `main` protected, CI must pass before merge, no direct pushes

## User Profile & Token Upgrade (Spec 140) — 2026-04-04

- 3-tier daily token system: Tier 1 (20 tokens/day) on signup, Tier 2 (50) on email verification, Tier 3 (100) on full profile completion
- Profile page accessible via email link in header: editable display name, GitHub URL, LinkedIn URL, country dropdown (ISO 3166-1 alpha-2)
- Profile document auto-created on first access with safe defaults; stored in dedicated `profiles` Firestore collection
- Email verification via Amazon SES: UUID tokens with 24h TTL, click-through validation, automatic Tier 2 upgrade
- Tier 3 is permanent once earned — `profile_completed_at` timestamp is write-once, never cleared
- Password-based account protection: bcrypt hashing, conditional password prompt on login for accounts with passwords set
- Google OAuth account linking: link/unlink on profile page, Google sign-in button on login form, ID token validation via Google tokeninfo endpoint
- Auth router: set-password, login, check-email, google/link, google/login, google/unlink endpoints
- Profile router: GET/PUT profile, POST verify-email, GET verify token endpoints with Pydantic V2 validation
- Country field for upcoming leaderboard feature — validated via `pycountry`, stored as ISO 3166-1 alpha-2
- Tier-aware token reset: midnight UTC reset uses profile tier (20/50/100) instead of hardcoded 100
- Frontend SessionContext updated with tier/dailyLimit fields; TokenDisplay shows dynamic `X / {dailyLimit}`
- Dual-mode support: SQLiteProfileClient for local mode, FirestoreProfileClient for cloud — same `get_profile_client()` factory pattern
- Property tests (18 Hypothesis/fast-check properties): profile validation, tier determination, bcrypt round-trip, URL format, country codes, token display, Google OAuth uniqueness

## Landing Page Redesign (Spec 180) - 2026-04-04

- Shared Header component: persistent sticky header with logo, nav links, auth-aware state (email/tokens/logout vs Join Waitlist CTA)
- Header integrated into root layout; inline header bar removed from protected layout - auth-guard logic preserved
- Landing page restructured: Hero → ScenarioBanner → Value Props → GitHub CTA in centered max-w-[1200px] container
- Value proposition cards redesigned with Lucide React icons, brand color tinted backgrounds, responsive 3-column grid
- GitHub community CTA section with gradient accent, GitHub icon, and external link to public repo
- All color references use brand-* Tailwind tokens or CSS custom properties - zero inline hex values
- Mobile-responsive: compact header below 768px, stacked cards below 640px, no horizontal overflow at 320px minimum
- Unit tests for Header component (logo, nav links, auth states) and landing page (section order, value props, GitHub CTA, brand colors)

## Hybrid Agent Memory (Spec 110) - 2026-04-04

- Milestone summary generator: lightweight LLM call per agent at configurable turn intervals produces ≤300-token strategic summaries capturing key positions, concessions, disputes, and trajectory
- Configurable sliding window: `sliding_window_size` scenario parameter (default 3) replaces hardcoded window from spec 100
- Full history elimination: after first milestone, prompt builder excludes all raw history beyond the sliding window - token cost per turn becomes bounded regardless of negotiation length
- `milestone_interval` scenario parameter (default 4) controls turn cycles between summary generations
- Milestone summaries include agent-private reasoning context (inner thoughts, strategy) for perspective-aware compression
- Non-blocking failure: LLM failure for one agent's summary does not block other agents or the negotiation
- Dispatcher integration: milestone generation triggers after turn advancement, before next agent node runs
- "Milestone Summaries" toggle in Advanced Options - visually disabled when structured memory is off, auto-enables structured memory when toggled on
- Server-side dependency enforcement: `milestone_summaries_enabled=True` forces `structured_memory_enabled=True` regardless of request payload
- Full backward compatibility: disabled by default, missing fields default safely, existing sessions and scenario JSONs unaffected
- Property tests: NegotiationParams round-trip, state initialization invariants, milestone serialization round-trip, prompt token boundedness

## Structured Agent Memory (Spec 100) - 2026-04-03

- Per-agent `AgentMemory` Pydantic V2 model: typed fields for offer history, concessions, open items, tactics, red lines, compliance status, and turn count
- Memory-aware prompt builder: structured memory + sliding window of last 3 messages replaces full history transcript when enabled
- Deterministic memory extraction in `_update_state`: appends offers, tracks opposing offers, increments turn count - no extra LLM calls
- Stall detector reads `my_offers` directly from `agent_memories` when enabled, bypassing full history re-parsing
- `structured_memory_enabled` flag threaded through `NegotiationState`, `NegotiationStateModel`, `StartNegotiationRequest`, and Firestore persistence
- Collapsible "Advanced Options" section on Arena Selector with labeled toggle for structured agent memory
- Full backward compatibility: disabled by default, missing fields default to `False`/`{}`, existing sessions unaffected
- Property tests: AgentMemory round-trip, JSON serializability, state initialization, converter round-trip, prompt format, memory extraction, opposing offer capture, stall detector equivalence

## A2A Local Battle Arena (Spec 080) - 2026-04-03

- Dual-mode architecture: single `RUN_MODE` env var switches between cloud (GCP) and local (Docker) with zero code changes
- `SessionStore` protocol abstracting Firestore and SQLite - implementations swappable at runtime
- `SQLiteSessionClient` with aiosqlite for zero-cloud-config local persistence
- LiteLLM-based model router for local mode - supports OpenAI, Anthropic, and Ollama providers
- Ollama Docker Compose sidecar with auto-pull init service - working LLM out of the box, no API keys needed
- Transparent model mapping: scenario `model_id` values (e.g., `gemini-2.5-flash`) resolve to local provider equivalents
- `LLM_MODEL_OVERRIDE` and `MODEL_MAP` env vars for full model routing control
- Auth gate bypass in local mode - no waitlist, no token limits, no email validation
- Lazy GCP imports - local mode starts without any Google Cloud SDK packages installed
- `docker-compose.yml` with backend, frontend, ollama, and ollama-pull services (health checks, named volumes)
- Frontend `NEXT_PUBLIC_RUN_MODE` detection - skips landing page and hides token counter in local mode
- `.env.example` with grouped variables, inline docs, and zero-config Ollama defaults
- Property tests: session round-trip, missing session errors, update merge, model mapping validity, override precedence, Ollama model resolution, Ollama no-API-key requirement, RUN_MODE validation, HTTP 503 on DatabaseConnectionError, scenario state identity across modes

## World-Class README & Contributor Hub (Spec 120) - 2026-04-02

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

## Agent Advanced Configuration (Spec 090) - 2026-04-02

- "Advanced Config" button on each agent card with settings icon and active-state indicator
- Modal interface for per-agent custom prompt injection (free-text, 500 char limit with live counter)
- Model Selector dropdown populated from `GET /api/v1/models` - override any agent's default LLM
- Custom prompts appended to agent system messages with clear delimiter; model overrides routed through Model Router
- Backend validation: HTTP 422 on oversized prompts or unrecognized model IDs
- State management: overrides persist within a session, reset on scenario change
- Responsive modal layout - bottom sheet on mobile, centered dialog on desktop

## Glass Box Simulation UI (Spec 060) - 2026-04-01

- Arena Selector with scenario dropdown, agent cards, and information toggles
- Terminal Panel - dark monospace display for agent inner thoughts
- Chat Panel - color-coded bubbles for public messages (N-agent compatible)
- Metrics Dashboard - live current offer, regulator traffic lights, turn counter
- SSE client with auto-reconnect and typed event dispatch
- Outcome Receipt with deal summary, ROI metrics, and replay CTAs
- Responsive layout: side-by-side ≥1024px, stacked on mobile

## CI/CD Pipelines (Spec 070) - 2026-04-01

- Google Cloud Build pipeline (`cloudbuild.yaml`) with substitution variables
- Parallel Docker builds for backend and frontend
- Automatic push to Artifact Registry (commit SHA + `latest` tags)
- Cloud Run deployment with service account identity
- Cloud Build trigger on `main` branch (Terragrunt-managed)
- Least-privilege Cloud Build SA permissions

## Frontend Gate & Waitlist (Spec 050) - 2026-04-01

- Next.js 14 App Router with Tailwind CSS and Lucide React
- High-conversion landing page with value proposition
- Email waitlist form with Firestore persistence
- Access gate - sandbox routes protected behind email capture
- Token system: 100 tokens/day per email, midnight UTC reset
- Server-side token deduction via atomic Firestore operations
- Firestore security rules preventing client-side token manipulation

## Scenario Config Engine (Spec 040) - 2026-04-01

- JSON schema for Arena Scenarios with full validation
- Scenario loader with typed error hierarchy
- Auto-discovery registry - drop a `.scenario.json` file, zero code changes
- Toggle injector for information asymmetry (hidden context per agent role)
- Pretty printer with round-trip integrity
- 3 MVP scenarios: Talent War, M&A Buyout, Enterprise B2B Sales
- REST endpoints: `GET /api/v1/scenarios`, `GET /api/v1/scenarios/{id}`

## LangGraph Orchestration (Spec 030) - 2026-04-01

- LangGraph state machine with config-driven N-agent turn-based protocol
- Generic AgentNode factory - zero code changes to add new agent roles
- Dynamic graph construction from scenario JSON (no hardcoded role names)
- Dispatcher-based routing with conditional edges
- Vertex AI Model Router: Gemini 2.5 Flash, Claude 3.5 Sonnet, Claude Sonnet 4, Gemini 2.5 Pro
- Fallback model support with configurable timeouts
- Typed output parsing: `NegotiatorOutput`, `RegulatorOutput`, `ObserverOutput`
- N-agent termination: price convergence, max turns, regulator block
- Bidirectional state conversion (LangGraph TypedDict ↔ Pydantic)

## Backend Core & SSE Streaming (Spec 020) - 2026-04-01

- FastAPI application with Pydantic V2 validation and `/api/v1` prefix
- CORS middleware with configurable origins
- Health check endpoint (`GET /api/v1/health`) for Cloud Run probes
- NegotiationState Pydantic model with N-agent support
- Firestore client module for session CRUD with typed errors
- SSE streaming endpoint (`GET /api/v1/negotiation/stream/{session_id}`)
- Typed SSE event models: `agent_thought`, `agent_message`, `negotiation_complete`, `error`
- Rate limiting - max 3 concurrent SSE connections per email

## GCP Infrastructure (Spec 010) - 2026-03-31

- Monorepo scaffolding with `/infra`, `/backend`, `/frontend`, `/docs` directories
- Terragrunt-managed remote state on GCS with native locking
- Cloud Run services for backend (FastAPI) and frontend (Next.js)
- Artifact Registry Docker repository for container images
- Firestore Native mode database for sessions and waitlist
- Vertex AI API enabled for foundation model access
- Least-privilege IAM service accounts (Backend_SA, Frontend_SA)
