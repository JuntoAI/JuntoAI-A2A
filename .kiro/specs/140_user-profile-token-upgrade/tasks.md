# Implementation Plan: User Profile Token Upgrade

## Overview

Implement a 3-tier daily token system (20/50/100 tokens) driven by profile milestones. Backend: FastAPI profile router, auth router, tier calculator, email verifier (SES), auth service (bcrypt + Google OAuth), Firestore profile/verification collections. Frontend: profile page with country dropdown + password section + Google OAuth section, tier-aware token display, updated session context, login form with conditional password + Google sign-in. Property-based tests validate all 18 correctness properties.

## Tasks

- [ ] 1. Create backend profile models and tier calculator
  - [ ] 1.1 Create Pydantic V2 profile models (`backend/app/models/profile.py`)
    - Define `ProfileDocument`, `ProfileUpdateRequest`, `ProfileResponse` models
    - `ProfileDocument` includes `password_hash`, `country`, `google_oauth_id` fields (all default `None`)
    - `ProfileUpdateRequest` includes `country` field with ISO 3166-1 alpha-2 validator (using `pycountry`)
    - `ProfileResponse` includes `password_hash_set` (bool, never expose hash), `country`, `google_oauth_id`
    - Implement field validators: display name (2-100 chars, trimmed), GitHub URL (`https://github.com/{username}`), LinkedIn URL (`https://[www.]linkedin.com/in/{slug}`), country (valid ISO 3166-1 alpha-2 via `pycountry`)
    - _Requirements: 3.1, 3.3, 3.4, 5.1, 5.2, 5.4, 9.6, 12.2, 12.4, 12.6, 12.7_

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

  - [ ]* 1.8 Write property test for country code validation (Hypothesis)
    - **Property 17: Country code validation** — generate random strings, verify only valid ISO 3166-1 alpha-2 codes accepted by `validate_country`
    - **Validates: Requirements 12.2, 12.4**

- [ ] 2. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 3. Create Firestore profile client and email verifier service
  - [ ] 3.1 Create profile Firestore client (`backend/app/db/profile_client.py`)
    - Implement get-or-create profile (create with defaults including `password_hash=None`, `country=None`, `google_oauth_id=None` if not exists, return existing if exists)
    - Implement update profile fields (display_name, github_url, linkedin_url, country)
    - Implement read profile by email
    - Implement update `password_hash` field
    - Implement update `google_oauth_id` field (set and clear)
    - Implement query profiles by `google_oauth_id` (for Google OAuth login lookup)
    - Use existing `firestore.AsyncClient` pattern from `firestore_client.py`
    - CRUD operations on `verification_tokens` collection (create, read, delete)
    - _Requirements: 1.1, 1.2, 1.3, 9.1, 9.2, 12.3, 12.6, 12.7, 13.4, 13.7_

  - [ ] 3.2 Create email verifier service (`backend/app/services/email_verifier.py`)
    - Generate UUID-based verification tokens with 24h TTL
    - Store tokens in `verification_tokens` Firestore collection with `email`, `created_at`, `expires_at`
    - Send verification email via Amazon SES (boto3 `ses.send_email`)
    - Validate tokens on click-through: check existence, check expiry, mark email verified
    - Configure SES with IAM credentials from backend service account
    - _Requirements: 4.1, 4.2, 4.3, 4.5, 4.6, 4.8_

  - [ ]* 3.3 Write property test for profile initialization defaults (Hypothesis)
    - **Property 1: Profile initialization defaults** — generate random emails, verify all default fields match spec (including `password_hash=None`, `country=None`, `google_oauth_id=None`)
    - **Validates: Requirements 1.1, 1.2**

  - [ ]* 3.4 Write property test for profile get-or-create idempotency (Hypothesis)
    - **Property 2: Profile get-or-create idempotency** — create profile, modify fields, call get-or-create again, verify modifications preserved
    - **Validates: Requirements 1.3**

  - [ ]* 3.5 Write property test for verification token generation (Hypothesis)
    - **Property 11: Verification token generation** — generate multiple tokens, verify uniqueness and `expires_at == created_at + 24h`
    - **Validates: Requirements 4.1, 4.2**

