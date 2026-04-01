# Implementation Plan: A2A Frontend Gate & Waitlist

## Overview

Incrementally build the Next.js 14 frontend: scaffold → Firebase client → waitlist service → session context → landing page + form → access gate → token system → Firestore security rules. Each step builds on the previous, with property tests validating correctness at each layer.

## Tasks

- [x] 1. Scaffold Next.js 14 App Router project with Tailwind CSS and Lucide React
  - [x] 1.1 Initialize Next.js 14+ project in `frontend/` with TypeScript, App Router (`app/` directory), and Tailwind CSS
    - Run `npx create-next-app@14` with TypeScript and Tailwind flags, or manually create `package.json`, `tsconfig.json`, `tailwind.config.ts`, `postcss.config.mjs`
    - Install `lucide-react` as a dependency
    - _Requirements: 1.1, 1.2, 1.3_
  - [x] 1.2 Create root layout (`app/layout.tsx`) and global CSS (`app/globals.css`)
    - Root layout sets `<html lang="en">`, applies global styles, renders `{children}`
    - `globals.css` imports `@tailwind base; @tailwind components; @tailwind utilities;`
    - _Requirements: 1.4, 1.5_
  - [x] 1.3 Create placeholder landing page (`app/page.tsx`)
    - Minimal page component returning a heading — confirms the scaffold works
    - _Requirements: 2.1_

- [x] 2. Implement Firebase client and waitlist service
  - [x] 2.1 Create Firebase singleton module (`lib/firebase.ts`)
    - Initialize Firebase app with `NEXT_PUBLIC_FIREBASE_API_KEY`, `NEXT_PUBLIC_FIREBASE_PROJECT_ID`, `NEXT_PUBLIC_FIREBASE_APP_ID` from env vars
    - Validate all required env vars at init time — throw descriptive error if any missing
    - Export singleton `Firestore` instance using modular `firebase/firestore` imports
    - Use `getApps().length === 0` guard for singleton pattern
    - _Requirements: 8.1, 8.2, 8.3, 8.4_
  - [x] 2.2 Write property test for Firebase env var validation
    - **Property 13: Missing Firebase env var throws descriptive error**
    - For each required env var, remove it and verify the thrown error message includes the variable name
    - **Validates: Requirements 8.4**
  - [x] 2.3 Create token helper functions (`lib/tokens.ts`)
    - `getUtcDateString(): string` — returns `YYYY-MM-DD` in UTC
    - `needsReset(lastResetDate: string): boolean` — true if `lastResetDate < today` (UTC)
    - `resetTokens(email: string): Promise<void>` — updates Firestore doc with `token_balance: 100` and `last_reset_date: today`
    - `formatTokenDisplay(balance: number): string` — returns `"Tokens: X / 100"` clamping X to `max(0, balance)`
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 7.1, 7.4_
  - [x] 2.4 Write property test for UTC date consistency
    - **Property 9: UTC date consistency**
    - Generate random `Date` objects across timezone offsets, verify `getUtcDateString` always returns UTC `YYYY-MM-DD`
    - **Validates: Requirements 6.4**
  - [x] 2.5 Write property test for token balance display formatting
    - **Property 10: Token balance display formatting**
    - Generate random integers (including negatives), verify `formatTokenDisplay` returns `"Tokens: X / 100"` where `X = max(0, balance)`
    - **Validates: Requirements 7.1, 7.4**
  - [x] 2.6 Create waitlist service (`lib/waitlist.ts`)
    - Define `WaitlistDocument` interface: `email`, `signed_up_at`, `token_balance`, `last_reset_date`
    - Implement `joinWaitlist(email: string): Promise<WaitlistDocument>`:
      - Normalize email to lowercase
      - `getDoc(waitlist/{email})` — if exists, return existing doc (do not overwrite)
      - If not exists, `setDoc` with `email`, `signed_up_at: serverTimestamp()`, `token_balance: 100`, `last_reset_date: getUtcDateString()`
    - _Requirements: 3.4, 3.5, 5.1, 5.2, 5.3_
  - [x] 2.7 Write property test for new waitlist document structure
    - **Property 2: New waitlist document structure**
    - Generate random valid emails, call `joinWaitlist`, verify document has `email` (lowercase), `token_balance === 100`, `last_reset_date === today UTC`
    - **Validates: Requirements 3.4, 5.1, 5.2**
  - [x] 2.8 Write property test for idempotent re-submission
    - **Property 3: Idempotent re-submission**
    - Generate existing documents with random `token_balance`/`last_reset_date`, re-submit same email, verify original fields preserved
    - **Validates: Requirements 3.5**

