# Implementation Plan: User Profile Token Upgrade

## Overview

Implement a 3-tier daily token system (20/50/100 tokens) driven by profile milestones. Backend: FastAPI profile router, tier calculator, email verifier (SES), Firestore profile/verification collections. Frontend: profile page, tier-aware token display, updated session context. Property-based tests validate all 14 correctness properties.

## Tasks

- [ ] 1. Create backend profile models and tier calculator
  - [ ] 1.1 Create Pydantic V2 profile models (`backend/app/models/profile.py`)
    - Define `ProfileDocument`, `ProfileUpdateRequest`, `ProfileResponse` models
    - Implement field validators: display name (2-100 chars, trimmed), GitHub URL (`https://github.com/{username}`), LinkedIn URL (`https://[www.]linkedin.com/in/{slug}`)
    - _Requirements: 3.1, 3.3, 3.4, 5.1, 5.2, 5.4, 9.6_

  - [ ] 1.2 Create tier calculator pure functions (`backend/app/services/tier_calculator.py`)
    - Implement `calculate_tier(profile_completed_at, email_verified) -> int` returning 1, 2, or 3
    - Implement `get_daily_limit(tier) -> int` returning 20, 50, or 100
    - Implement `is_profile_complete(display_name, email_verified, github_url, linkedin_url) -> bool`
    - Define `TIER_LIMITS = {1: 20, 2: 50, 3: 100}`
    - _Requirements: 6.6, 6.7, 7.1, 7.2_

  - [ ]* 1.3 Write property tests for profile validation (Hypothesis)
    - **Property 3: Display name length validation** — generate random strings, verify accept/reject at 2-100 char boundary after trimming
    - **Validates: Requirements 3.1, 3.3**

  - [ ]* 1.4 Write property tests for display name trimming (Hypothesis)
    - **Property 4: Display name whitespace trimming** — generate strings with arbitrary leading/trailing whitespace, verify `stored == input.strip()`
    - **Validates: Requirements 3.4**

  - [ ]* 1.5 Write property tests for URL validation (Hypothesis)
    - **Property 5: URL format validation** — generate random strings, verify GitHub/LinkedIn pattern matching accept/reject
    - **Validates: Requirements 5.1, 5.2, 5.4**

  - [ ]* 1.6 Write property tests for tier determination (Hypothesis)
    - **Property 7: Tier determination** — generate all combos of `profile_completed_at` (null/non-null) and `email_verified` (true/false), verify tier and daily limit
    - **Validates: Requirements 6.7, 7.1, 7.2**

  - [ ]* 1.7 Write property tests for profile completeness (Hypothesis)
    - **Property 8: Profile completeness evaluation** — generate all combos of display_name, email_verified, github_url, linkedin_url, verify completeness logic
    - **Validates: Requirements 5.5, 6.6**

- [ ] 2. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 3. Create Firestore profile client and email verifier service
  - [ ] 3.1 Create profile Firestore client (`backend/app/db/profile_client.py`)
    - Implement get-or-create profile (create with defaults if not exists, return existing if exists)
    - Implement update profile fields (display_name, github_url, linkedin_url)
    - Implement read profile by email
    - Use existing `firestore.AsyncClient` pattern from `firestore_client.py`
    - CRUD operations on `verification_tokens` collection (create, read, delete)
    - _Requirements: 1.1, 1.2, 1.3, 9.1, 9.2_

  - [ ] 3.2 Create email verifier service (`backend/app/services/email_verifier.py`)
    - Generate UUID-based verification tokens with 24h TTL
    - Store tokens in `verification_tokens` Firestore collection with `email`, `created_at`, `expires_at`
    - Send verification email via Amazon SES (boto3 `ses.send_email`)
    - Validate tokens on click-through: check existence, check expiry, mark email verified
    - Configure SES with IAM credentials from backend service account
    - _Requirements: 4.1, 4.2, 4.3, 4.5, 4.6, 4.8_

  - [ ]* 3.3 Write property test for profile initialization defaults (Hypothesis)
    - **Property 1: Profile initialization defaults** — generate random emails, verify all default fields match spec
    - **Validates: Requirements 1.1, 1.2**

  - [ ]* 3.4 Write property test for profile get-or-create idempotency (Hypothesis)
    - **Property 2: Profile get-or-create idempotency** — create profile, modify fields, call get-or-create again, verify modifications preserved
    - **Validates: Requirements 1.3**

  - [ ]* 3.5 Write property test for verification token generation (Hypothesis)
    - **Property 11: Verification token generation** — generate multiple tokens, verify uniqueness and `expires_at == created_at + 24h`
    - **Validates: Requirements 4.1, 4.2**