- [ ] 4. Create profile router with all 4 endpoints
  - [ ] 4.1 Implement profile router (`backend/app/routers/profile.py`)
    - `GET /api/v1/profile/{email}` — get-or-create profile, return profile + tier info via `ProfileResponse` (includes `password_hash_set`, `country`, `google_oauth_id`)
    - `PUT /api/v1/profile/{email}` — validate input (display_name, github_url, linkedin_url, country), update profile, evaluate completeness, trigger tier upgrade if newly complete (Firestore transaction for atomicity)
    - `POST /api/v1/profile/{email}/verify-email` — generate token, send SES email
    - `GET /api/v1/profile/verify/{token}` — validate token, mark email verified, upgrade to Tier 2 if applicable (Firestore transaction)
    - Return 404 for non-existent profiles on PUT, return appropriate error codes (410 expired, 404 invalid token)
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 4.3, 4.4, 4.5, 4.6, 6.3, 6.4, 6.5, 12.6, 12.7_

  - [ ] 4.2 Register profile router in FastAPI app (`backend/app/main.py`)
    - Import and include profile router in the `api_router` with `PUT` added to `allow_methods` in CORS middleware
    - _Requirements: 9.1_

  - [ ]* 4.3 Write property test for profile round-trip persistence (Hypothesis)
    - **Property 6: Profile field persistence round-trip** — generate valid updates (including valid country codes), store via PUT, read via GET, verify field equality
    - **Validates: Requirements 3.2, 5.3, 12.3, 12.6, 12.7**

  - [ ]* 4.4 Write property test for tier upgrade on profile completion (Hypothesis)
    - **Property 9: Tier upgrade on profile completion** — generate profiles transitioning to complete, verify `profile_completed_at` set and `token_balance = max(current, 100)`
    - **Validates: Requirements 6.3, 6.4, 6.5**

  - [ ]* 4.5 Write property test for email verification tier 2 upgrade (Hypothesis)
    - **Property 10: Email verification triggers tier 2 upgrade** — generate valid tokens, verify `email_verified = true` and `token_balance = max(current, 50)` when `profile_completed_at` is null
    - **Validates: Requirements 4.3, 4.4, 6.2**

