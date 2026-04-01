# Requirements Document

## Introduction

This specification covers the Next.js 14 frontend foundation, the high-conversion landing page, the email waitlist capture form, and the token-based access gate for the JuntoAI A2A MVP. Users arriving at the application encounter a landing page with a compelling value proposition. To access the A2A Sandbox, users must submit their email address through a waitlist form that persists the entry to GCP Firestore. Once authenticated, each email receives 100 tokens per day for running simulations, with the quota resetting daily at midnight UTC. The backend API scaffold (FastAPI, Firestore client, SSE streaming) is covered in the `a2a-backend-core-sse` spec. The GCP infrastructure (Cloud Run, Firestore provisioning) is covered in the `a2a-gcp-infrastructure` spec. The scenario listing API endpoints are covered in the `a2a-scenario-config-engine` spec.

## Glossary

- **Frontend**: The Next.js 14+ application using the App Router, React, Tailwind CSS, and Lucide React icons.
- **Landing_Page**: The root route (`/`) of the Frontend that displays the value proposition and the Waitlist_Form.
- **Waitlist_Form**: The email capture form component on the Landing_Page that collects a user email address and submits it to Firestore.
- **Waitlist_Document**: A Firestore document in the `waitlist` collection, keyed by the normalized email address, containing the email, signup timestamp, and token state.
- **Access_Gate**: The mechanism that prevents navigation to protected routes until the user has submitted a valid email through the Waitlist_Form.
- **Token_System**: The subsystem that tracks and enforces a daily token budget per authenticated email address.
- **Token_Balance**: The number of remaining tokens available to an authenticated user for the current day, stored in the Waitlist_Document.
- **Token_Reset**: The process that resets a user's Token_Balance to 100 when the current UTC date exceeds the `last_reset_date` stored in the Waitlist_Document.
- **Firestore**: GCP Firestore (NoSQL) used as the persistence layer for waitlist entries and token state.
- **Protected_Route**: Any Frontend route beyond the Landing_Page (e.g., the Arena Selector) that requires a valid authenticated email and a positive Token_Balance.
- **Email_Validation**: Client-side and logical validation ensuring the submitted email conforms to a standard email format.

## Requirements

### Requirement 1: Next.js 14 Application Scaffold

**User Story:** As a developer, I want a properly scaffolded Next.js 14 application with Tailwind CSS and Lucide React configured, so that the frontend has a solid foundation for all UI screens.

#### Acceptance Criteria

1. THE Frontend SHALL be a Next.js 14+ application using the App Router (`app/` directory structure).
2. THE Frontend SHALL include Tailwind CSS configured as the utility-first CSS framework with a `tailwind.config.ts` file.
3. THE Frontend SHALL include the `lucide-react` package as the icon library available to all components.
4. THE Frontend SHALL define a root layout (`app/layout.tsx`) that applies global styles, sets the HTML language attribute to `"en"`, and renders child routes.
5. THE Frontend SHALL include a global CSS file that imports Tailwind CSS base, components, and utilities layers.

### Requirement 2: Landing Page Value Proposition

**User Story:** As a visitor, I want to see a compelling value proposition when I arrive at the site, so that I understand the power of JuntoAI A2A and am motivated to join the waitlist.

#### Acceptance Criteria

1. THE Landing_Page SHALL be served at the root route (`/`).
2. THE Landing_Page SHALL display a headline communicating the JuntoAI A2A value proposition.
3. THE Landing_Page SHALL display a subheadline or body paragraph elaborating on the A2A protocol sandbox concept.
4. THE Landing_Page SHALL render the Waitlist_Form prominently below the value proposition content.
5. THE Landing_Page SHALL be responsive, rendering correctly on viewport widths from 320px to 1920px.
6. THE Landing_Page SHALL use Tailwind CSS utility classes for all styling.

### Requirement 3: Email Waitlist Capture Form

**User Story:** As a visitor, I want to submit my email address through a waitlist form, so that I can gain access to the A2A Sandbox and be added to the JuntoAI mailing list.

#### Acceptance Criteria

1. THE Waitlist_Form SHALL contain a single email input field and a submit button.
2. WHEN the user submits the Waitlist_Form, THE Waitlist_Form SHALL perform Email_Validation on the input value before submission.
3. IF the email input is empty or does not conform to a standard email format, THEN THE Waitlist_Form SHALL display an inline error message and prevent submission.
4. WHEN a valid email is submitted, THE Waitlist_Form SHALL write a Waitlist_Document to the Firestore `waitlist` collection with the following fields: `email` (normalized to lowercase), `signed_up_at` (server timestamp), `token_balance` set to `100`, and `last_reset_date` set to the current UTC date string (`YYYY-MM-DD`).
5. IF a Waitlist_Document with the same email already exists in Firestore, THEN THE Waitlist_Form SHALL treat the submission as a successful login and proceed to grant access without overwriting the existing document.
6. WHEN the Firestore write or read completes successfully, THE Waitlist_Form SHALL store the authenticated email in the client-side session state and navigate the user past the Access_Gate.
7. IF the Firestore write fails due to a network or service error, THEN THE Waitlist_Form SHALL display a user-facing error message indicating the submission could not be completed.
8. WHILE the Firestore write is in progress, THE Waitlist_Form SHALL disable the submit button and display a loading indicator.

### Requirement 4: Access Gate Enforcement

**User Story:** As a product owner, I want the application to gate all sandbox functionality behind the email waitlist, so that every tester becomes a captured lead before accessing the A2A simulations.

#### Acceptance Criteria