- [ ] 4. Create profile router with all 4 endpoints
  - [ ] 4.1 Implement profile router (`backend/app/routers/profile.py`)
    - `GET /api/v1/profile/{email}` — get-or-create profile, return profile + tier info via `ProfileResponse`
    - `PUT /api/v1/profile/{email}` — validate input, update profile, evaluate completeness, trigger tier upgrade if newly complete (Firestore transaction for atomicity)
    - `POST /api/v1/profile/{email}/verify-email` — generate token, send SES email
    - `GET /api/v1/profile/verify/{token}` — validate token, mark email verified, upgrade to Tier 2 if applicable (Firestore transaction)
    - Return 404 for non-existent profiles on PUT, return appropriate error codes (410 expired, 404 invalid token)
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 4.3, 4.4, 4.5, 4.6, 6.3, 6.4, 6.5_

  - [ ] 4.2 Register profile router in FastAPI app (`backend/app/main.py`)
    - Import and include profile router in the `api_router` with `PUT` added to `allow_methods` in CORS middleware
    - _Requirements: 9.1_

  - [ ]* 4.3 Write property test for profile round-trip persistence (Hypothesis)
    - **Property 6: Profile field persistence round-trip** — generate valid updates, store via PUT, read via GET, verify field equality
    - **Validates: Requirements 3.2, 5.3**

  - [ ]* 4.4 Write property test for tier upgrade on profile completion (Hypothesis)
    - **Property 9: Tier upgrade on profile completion** — generate profiles transitioning to complete, verify `profile_completed_at` set and `token_balance = max(current, 100)`
    - **Validates: Requirements 6.3, 6.4, 6.5**

  - [ ]* 4.5 Write property test for email verification tier 2 upgrade (Hypothesis)
    - **Property 10: Email verification triggers tier 2 upgrade** — generate valid tokens, verify `email_verified = true` and `token_balance = max(current, 50)` when `profile_completed_at` is null
    - **Validates: Requirements 4.3, 4.4, 6.2**

- [ ] 5. Checkpoint — Ensure all backend tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 6. Update existing backend token logic for tier awareness
  - [ ] 6.1 Update token reset logic for tier-aware resets
    - Modify the token reset flow (in `resetTokens` / negotiation router) to check `profiles` collection for tier determination
    - Reset to 100 if `profile_completed_at` non-null, 50 if `email_verified` true, 20 otherwise
    - _Requirements: 10.1, 10.2, 10.3, 10.4_

  - [ ] 6.2 Update waitlist signup to set initial balance to 20
    - Modify `joinWaitlist` / waitlist creation to set `token_balance` to 20 instead of 100
    - _Requirements: 6.1_

  - [ ]* 6.3 Write property test for tier-aware token reset (Hypothesis)
    - **Property 12: Tier-aware token reset** — generate users at each tier, verify correct reset balance (20/50/100)
    - **Validates: Requirements 10.2, 10.3, 10.4**

  - [ ]* 6.4 Write property test for waitlist signup initial balance (Hypothesis)
    - **Property 14: Waitlist signup initial balance** — generate random emails, verify initial `token_balance` is 20
    - **Validates: Requirements 6.1**