- [ ] 5. Checkpoint — Ensure all backend tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 6. Create auth models, auth service, and auth router
  - [ ] 6.1 Create auth Pydantic V2 models (`backend/app/models/auth.py`)
    - Define `SetPasswordRequest` with password validator (8-128 chars)
    - Define `ChangePasswordRequest` with current_password and new_password (8-128 chars validator)
    - Define `LoginRequest` with email and password
    - Define `GoogleTokenRequest` with id_token and optional email
    - Define `CheckEmailResponse` with `has_password` bool
    - Define `LoginResponse` with email, tier, daily_limit, token_balance
    - _Requirements: 9.7, 9.8, 9.9, 9.10, 9.11, 9.12, 11.2, 11.4_

  - [ ] 6.2 Create auth service (`backend/app/services/auth_service.py`)
    - Implement `hash_password(password: str) -> str` using `bcrypt.hashpw(password.encode(), bcrypt.gensalt())`
    - Implement `verify_password(password: str, stored_hash: str) -> bool` using `bcrypt.checkpw`
    - Implement `validate_google_token(id_token: str) -> dict` via `requests.get(f"https://oauth2.googleapis.com/tokeninfo?id_token={token}")` returning claims (`sub`, `email`)
    - Implement `check_google_oauth_id_unique(google_oauth_id: str, exclude_email: str) -> bool` querying profiles collection
    - _Requirements: 11.3, 11.7, 13.3, 13.5_

  - [ ] 6.3 Create auth router (`backend/app/routers/auth.py`)
    - `POST /api/v1/auth/set-password` — validate password length, hash with bcrypt, store `password_hash` in profile
    - `POST /api/v1/auth/login` — verify password against stored hash, return session data (email, tier, daily_limit, token_balance); return 401 on mismatch, 400 if no password set
    - `GET /api/v1/auth/check-email/{email}` — return `{has_password: true/false}` based on profile's `password_hash` field
    - `POST /api/v1/auth/google/link` — validate Google ID token, check uniqueness of `google_oauth_id`, store in profile; return 409 if already linked to another profile
    - `POST /api/v1/auth/google/login` — validate Google ID token, query profile by `google_oauth_id`, return session data; return 404 if no linked account
    - `DELETE /api/v1/auth/google/link/{email}` — set `google_oauth_id` to null in profile
    - _Requirements: 9.7, 9.8, 9.9, 9.10, 9.11, 9.12, 11.3, 11.5, 11.6, 11.7, 11.8, 11.9, 11.10, 11.11, 13.3, 13.4, 13.5, 13.7, 13.8, 13.9, 13.10_

  - [ ] 6.4 Register auth router in FastAPI app (`backend/app/main.py`)
    - Import and include auth router in the `api_router` with `DELETE` added to `allow_methods` in CORS middleware
    - _Requirements: 9.7_

  - [ ]* 6.5 Write property test for password length validation (Hypothesis)
    - **Property 15: Password length validation** — generate random strings, verify accept/reject at 8-128 char boundary
    - **Validates: Requirements 11.2, 11.4**

  - [ ]* 6.6 Write property test for bcrypt hash round-trip (Hypothesis)
    - **Property 16: Bcrypt password hash round-trip** — generate valid passwords (8-128 chars), hash with bcrypt, verify original password matches hash, verify different password does not match
    - **Validates: Requirements 11.3, 11.7, 11.8**

  - [ ]* 6.7 Write property test for Google OAuth ID uniqueness (Hypothesis)
    - **Property 18: Google OAuth ID uniqueness constraint** — generate two distinct emails and one google_oauth_id, link to first email, verify second link attempt returns 409 conflict
    - **Validates: Requirements 13.5**

- [ ] 7. Checkpoint — Ensure all backend tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 8. Update existing backend token logic for tier awareness
  - [ ] 8.1 Update token reset logic for tier-aware resets
    - Modify the token reset flow (in `resetTokens` / negotiation router) to check `profiles` collection for tier determination
    - Reset to 100 if `profile_completed_at` non-null, 50 if `email_verified` true, 20 otherwise
    - _Requirements: 10.1, 10.2, 10.3, 10.4_

  - [ ] 8.2 Update waitlist signup to set initial balance to 20
    - Modify `joinWaitlist` / waitlist creation to set `token_balance` to 20 instead of 100
    - _Requirements: 6.1_

  - [ ]* 8.3 Write property test for tier-aware token reset (Hypothesis)
    - **Property 12: Tier-aware token reset** — generate users at each tier, verify correct reset balance (20/50/100)
    - **Validates: Requirements 10.2, 10.3, 10.4**

  - [ ]* 8.4 Write property test for waitlist signup initial balance (Hypothesis)
    - **Property 14: Waitlist signup initial balance** — generate random emails, verify initial `token_balance` is 20
    - **Validates: Requirements 6.1**

- [ ] 9. Checkpoint — Ensure all backend tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 10. Update frontend SessionContext and token utilities
  - [ ] 10.1 Add tier fields to SessionContext (`frontend/context/SessionContext.tsx`)
    - Add `tier`, `dailyLimit` to `SessionState` interface
    - Add `updateTier(tier: number, dailyLimit: number, tokenBalance: number)` method
    - Update `login` to accept and store `tier` and `dailyLimit`
    - Persist `tier` and `dailyLimit` to sessionStorage
    - _Requirements: 8.4, 8.5_

  - [ ] 10.2 Update token utility functions (`frontend/lib/tokens.ts`)
    - Modify `resetTokens` to accept `dailyLimit` parameter instead of hardcoded 100
    - Modify `formatTokenDisplay` to accept `dailyLimit` parameter: `Tokens: {balance} / {dailyLimit}`
    - _Requirements: 8.1, 8.2, 8.3_

  - [ ] 10.3 Update TokenDisplay component (`frontend/components/TokenDisplay.tsx`)
    - Read `dailyLimit` from SessionContext
    - Pass `dailyLimit` to `formatTokenDisplay`
    - _Requirements: 8.1, 8.2, 8.3_

  - [ ]* 10.4 Write property test for token display format (fast-check)
    - **Property 13: Token display format** — generate random balance/limit pairs, verify output is `"Tokens: {clamped_balance} / {dailyLimit}"`
    - **Validates: Requirements 8.1, 8.2, 8.3**