- [x] 3. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Implement Session Context and Access Gate
  - [x] 4.1 Create Session Context (`context/SessionContext.tsx`)
    - Define `SessionState` interface: `email`, `tokenBalance`, `lastResetDate`, `isAuthenticated`
    - Define `SessionContextValue` extending `SessionState` with `login`, `logout`, `updateTokenBalance` methods
    - `SessionProvider` persists `email`, `tokenBalance`, `lastResetDate` to `sessionStorage`
    - On mount, restore state from `sessionStorage`
    - `login()` sets a `junto_session=1` cookie (SameSite=Strict, path=/) for middleware
    - `logout()` clears `sessionStorage` and removes the cookie
    - _Requirements: 4.4, 4.5, 5.4_
  - [x] 4.2 Write property test for session state loaded on auth
    - **Property 4: Session state loaded on auth**
    - Generate random valid emails with random Firestore state, after auth verify session matches Firestore values
    - **Validates: Requirements 3.6, 5.4**
  - [x] 4.3 Create Next.js middleware (`middleware.ts`)
    - Check for `junto_session` cookie on protected route patterns (e.g., `/arena/:path*`)
    - If cookie absent, redirect to `/` via `NextResponse.redirect`
    - Export `config.matcher` for protected routes only
    - _Requirements: 4.1, 4.2_
  - [x] 4.4 Write property test for access gate blocks unauthenticated users
    - **Property 6: Access gate blocks unauthenticated users**
    - Generate random protected route paths, with no session cookie, verify redirect to `/`
    - **Validates: Requirements 4.1, 4.2**
  - [x] 4.5 Write property test for access gate allows authenticated users
    - **Property 7: Access gate allows authenticated users**
    - Generate random protected route paths with valid session cookie, verify access allowed
    - **Validates: Requirements 4.3**
  - [x] 4.6 Create protected layout (`app/(protected)/layout.tsx`)
    - Client component that reads `SessionContext`
    - If `!isAuthenticated`, redirect to `/` via `router.replace`
    - Render `TokenDisplay` + `{children}` when authenticated
    - _Requirements: 4.1, 4.3_
  - [x] 4.7 Create placeholder arena page (`app/(protected)/arena/page.tsx`)
    - Minimal protected page to verify the gate works end-to-end
    - _Requirements: 4.1_

- [x] 5. Implement Landing Page and Waitlist Form
  - [x] 5.1 Create WaitlistForm component (`components/WaitlistForm.tsx`)
    - Single email input field + submit button
    - Client-side email validation with regex on submit — inline error for invalid/empty input
    - Loading state: disable button + show spinner while Firestore write in progress
    - On valid submit: call `joinWaitlist(email)`, handle token reset if `needsReset`, call `login()` from SessionContext, navigate to `/arena` via `router.push`
    - On Firestore error: display user-facing error message, do not set session state
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8_
  - [x] 5.2 Write property test for invalid email rejection
    - **Property 1: Invalid email rejection**
    - Generate random invalid email strings (empty, whitespace, missing `@`, missing domain), verify all rejected with inline error, no Firestore write
    - **Validates: Requirements 3.2, 3.3**
  - [x] 5.3 Write property test for error display on Firestore failure
    - **Property 5: Error display on Firestore failure**
    - Generate random Firestore error types (network, permission-denied, unavailable), verify error message displayed, no navigation
    - **Validates: Requirements 3.7**
  - [x] 5.4 Write property test for token daily reset logic
    - **Property 8: Token daily reset logic**
    - Generate random past dates and today's date, verify reset happens iff `last_reset_date < today UTC`, and persists to Firestore
    - **Validates: Requirements 6.1, 6.2, 6.3**
  - [x] 5.5 Build Landing Page (`app/page.tsx`)
    - Headline communicating JuntoAI A2A value proposition
    - Subheadline/body paragraph elaborating on the A2A protocol sandbox concept
    - Render `WaitlistForm` prominently below value proposition
    - Responsive layout: 320px to 1920px using Tailwind utility classes
    - Use brand colors from styling guide (Primary Blue CTA, Dark Charcoal text, Off-White background)
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_

