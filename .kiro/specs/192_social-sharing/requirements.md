# Requirements Document

## Introduction

Social sharing for the JuntoAI A2A Outcome Receipt (Screen 4). After a negotiation completes, users can share their negotiation results via social media (LinkedIn, X/Twitter, Facebook), direct URL, or email. This requires: (1) persisting completed negotiations with a public-access link, (2) generating shareable post content with AI-generated images, (3) JuntoAI A2A branding in all shared content, and (4) direct sharing via URL copy and email.

Currently, negotiation sessions are stored in Firestore/SQLite but are only accessible to the authenticated session owner via the SSE stream endpoint. There is no public read path, no share-friendly slug, and no mechanism to view a completed negotiation without being the owner. This spec adds the persistence, public access, content generation, and sharing UI needed to make negotiations shareable.

## Glossary

- **Outcome_Receipt**: Screen 4 of the core user flow — the overlay shown after a negotiation reaches a terminal state (Agreed, Blocked, or Failed). Displays deal terms, participant summaries, performance metrics, and CTAs. This is the screen from which sharing is triggered.
- **Share_Payload**: A structured object containing all data needed to render a shared negotiation: session metadata, deal status, final summary, participant summaries, scenario name, and elapsed time. Stored as a Firestore/SQLite document keyed by a Share_Slug.
- **Share_Slug**: A URL-safe, unique, short identifier (e.g. 8-character alphanumeric string) used in the public share URL. Maps to a Share_Payload document. Not the same as the session_id (which is a 32-char hex UUID and should not be exposed publicly).
- **Public_Share_Page**: A read-only Next.js page at `/share/{share_slug}` that renders a completed negotiation for unauthenticated viewers. Does not require login or token balance.
- **Share_Image**: An AI-generated image (via Vertex AI Imagen or equivalent) that visually summarizes the negotiation highlights — participants, outcome, and key metrics. Used as the Open Graph image and attached to social media posts.
- **Social_Post_Text**: Auto-generated text for social media posts containing: a brief negotiation summary, JuntoAI A2A branding line ("Created with JuntoAI A2A"), the public share URL, and relevant hashtags (#JuntoAI #A2A #AIAgents #Negotiation).
- **Share_Service**: Backend service responsible for creating Share_Payloads, generating Share_Slugs, orchestrating image generation, and composing Social_Post_Text.
- **Share_Panel**: A UI component on the Outcome_Receipt that provides sharing options: social media buttons (LinkedIn, X, Facebook), copy URL, and email share.

## Requirements

### Requirement 1: Share Payload Persistence

**User Story:** As a user, I want my completed negotiation to be saved with a shareable link, so that other people can view the full discussion after I share it.

#### Acceptance Criteria

1. WHEN a user clicks a "Share" button on the Outcome_Receipt, THE Share_Service SHALL create a Share_Payload document containing: scenario name, scenario description, deal status, final summary (including participant summaries, outcome text, current offer, turns completed, warnings), elapsed time, agent names and roles, and a created_at timestamp.
2. THE Share_Service SHALL generate a Share_Slug as an 8-character alphanumeric string that is unique across all existing Share_Payload documents.
3. THE Share_Service SHALL store the Share_Payload in a dedicated `shared_negotiations` Firestore collection (cloud mode) or SQLite table (local mode), keyed by the Share_Slug.
4. WHEN a Share_Payload already exists for a given session_id, THE Share_Service SHALL return the existing Share_Slug instead of creating a duplicate.
5. THE Share_Payload SHALL NOT include raw negotiation history messages, hidden context, custom prompts, model overrides, or any other sensitive session internals — only the public-facing summary data visible on the Outcome_Receipt.
6. IF the Share_Payload creation fails due to a database error, THEN THE Share_Service SHALL return an error response with a descriptive message and HTTP 500 status code.

### Requirement 2: Public Share Page

**User Story:** As a recipient of a shared link, I want to view the full negotiation summary without logging in, so that I can understand the discussion outcome.

#### Acceptance Criteria

1. THE system SHALL serve a public page at the route `/share/{share_slug}` that renders the negotiation summary without requiring authentication or token balance.
2. WHEN a valid Share_Slug is provided, THE Public_Share_Page SHALL display: the scenario name, deal status with appropriate visual styling (green for Agreed, yellow for Blocked, gray for Failed), final offer or outcome text, participant summaries with agent names and roles, turn count, warning count, and elapsed time.
3. WHEN an invalid or non-existent Share_Slug is provided, THE Public_Share_Page SHALL display a "Negotiation not found" message with a CTA linking to the JuntoAI landing page.
4. THE Public_Share_Page SHALL include Open Graph meta tags: `og:title` (scenario name + deal status), `og:description` (outcome summary text, max 200 characters), `og:image` (Share_Image URL), and `og:url` (canonical share URL).
5. THE Public_Share_Page SHALL include Twitter Card meta tags: `twitter:card` set to "summary_large_image", `twitter:title`, `twitter:description`, and `twitter:image` matching the Open Graph values.
6. THE Public_Share_Page SHALL include a JuntoAI A2A branded header with the logo and a "Try JuntoAI A2A" CTA button linking to the landing page.
7. THE Public_Share_Page SHALL render correctly on viewports from 320px to 1920px wide, using responsive layout consistent with the existing styling guide.

### Requirement 3: Share Image Generation

**User Story:** As a user sharing on social media, I want an AI-generated image that visually represents my negotiation, so that my post is eye-catching and informative.

#### Acceptance Criteria

1. WHEN a Share_Payload is created, THE Share_Service SHALL generate a Share_Image by calling an image generation API (Vertex AI Imagen) with a prompt derived from the negotiation context: scenario name, participant roles, deal status, and key outcome metrics.
2. THE Share_Image SHALL be stored in a GCP Cloud Storage bucket (cloud mode) or local filesystem directory (local mode) with a path derived from the Share_Slug.
3. THE Share_Image SHALL be served via a publicly accessible URL that does not require authentication.
4. THE image generation prompt SHALL NOT include any raw negotiation messages, hidden context, or sensitive session data — only the public summary information.
5. IF the image generation API call fails or times out, THEN THE Share_Service SHALL fall back to a static branded placeholder image (JuntoAI A2A logo with scenario name overlaid as text) and proceed with sharing without blocking the user.
6. THE Share_Image generation SHALL complete within 15 seconds. IF the generation exceeds 15 seconds, THEN THE Share_Service SHALL use the fallback placeholder image.

### Requirement 4: Social Media Post Composition

**User Story:** As a user, I want to share a pre-composed post on LinkedIn, X, or Facebook that summarizes my negotiation with proper branding, so that I can share with minimal effort.

#### Acceptance Criteria

1. THE Share_Service SHALL compose a Social_Post_Text containing: (a) a one-sentence negotiation summary derived from the deal status and outcome (e.g. "I just simulated an M&A Buyout negotiation — the AI agents reached a deal at $4.2M"), (b) participant names and their roles, (c) the public share URL, (d) the branding line "Created with @JuntoAI A2A", and (e) hashtags: #JuntoAI #A2A #AIAgents #Negotiation.
2. THE Social_Post_Text for X/Twitter SHALL NOT exceed 280 characters. WHEN the full text exceeds 280 characters, THE Share_Service SHALL truncate the negotiation summary portion while preserving the URL, branding line, and hashtags.
3. THE Social_Post_Text for LinkedIn and Facebook SHALL NOT exceed 3000 characters.
4. WHEN the user clicks the LinkedIn share button, THE Share_Panel SHALL open a new browser tab with the LinkedIn share URL (`https://www.linkedin.com/sharing/share-offsite/?url={share_url}`) pre-populated.
5. WHEN the user clicks the X/Twitter share button, THE Share_Panel SHALL open a new browser tab with the X intent URL (`https://twitter.com/intent/tweet?text={encoded_post_text}&url={share_url}`) pre-populated with the Social_Post_Text.
6. WHEN the user clicks the Facebook share button, THE Share_Panel SHALL open a new browser tab with the Facebook share dialog URL (`https://www.facebook.com/sharer/sharer.php?u={share_url}`) pre-populated.

### Requirement 5: URL and Email Sharing

**User Story:** As a user, I want to copy the share link or send it via email to my manager or business partner, so that I can share the negotiation through direct channels.

#### Acceptance Criteria

1. WHEN the user clicks the "Copy Link" button on the Share_Panel, THE system SHALL copy the public share URL to the clipboard and display a brief confirmation toast ("Link copied").
2. WHEN the user clicks the "Share via Email" button, THE system SHALL open the user's default email client via a `mailto:` link with: (a) a pre-filled subject line containing the scenario name and deal status (e.g. "JuntoAI A2A: M&A Buyout — Deal Agreed"), and (b) a pre-filled body containing the negotiation summary, the public share URL, and the JuntoAI A2A branding line.
3. THE "Copy Link" button SHALL provide visual feedback: a checkmark icon replacing the copy icon for 2 seconds after a successful copy.
4. IF the clipboard API is unavailable (e.g. non-HTTPS context in local mode), THEN THE system SHALL display the share URL in a selectable text input field as a fallback.

### Requirement 6: Share Panel UI on Outcome Receipt

**User Story:** As a user viewing the Outcome Receipt, I want clearly visible sharing options, so that I can easily share my negotiation results.

#### Acceptance Criteria

1. THE Outcome_Receipt component SHALL render a Share_Panel section with `data-testid="share-panel"` below the existing action buttons ("Run Another Scenario" and "Reset with Different Variables").
2. THE Share_Panel SHALL display four sharing options: LinkedIn (with LinkedIn icon), X/Twitter (with X icon), Facebook (with Facebook icon), Copy Link (with link/copy icon), and Share via Email (with mail icon).
3. THE Share_Panel SHALL be visible only after the negotiation reaches a terminal state (Agreed, Blocked, or Failed).
4. WHEN the user clicks any share button for the first time in a session, THE Share_Panel SHALL trigger the Share_Payload creation (lazy creation — the payload is not created until the user actually wants to share).
5. WHILE the Share_Payload is being created (API call in progress), THE Share_Panel SHALL display a loading state on the clicked button and disable all share buttons to prevent duplicate requests.
6. THE Share_Panel SHALL render correctly on viewports from 320px to 1920px wide, with share buttons arranged horizontally on desktop (1024px and above) and in a 2-column grid on mobile.

### Requirement 7: Public Share API Endpoint

**User Story:** As a developer, I want a clean API for creating and retrieving share payloads, so that the frontend can interact with the sharing system through well-defined endpoints.

#### Acceptance Criteria

1. THE system SHALL expose a `POST /api/v1/share` endpoint that accepts a JSON body with `session_id` (required) and `email` (required), validates that the email matches the session owner, creates or retrieves the Share_Payload, and returns the Share_Slug and public share URL.
2. THE system SHALL expose a `GET /api/v1/share/{share_slug}` endpoint that returns the Share_Payload as JSON without requiring authentication.
3. WHEN the `POST /api/v1/share` endpoint receives a session_id that does not exist, THE system SHALL return HTTP 404 with a descriptive error message.
4. WHEN the `POST /api/v1/share` endpoint receives an email that does not match the session owner, THE system SHALL return HTTP 403 with a descriptive error message.
5. WHEN the `GET /api/v1/share/{share_slug}` endpoint receives a non-existent slug, THE system SHALL return HTTP 404 with a descriptive error message.
6. THE `POST /api/v1/share` response SHALL include: `share_slug` (string), `share_url` (string, full public URL), `social_post_text` (object with `twitter`, `linkedin`, and `facebook` variants), and `share_image_url` (string, URL of the generated or fallback image).
7. FOR ALL valid Share_Payload objects, serializing to JSON via `.model_dump_json()` and deserializing back via `SharePayload.model_validate_json()` SHALL produce an equivalent object (round-trip property).

### Requirement 8: Share Payload Schema

**User Story:** As a developer, I want well-defined Pydantic models for the share data, so that the contract between backend and frontend is explicit and validated.

#### Acceptance Criteria

1. THE system SHALL define a `SharePayload` Pydantic V2 model with fields: `share_slug` (str, min_length=8, max_length=8), `session_id` (str), `scenario_name` (str), `scenario_description` (str), `deal_status` (Literal["Agreed", "Blocked", "Failed"]), `outcome_text` (str), `final_offer` (float, ge=0), `turns_completed` (int, ge=0), `warning_count` (int, ge=0), `participant_summaries` (list of ParticipantSummary), `elapsed_time_ms` (int, ge=0), `share_image_url` (str), `created_at` (datetime).
2. THE system SHALL define a `ParticipantSummary` Pydantic V2 model with fields: `role` (str), `name` (str), `agent_type` (str), and `summary` (str).
3. THE system SHALL define a `CreateShareRequest` Pydantic V2 model with fields: `session_id` (str, min_length=1) and `email` (str, min_length=1).
4. THE system SHALL define a `CreateShareResponse` Pydantic V2 model with fields: `share_slug` (str), `share_url` (str), `social_post_text` (SocialPostText), and `share_image_url` (str).
5. THE system SHALL define a `SocialPostText` Pydantic V2 model with fields: `twitter` (str, max_length=280), `linkedin` (str, max_length=3000), and `facebook` (str, max_length=3000).
6. FOR ALL valid SharePayload instances, serializing to JSON via `.model_dump_json()` and deserializing back via `SharePayload.model_validate_json()` SHALL produce an equivalent object (round-trip property).
7. FOR ALL valid SocialPostText instances, the `twitter` field length SHALL be less than or equal to 280 characters.