- [ ] 11. Update WaitlistForm / Login Form and protected layout
  - [ ] 11.1 Update WaitlistForm / Login Form (`frontend/components/WaitlistForm.tsx`)
    - Set initial token balance to 20 (Tier 1) instead of 100 on signup and reset
    - Pass tier info (tier=1, dailyLimit=20) to `login` in SessionContext
    - On email blur/submit: call `GET /api/v1/auth/check-email/{email}` to determine if password field is needed
    - Conditionally show password input field when `has_password` is true
    - On email+password submit: call `POST /api/v1/auth/login` and handle 401 errors inline
    - When `has_password` is false, proceed with existing email-only login flow
    - Add "Sign in with Google" button alongside email input
    - Google sign-in triggers Google Identity Services consent flow, then calls `POST /api/v1/auth/google/login`
    - Handle Google login 404 (no linked account) with inline error message
    - Handle Google consent flow cancellation gracefully (no error shown)
    - _Requirements: 6.1, 11.5, 11.6, 11.7, 11.8, 11.9, 13.8, 13.9, 13.10, 13.11_

  - [ ] 11.2 Update protected layout header (`frontend/app/(protected)/layout.tsx`)
    - Make the email `<span>` a clickable `<Link>` to `/profile`
    - _Requirements: 2.1_

- [ ] 12. Create profile page with all sections
  - [ ] 12.1 Create profile page component (`frontend/app/(protected)/profile/page.tsx`)
    - Form with editable fields: display name, GitHub URL, LinkedIn URL
    - Country dropdown field with all ISO 3166-1 alpha-2 codes and corresponding country names
    - Display currently selected country name on profile view
    - Email verification status display with "Verify Email" button (hidden when already verified, show "Verified" badge)
    - Password section: "Set Password" button (visible when email verified and no password set), "Change Password" form (visible when password already set) — calls `POST /api/v1/auth/set-password` or change password endpoint
    - Google OAuth section: "Link Google Account" button (visible when email verified and no Google linked), linked Google account info + "Unlink Google Account" button (visible when Google linked) — calls `POST /api/v1/auth/google/link` and `DELETE /api/v1/auth/google/link/{email}`
    - Progress indicator showing completion steps (email verified, display name set, professional link added)
    - Save button triggers `PUT /api/v1/profile/{email}` via API client
    - On successful save with tier upgrade, call `updateTier` on SessionContext to reflect immediately
    - Redirect to landing page if not authenticated
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 4.7, 11.1, 11.10, 12.1, 12.5, 13.1, 13.2, 13.6, 13.7_

  - [ ] 12.2 Create profile API client functions (`frontend/lib/profile.ts`)
    - `getProfile(email)` — calls `GET /api/v1/profile/{email}`
    - `updateProfile(email, data)` — calls `PUT /api/v1/profile/{email}` (includes country field)
    - `requestEmailVerification(email)` — calls `POST /api/v1/profile/{email}/verify-email`
    - _Requirements: 9.1, 9.2, 9.3_

  - [ ] 12.3 Create auth API client functions (`frontend/lib/auth.ts`)
    - `checkEmail(email)` — calls `GET /api/v1/auth/check-email/{email}`
    - `loginWithPassword(email, password)` — calls `POST /api/v1/auth/login`
    - `setPassword(email, password)` — calls `POST /api/v1/auth/set-password`
    - `changePassword(email, currentPassword, newPassword)` — calls change password endpoint
    - `linkGoogle(idToken, email)` — calls `POST /api/v1/auth/google/link`
    - `loginWithGoogle(idToken)` — calls `POST /api/v1/auth/google/login`
    - `unlinkGoogle(email)` — calls `DELETE /api/v1/auth/google/link/{email}`
    - _Requirements: 9.7, 9.8, 9.9, 9.10, 9.11, 9.12_

  - [ ] 12.4 Create email verification callback page (`frontend/app/(protected)/profile/verify/page.tsx`)
    - Read token from URL query params
    - Call `GET /api/v1/profile/verify/{token}` on mount
    - Display success, expired (with resend option), or invalid token states
    - _Requirements: 4.3, 4.5, 4.6_