- [x] 6. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Implement Token Display and Backend Sync
  - [x] 7.1 Create TokenDisplay component (`components/TokenDisplay.tsx`)
    - Read `tokenBalance` from `SessionContext`
    - Render `"Tokens: {max(0, balance)} / 100"` with Lucide `Coins` icon
    - Display on all protected routes (rendered by protected layout)
    - _Requirements: 7.1, 7.4_
  - [x] 7.2 Implement token balance sync from backend response
    - When backend `POST /api/v1/negotiation/start` returns `tokens_remaining`, call `updateTokenBalance()` on SessionContext
    - If client-side balance < expected cost, disable action button and show "No tokens remaining. Resets at midnight UTC."
    - Client-side balance never displays below 0
    - Note: the actual negotiation API call is in a future spec — wire the `updateTokenBalance` hook so it's ready
    - _Requirements: 7.2, 7.3, 7.4, 7.5_
  - [x] 7.3 Write property test for token balance sync from backend
    - **Property 11: Token balance sync from backend**
    - Generate random `tokens_remaining` values (0–100), verify client state matches exactly
    - **Validates: Requirements 7.2**
  - [x] 7.4 Write property test for insufficient tokens disables action
    - **Property 12: Insufficient tokens disables action**
    - Generate random balance/cost pairs where balance < cost, verify action button disabled and message displayed
    - **Validates: Requirements 7.3**

- [x] 8. Create Firestore Security Rules
  - [x] 8.1 Write `firestore.rules` file at `frontend/firestore.rules`
    - Allow create on `waitlist/{emailId}` only if doc ID matches `email` field AND `token_balance === 100`
    - Allow read on `waitlist/{emailId}` (scoped to specific doc ID — no list queries)
    - Allow update on `waitlist/{emailId}` only if `token_balance` between 0–100 and `email` matches doc ID
    - Deny all deletes on `waitlist`
    - Deny all client read/write on `negotiation_sessions`
    - Default deny for all other collections
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7_
  - [x] 8.2 Write property test for waitlist document write validation (Security Rules)
    - **Property 14: Waitlist document write validation**
    - Generate random create/update payloads with invalid fields (mismatched email, token_balance != 100 on create, balance > 100 or < 0 on update), verify rules deny
    - **Validates: Requirements 9.2, 9.4**
  - [x] 8.3 Write property test for waitlist document read scoping (Security Rules)
    - **Property 15: Waitlist document read scoping**
    - Generate random email pairs (requester vs doc owner), verify read only succeeds for the specific doc ID requested
    - **Validates: Requirements 9.3**
  - [x] 8.4 Write property test for default deny (Security Rules)
    - **Property 16: Default deny for unauthorized operations**
    - Generate random collection names and operations, verify all denied except explicitly allowed paths
    - **Validates: Requirements 9.5, 9.6, 9.7**

- [x] 9. Set up Vitest testing infrastructure
  - [x] 9.1 Configure Vitest with React Testing Library and fast-check
    - Install `vitest`, `@testing-library/react`, `@testing-library/jest-dom`, `jsdom`, `fast-check`, `@vitest/coverage-v8`
    - Create `vitest.config.ts` with jsdom environment, coverage thresholds at 70%
    - Create `__tests__/setup.ts` with testing-library matchers and Firebase SDK mocks
    - _Requirements: Testing guidelines (Vitest + RTL, 70% coverage)_
  - [x] 9.2 Install `@firebase/rules-unit-testing` for security rules tests
    - Configure rules test setup to load `firestore.rules` and connect to Firestore emulator
    - _Requirements: 9.1 (rules must be testable)_

- [x] 10. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- Firestore security rules tests require the Firebase emulator (`firebase emulators:exec`)
- The backend API integration (negotiation start, SSE streaming) is wired as hooks only — full implementation is in the `a2a-backend-core-sse` spec
