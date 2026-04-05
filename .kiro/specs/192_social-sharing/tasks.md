# Implementation Plan: Social Sharing

## Overview

Implement social sharing for the JuntoAI A2A Outcome Receipt. The plan follows a bottom-up approach: data models → store layer → service logic → API router → frontend components → property tests. Each task builds on the previous, with checkpoints to validate incremental progress.

## Tasks

- [ ] 1. Define share data models and exceptions
  - [ ] 1.1 Create `backend/app/models/share.py` with Pydantic V2 models
    - `ParticipantSummary`: role, name, agent_type, summary
    - `SharePayload`: share_slug (8-char), session_id, scenario_name, scenario_description, deal_status (Literal["Agreed","Blocked","Failed"]), outcome_text, final_offer (ge=0), turns_completed (ge=0), warning_count (ge=0), participant_summaries, elapsed_time_ms (ge=0), share_image_url, created_at
    - `SocialPostText`: twitter (max_length=280), linkedin (max_length=3000), facebook (max_length=3000)
    - `CreateShareRequest`: session_id (min_length=1), email (min_length=1)
    - `CreateShareResponse`: share_slug, share_url, social_post_text, share_image_url
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_
  - [ ] 1.2 Add `ShareNotFoundError` to `backend/app/exceptions.py`
    - Follow existing `SessionNotFoundError` pattern with share_slug parameter
    - _Requirements: 7.5_

  - [ ]* 1.3 Write property test: SharePayload round-trip serialization
    - **Property 7: SharePayload round-trip serialization**
    - Create `backend/tests/property/test_share_properties.py`
    - Build a Hypothesis composite strategy generating valid `SharePayload` instances (random slugs, deal statuses, participant lists, timestamps)
    - Assert `SharePayload.model_validate_json(payload.model_dump_json()) == payload`
    - **Validates: Requirements 7.7, 8.6**

- [ ] 2. Implement share store layer (Firestore + SQLite)
  - [ ] 2.1 Add `ShareStore` protocol to `backend/app/db/base.py`
    - `create_share(payload: SharePayload) -> None`
    - `get_share(share_slug: str) -> SharePayload | None`
    - `get_share_by_session(session_id: str) -> SharePayload | None`
    - Follow existing `SessionStore` protocol pattern with `@runtime_checkable`
    - _Requirements: 1.3, 1.4_
  - [ ] 2.2 Implement `FirestoreShareClient` in `backend/app/db/firestore_client.py`
    - Collection: `shared_negotiations`, document ID = share_slug
    - `create_share`: set document with `payload.model_dump()`
    - `get_share`: get by document ID, return `SharePayload` or None
    - `get_share_by_session`: query where `session_id == X`, limit 1
    - _Requirements: 1.3, 1.4_
  - [ ] 2.3 Implement `SQLiteShareClient` in `backend/app/db/sqlite_client.py`
    - Table: `shared_negotiations` (share_slug TEXT PK, session_id TEXT NOT NULL UNIQUE, data JSON NOT NULL, created_at TIMESTAMP)
    - Index: `idx_shared_session` on session_id
    - `create_share`, `get_share`, `get_share_by_session` methods
    - Lazy table creation via `_ensure_share_table()` pattern
    - _Requirements: 1.3, 1.4_

- [ ] 3. Implement image generator service
  - [ ] 3.1 Create `backend/app/services/image_generator.py`
    - `generate_share_image(prompt: str, share_slug: str) -> str`
    - Cloud mode: call Vertex AI Imagen with 15s timeout, store result in GCS bucket, return public URL
    - Local mode: store in `data/share_images/`, return `/api/v1/share/images/{slug}.png`
    - On failure/timeout: return fallback placeholder image URL
    - Use `asyncio.wait_for` for the 15s timeout enforcement
    - _Requirements: 3.1, 3.2, 3.3, 3.5, 3.6_