- [ ] 13. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 14. Integration wiring and final validation
  - [ ] 14.1 Wire negotiation router to use tier-aware token lookup
    - Update `start_negotiation` in `backend/app/routers/negotiation.py` to fetch tier from profile when displaying `tokens_remaining`
    - Update token deduction in `event_stream` finally block to use tier-aware daily limit
    - _Requirements: 6.7, 10.1_

  - [ ]* 14.2 Write backend integration tests for profile endpoints
    - Test GET profile (creates new with all default fields including password_hash, country, google_oauth_id + returns existing)
    - Test PUT profile (valid update with country, validation errors for invalid country code, tier upgrade trigger)
    - Test POST verify-email (mock SES)
    - Test GET verify token (valid, expired, invalid)
    - Test 404 for non-existent profile on targeted endpoints
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 12.6, 12.7_

  - [ ]* 14.3 Write backend integration tests for auth endpoints
    - Test POST set-password (valid password, invalid length)
    - Test POST login (correct password, wrong password 401, no password set 400)
    - Test GET check-email (has_password true/false)
    - Test password change (correct current password, incorrect current password 401)
    - Test POST google/link (valid token, 409 conflict when already linked)
    - Test POST google/login (valid linked account, 404 no linked account)
    - Test DELETE google/link (unlink success)
    - Mock Google token endpoint and bcrypt where appropriate
    - _Requirements: 9.7, 9.8, 9.9, 9.10, 9.11, 9.12, 11.3, 11.7, 11.8, 11.10, 11.11, 13.3, 13.4, 13.5, 13.7, 13.8, 13.9, 13.10_

  - [ ]* 14.4 Write frontend component tests for profile page
    - Test profile page renders all fields including country dropdown and Google OAuth section
    - Test country dropdown renders with ISO 3166-1 alpha-2 codes and country names
    - Test country name displayed on profile view
    - Test password section: "Set Password" visible when email verified and no password, "Change Password" visible when password set
    - Test Google OAuth section: "Link Google Account" visible when email verified and no Google linked, linked info + "Unlink" visible when linked
    - Test save triggers API call and updates session context on tier upgrade
    - Test email verification button visibility based on verification status
    - Test unauthenticated redirect
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 4.7, 8.4, 11.1, 12.1, 12.5, 13.1, 13.6_

  - [ ]* 14.5 Write frontend component tests for login form
    - Test login form conditionally shows password field based on check-email response
    - Test login form displays "Sign in with Google" button
    - Test password login flow (correct/incorrect password handling)
    - Test Google sign-in flow (success/error handling)
    - _Requirements: 11.5, 11.6, 11.8, 11.9, 13.8, 13.10, 13.11_

- [ ] 15. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Backend property tests use Hypothesis with `@settings(max_examples=100)`
- Frontend property tests use fast-check with `fc.assert(property, { numRuns: 100 })`
- Firestore transactions are required for tier upgrade operations (profile + waitlist atomicity)
- `profile_completed_at` is write-once (permanent Tier 3) — never cleared after being set
- Each property test maps to exactly one correctness property from the design document
- Auth service uses bcrypt for password hashing — no separate salt column needed (bcrypt embeds salt in hash)
- Google OAuth uses Google Identity Services (GIS) on frontend, backend validates ID tokens against Google's tokeninfo endpoint
- Country codes use ISO 3166-1 alpha-2 standard, validated via `pycountry` library
- Google OAuth ID uniqueness enforced via Firestore transaction to prevent race conditions