1. THE Access_Gate SHALL prevent navigation to any Protected_Route when no authenticated email exists in the client-side session state.
2. WHEN an unauthenticated user attempts to access a Protected_Route directly via URL, THE Access_Gate SHALL redirect the user to the Landing_Page.
3. WHEN a user has successfully submitted the Waitlist_Form, THE Access_Gate SHALL allow navigation to Protected_Routes for the duration of the browser session.
4. THE Access_Gate SHALL store the authenticated email and token state using React context or a client-side state management approach accessible to all components.
5. WHEN the browser session ends (tab or window closed), THE Access_Gate SHALL clear the client-side session state, requiring re-authentication on the next visit.

### Requirement 5: Token System — Balance Initialization and Storage

**User Story:** As a product owner, I want each waitlisted email to receive exactly 100 tokens per day, so that API costs are controlled while allowing users to fully test the platform.

#### Acceptance Criteria

1. WHEN a new Waitlist_Document is created, THE Token_System SHALL set the `token_balance` field to `100`.
2. WHEN a new Waitlist_Document is created, THE Token_System SHALL set the `last_reset_date` field to the current UTC date string in `YYYY-MM-DD` format.
3. THE Token_System SHALL store the `token_balance` and `last_reset_date` fields within the Waitlist_Document in the Firestore `waitlist` collection.
4. WHEN the user authenticates (new signup or returning user), THE Token_System SHALL read the `token_balance` and `last_reset_date` from the Waitlist_Document and load them into the client-side session state.

### Requirement 6: Token System — Daily Reset at Midnight UTC

**User Story:** As a user, I want my token balance to reset to 100 every day at midnight UTC, so that I can continue testing the platform on subsequent days.

#### Acceptance Criteria

1. WHEN a user authenticates and the `last_reset_date` in the Waitlist_Document is earlier than the current UTC date, THE Token_System SHALL update the `token_balance` to `100` and set `last_reset_date` to the current UTC date string.
2. WHEN a user authenticates and the `last_reset_date` matches the current UTC date, THE Token_System SHALL use the existing `token_balance` without modification.
3. WHEN a Token_Reset occurs, THE Token_System SHALL persist the updated `token_balance` and `last_reset_date` to the Waitlist_Document in Firestore.
4. THE Token_System SHALL determine the current date using UTC time exclusively, so that the reset boundary is consistent for all users regardless of local timezone.

### Requirement 7: Token System — Balance Display and Deduction

**User Story:** As a user, I want to see my remaining token balance and have tokens deducted when I run simulations, so that I understand my usage limits.

#### Acceptance Criteria

1. THE Frontend SHALL display the current Token_Balance in a visible location on all Protected_Routes, formatted as "Tokens: X / 100".
2. WHEN the backend `POST /api/v1/negotiation/start` response returns a `tokens_remaining` value, THE Token_System SHALL update the client-side Token_Balance to match the backend value. The backend is the single source of truth for all token deductions.
3. IF the client-side Token_Balance is less than the expected token cost for an action, THEN THE Token_System SHALL disable the action and display a message indicating insufficient tokens and the reset time. This is an optimistic UI check; the backend enforces the actual limit via HTTP 429.
4. THE Token_System SHALL ensure that the client-side Token_Balance never displays below `0`.
5. THE Token_System SHALL NOT perform direct client-side Firestore writes to deduct tokens. All token deductions SHALL be performed by the backend API using an atomic Firestore operation (increment by negative value) to prevent race conditions from concurrent sessions.

### Requirement 8: Firestore Client-Side Integration

**User Story:** As a developer, I want a configured Firebase/Firestore client in the Next.js frontend, so that the Waitlist_Form and Token_System can read and write to Firestore directly from the client.

#### Acceptance Criteria

1. THE Frontend SHALL initialize the Firebase JS SDK with project configuration values sourced from environment variables (`NEXT_PUBLIC_FIREBASE_API_KEY`, `NEXT_PUBLIC_FIREBASE_PROJECT_ID`, `NEXT_PUBLIC_FIREBASE_APP_ID`).
2. THE Frontend SHALL export a singleton Firestore instance from a shared module (e.g., `lib/firebase.ts`) for use across components.
3. THE Frontend SHALL use the `firebase/firestore` modular SDK (tree-shakeable imports) for all Firestore operations.
4. IF any required Firebase environment variable is missing at build time, THEN THE Frontend SHALL throw a descriptive error during initialization indicating which variable is absent.

### Requirement 9: Firestore Security Rules

**User Story:** As a security engineer, I want Firestore security rules that prevent unauthorized data access, so that users cannot manipulate token balances, read other users' data, or write arbitrary documents using the publicly exposed Firebase config.

#### Acceptance Criteria

1. THE project SHALL include a `firestore.rules` file at the repository root (or in `/infra`) defining Firestore Security Rules.
2. THE Firestore Security Rules SHALL allow a client to create a new document in the `waitlist` collection only if the document ID matches the `email` field in the document data and the `token_balance` field equals `100`.
3. THE Firestore Security Rules SHALL allow a client to read a document in the `waitlist` collection only if the document ID matches the email provided in the request (users can only read their own waitlist entry).
4. THE Firestore Security Rules SHALL deny all client-side writes that attempt to set `token_balance` to a value greater than `100` or less than `0`.
5. THE Firestore Security Rules SHALL deny all client-side delete operations on the `waitlist` collection.
6. THE Firestore Security Rules SHALL deny all client-side read and write access to the `negotiation_sessions` collection. Only the backend service account (server-side SDK) SHALL access negotiation session data.
7. THE Firestore Security Rules SHALL deny all access to any collection not explicitly listed in the rules (default deny).
8. THE Firestore Security Rules SHALL be deployed as part of the CI/CD pipeline or Terragrunt infrastructure provisioning.