- [ ] 7. Checkpoint — Ensure all backend tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 8. Update frontend SessionContext and token utilities
  - [ ] 8.1 Add tier fields to SessionContext (`frontend/context/SessionContext.tsx`)
    - Add `tier`, `dailyLimit` to `SessionState` interface
    - Add `updateTier(tier: number, dailyLimit: number, tokenBalance: number)` method
    - Update `login` to accept and store `tier` and `dailyLimit`
    - Persist `tier` and `dailyLimit` to sessionStorage
    - _Requirements: 8.4, 8.5_

  - [ ] 8.2 Update token utility functions (`frontend/lib/tokens.ts`)
    - Modify `resetTokens` to accept `dailyLimit` parameter instead of hardcoded 100
    - Modify `formatTokenDisplay` to accept `dailyLimit` parameter: `Tokens: {balance} / {dailyLimit}`
    - _Requirements: 8.1, 8.2, 8.3_

  - [ ] 8.3 Update TokenDisplay component (`frontend/components/TokenDisplay.tsx`)
    - Read `dailyLimit` from SessionContext
    - Pass `dailyLimit` to `formatTokenDisplay`
    - _Requirements: 8.1, 8.2, 8.3_

  - [ ]* 8.4 Write property test for token display format (fast-check)
    - **Property 13: Token display format** — generate random balance/limit pairs, verify output is `"Tokens: {clamped_balance} / {dailyLimit}"`
    - **Validates: Requirements 8.1, 8.2, 8.3**

- [ ] 9. Update WaitlistForm and protected layout
  - [ ] 9.1 Update WaitlistForm (`frontend/components/WaitlistForm.tsx`)
    - Set initial token balance to 20 (Tier 1) instead of 100 on signup and reset
    - Pass tier info (tier=1, dailyLimit=20) to `login` in SessionContext
    - _Requirements: 6.1_

  - [ ] 9.2 Update protected layout header (`frontend/app/(protected)/layout.tsx`)
    - Make the email `<span>` a clickable `<Link>` to `/profile`
    - _Requirements: 2.1_

- [ ] 10. Create profile page
  - [ ] 10.1 Create profile page component (`frontend/app/(protected)/profile/page.tsx`)
    - Form with editable fields: display name, GitHub URL, LinkedIn URL
    - Email verification status display with "Verify Email" button (hidden when already verified, show "Verified" badge)
    - Progress indicator showing completion steps (email verified, display name set, professional link added)
    - Save button triggers `PUT /api/v1/profile/{email}` via API client
    - On successful save with tier upgrade, call `updateTier` on SessionContext to reflect immediately
    - Redirect to landing page if not authenticated
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 4.7_

  - [ ] 10.2 Create profile API client functions (`frontend/lib/profile.ts`)
    - `getProfile(email)` — calls `GET /api/v1/profile/{email}`
    - `updateProfile(email, data)` — calls `PUT /api/v1/profile/{email}`
    - `requestEmailVerification(email)` — calls `POST /api/v1/profile/{email}/verify-email`
    - _Requirements: 9.1, 9.2, 9.3_

  - [ ] 10.3 Create email verification callback page (`frontend/app/(protected)/profile/verify/page.tsx`)
    - Read token from URL query params
    - Call `GET /api/v1/profile/verify/{token}` on mount
    - Display success, expired (with resend option), or invalid token states
    - _Requirements: 4.3, 4.5, 4.6_

- [ ] 11. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 12. Integration wiring and final validation
  - [ ] 12.1 Wire negotiation router to use tier-aware token lookup
    - Update `start_negotiation` in `backend/app/routers/negotiation.py` to fetch tier from profile when displaying `tokens_remaining`
    - Update token deduction in `event_stream` finally block to use tier-aware daily limit
    - _Requirements: 6.7, 10.1_

  - [ ]* 12.2 Write backend integration tests for profile endpoints
    - Test GET profile (creates new + returns existing)
    - Test PUT profile (valid update, validation errors, tier upgrade trigger)
    - Test POST verify-email (mock SES)
    - Test GET verify token (valid, expired, invalid)
    - Test 404 for non-existent profile on targeted endpoints
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

  - [ ]* 12.3 Write frontend component tests for profile page
    - Test profile page renders all fields and progress indicator
    - Test save triggers API call and updates session context on tier upgrade
    - Test email verification button visibility based on verification status
    - Test unauthenticated redirect
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 4.7, 8.4_

- [ ] 13. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Backend property tests use Hypothesis with `@settings(max_examples=100)`
- Frontend property tests use fast-check with `fc.assert(property, { numRuns: 100 })`
- Firestore transactions are required for tier upgrade operations (profile + waitlist atomicity)
- `profile_completed_at` is write-once (permanent Tier 3) — never cleared after being set
- Each property test maps to exactly one correctness property from the design document