- [ ] 4. Implement share service (core business logic)
  - [ ] 4.1 Create `backend/app/services/share_service.py`
    - `create_or_get_share(session_id, email) -> CreateShareResponse`: idempotent creation — check existing share by session_id first, build payload from session doc, generate slug, trigger image gen, compose social text
    - `get_share(share_slug) -> SharePayload`: retrieve by slug, raise `ShareNotFoundError` if missing
    - `_generate_slug(existing_slugs) -> str`: 8-char alphanumeric, retry on collision
    - `_build_share_payload(session_doc, scenario, slug) -> SharePayload`: extract ONLY public-facing data — no history, hidden_context, custom_prompts, model_overrides
    - `_build_image_prompt(payload) -> str`: build prompt from public summary data only
    - `_compose_social_text(payload, share_url) -> SocialPostText`: platform-specific text with branding ("Created with @JuntoAI A2A"), hashtags (#JuntoAI #A2A #AIAgents #Negotiation), URL; truncate twitter variant to ≤280 chars preserving URL + branding + hashtags
    - `_compose_mailto(payload, share_url) -> str`: mailto link with subject (scenario name + deal status) and body (summary + URL + branding)
    - Validate email matches session owner, raise HTTP 403 if mismatch
    - _Requirements: 1.1, 1.2, 1.4, 1.5, 1.6, 3.4, 4.1, 4.2, 4.3, 5.2_

  - [ ]* 4.2 Write property test: Slug format and uniqueness
    - **Property 1: Slug format and uniqueness**
    - Generate random sets of existing slugs via Hypothesis
    - Assert returned slug is exactly 8 chars, matches `[a-zA-Z0-9]{8}`, and is not in the existing set
    - **Validates: Requirements 1.2**
  - [ ]* 4.3 Write property test: Idempotent share creation
    - **Property 2: Idempotent share creation**
    - Generate random session_ids, mock DB to track stored documents
    - Call `create_or_get_share` twice with same session_id, assert same slug returned and exactly 1 document stored
    - **Validates: Requirements 1.4**
  - [ ]* 4.4 Write property test: Sensitive data exclusion
    - **Property 3: Sensitive data exclusion**
    - Generate random NegotiationState dicts with non-empty history, hidden_context, custom_prompts, model_overrides
    - Assert `_build_share_payload` and `_build_image_prompt` outputs contain no substrings from those sensitive fields
    - **Validates: Requirements 1.5, 3.4**
  - [ ]* 4.5 Write property test: Social post required elements
    - **Property 4: Social post text contains required elements**
    - Generate random SharePayload instances and share URLs
    - Assert all three platform variants contain: the share URL, "JuntoAI A2A" branding, and at least one hashtag from {#JuntoAI, #A2A, #AIAgents, #Negotiation}
    - **Validates: Requirements 4.1**
  - [ ]* 4.6 Write property test: Social post length constraints
    - **Property 5: Social post text length constraints**
    - Generate random SharePayload with long scenario names and outcome text
    - Assert twitter ≤ 280 chars, linkedin ≤ 3000 chars, facebook ≤ 3000 chars
    - **Validates: Requirements 4.2, 4.3, 8.7**
  - [ ]* 4.7 Write property test: Mailto link composition
    - **Property 6: Mailto link composition**
    - Generate random SharePayload with non-empty scenario_name and deal_status
    - Assert mailto link contains scenario_name in subject, deal_status in subject, share URL in body, "JuntoAI A2A" in body
    - **Validates: Requirements 5.2**

- [ ] 5. Checkpoint — Backend models, store, and service
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 6. Implement share router and wire into FastAPI app
  - [ ] 6.1 Create `backend/app/routers/share.py`
    - `POST /share` — accepts `CreateShareRequest`, validates session ownership, calls `share_service.create_or_get_share`, returns `CreateShareResponse`
    - `GET /share/{share_slug}` — calls `share_service.get_share`, returns `SharePayload` JSON, no auth required
    - Follow existing router patterns (see `auth.py`, `negotiation.py`)
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6_
  - [ ] 6.2 Register share router in `backend/app/main.py`
    - Import and include `share_router` in the `api_router`
    - Add `ShareNotFoundError` exception handler returning HTTP 404
    - _Requirements: 7.1, 7.2_
  - [ ]* 6.3 Write integration tests for share endpoints
    - `POST /api/v1/share` — happy path for each deal status (Agreed, Blocked, Failed)
    - `POST /api/v1/share` — 404 for missing session, 403 for wrong email
    - `GET /api/v1/share/{slug}` — happy path and 404
    - Idempotency: POST twice with same session_id, verify same slug
    - Create `backend/tests/integration/test_share_router.py`
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

- [ ] 7. Implement frontend share API client
  - [ ] 7.1 Create `frontend/lib/share.ts`
    - `createShare(sessionId: string, email: string): Promise<CreateShareResponse>` — POST to `/api/v1/share`
    - `getShare(slug: string): Promise<SharePayload>` — GET from `/api/v1/share/{slug}`
    - TypeScript interfaces for `SharePayload`, `CreateShareResponse`, `SocialPostText`, `ParticipantSummary`
    - Follow existing API client patterns (see `frontend/lib/api.ts`, `frontend/lib/negotiation.ts`)
    - _Requirements: 7.1, 7.2, 7.6_

- [ ] 8. Implement SharePanel UI component
  - [ ] 8.1 Create `frontend/components/glassbox/SharePanel.tsx`
    - 5 share buttons: LinkedIn (LinkedIn icon), X/Twitter (X icon), Facebook (Facebook icon), Copy Link (link icon), Email (mail icon) — use Lucide React icons
    - `data-testid="share-panel"` on the container
    - Lazy creation: first button click triggers `createShare()`, caches response for subsequent clicks
    - Loading state: spinner on clicked button, all buttons disabled during API call
    - LinkedIn: `window.open('https://www.linkedin.com/sharing/share-offsite/?url={share_url}')`
    - X/Twitter: `window.open('https://twitter.com/intent/tweet?text={encoded_text}&url={share_url}')`
    - Facebook: `window.open('https://www.facebook.com/sharer/sharer.php?u={share_url}')`
    - Copy Link: `navigator.clipboard.writeText(share_url)`, show toast "Link copied", checkmark icon for 2s; fallback to selectable text input if clipboard API unavailable
    - Email: `window.location.href = mailto_link` with pre-filled subject and body
    - Responsive: horizontal row ≥1024px, 2-column grid on mobile
    - _Requirements: 4.4, 4.5, 4.6, 5.1, 5.2, 5.3, 5.4, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_
  - [ ] 8.2 Integrate SharePanel into `frontend/components/glassbox/OutcomeReceipt.tsx`
    - Render SharePanel below existing action buttons ("Run Another Scenario" and "Reset with Different Variables")
    - Only render when deal_status is terminal (Agreed, Blocked, or Failed)
    - Pass session_id and email as props
    - _Requirements: 6.1, 6.3_

- [ ] 9. Implement public share page
  - [ ] 9.1 Create `frontend/app/share/[slug]/page.tsx`
    - Server-rendered Next.js page (App Router) — outside `(protected)` layout, no auth required
    - Fetch SharePayload via `GET /api/v1/share/{slug}` at request time
    - Render: scenario name, deal status with color styling (green=Agreed, yellow=Blocked, gray=Failed), final offer, outcome text, participant summaries with names/roles, turn count, warning count, elapsed time
    - 404 state: "Negotiation not found" message with CTA to landing page
    - Branded header: JuntoAI logo + "Try JuntoAI A2A" CTA button
    - Responsive: 320px to 1920px
    - _Requirements: 2.1, 2.2, 2.3, 2.6, 2.7_
  - [ ] 9.2 Implement `generateMetadata()` for Open Graph and Twitter Card meta tags
    - `og:title`: scenario name + deal status
    - `og:description`: outcome summary text, max 200 chars
    - `og:image`: share_image_url
    - `og:url`: canonical share URL
    - `twitter:card`: "summary_large_image"
    - `twitter:title`, `twitter:description`, `twitter:image` matching OG values
    - _Requirements: 2.4, 2.5_
  - [ ]* 9.3 Write property test: Meta tag generation
    - **Property 8: Meta tag generation**
    - Generate random SharePayload instances via Hypothesis (backend test)
    - Assert generated meta tags include og:title with scenario name, og:description ≤ 200 chars, og:image matching share_image_url, og:url containing share_slug, and corresponding twitter:card values
    - **Validates: Requirements 2.4, 2.5**

- [ ] 10. Checkpoint — Full stack integration
  - Ensure all tests pass, ask the user if questions arise.

- [ ]* 11. Write frontend component tests
  - [ ]* 11.1 Write vitest tests for SharePanel
    - Renders 5 share buttons with correct icons
    - Lazy creation: first click triggers API call
    - Loading state: spinner on clicked button, all buttons disabled
    - LinkedIn/X/Facebook open correct URLs via `window.open`
    - Copy Link calls clipboard API, shows toast, fallback on failure
    - Email opens mailto with correct subject/body
    - Responsive layout at mobile/desktop breakpoints
    - _Requirements: 4.4, 4.5, 4.6, 5.1, 5.3, 5.4, 6.2, 6.4, 6.5, 6.6_
  - [ ]* 11.2 Write vitest tests for Public Share Page
    - Renders correct data for each deal status (Agreed, Blocked, Failed)
    - 404 state with CTA to landing page
    - _Requirements: 2.1, 2.2, 2.3_

- [ ] 12. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Property tests use Hypothesis (backend) following existing patterns in `backend/tests/property/`
- Frontend tests use vitest + React Testing Library following existing patterns
- All 8 correctness properties from the design document are covered as property test sub-tasks
- Backend uses Python 3.11+, frontend uses TypeScript (Next.js 14+)
