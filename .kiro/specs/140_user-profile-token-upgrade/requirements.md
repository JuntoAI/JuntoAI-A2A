# Requirements Document

## Introduction

Users who complete their profile — by adding a display name, verifying their email address via a confirmation link, and providing at least one professional link (GitHub or LinkedIn) — receive an upgraded daily token allowance of 150 tokens instead of the default 100. Profile data is stored in a dedicated `profiles` Firestore collection to support future user-centric features (custom scenarios, preferences, etc.). The profile page is accessed by clicking the user's email address displayed in the protected routes header. Once earned, the token bonus is permanent and cannot be revoked.

## Glossary

- **Profile_System**: The backend service responsible for creating, reading, updating, and validating user profile documents in the `profiles` Firestore collection.
- **Profile_Page**: The frontend page where authenticated users can view and edit their profile information (display name, email verification status, GitHub URL, LinkedIn URL).
- **Token_System**: The existing backend and frontend logic that manages daily token allowances, resets at midnight UTC, and deducts tokens after negotiations.
- **Email_Verifier**: The backend service responsible for generating, sending, and validating email verification tokens. Uses Amazon SES for email delivery.
- **Profile_Completeness**: A profile is considered complete when all three conditions are met: (1) display name is set, (2) email is verified, and (3) at least one professional link (GitHub or LinkedIn) is provided with a valid URL format.
- **Daily_Token_Limit**: The maximum number of tokens a user receives per day. Default is 100; upgraded is 150.
- **Waitlist_Document**: The existing Firestore document in the `waitlist` collection keyed by email, containing `email`, `signed_up_at`, `token_balance`, and `last_reset_date`.
- **Profile_Document**: A Firestore document in the `profiles` collection keyed by email, containing `display_name`, `email_verified`, `github_url`, `linkedin_url`, `profile_completed_at`, and `created_at`.
- **Verification_Token**: A unique, time-limited token sent to the user's email address to confirm ownership.

## Requirements

### Requirement 1: Profile Document Creation

**User Story:** As a user, I want a profile document to be created when I first access the profile page, so that I can start filling in my profile information.

#### Acceptance Criteria

1. WHEN an authenticated user navigates to the Profile_Page for the first time, THE Profile_System SHALL create a Profile_Document in the `profiles` collection keyed by the user's email address.
2. THE Profile_System SHALL initialize the Profile_Document with `display_name` set to empty string, `email_verified` set to false, `github_url` set to null, `linkedin_url` set to null, `profile_completed_at` set to null, and `created_at` set to the current server timestamp.
3. WHEN an authenticated user navigates to the Profile_Page and a Profile_Document already exists, THE Profile_System SHALL return the existing Profile_Document without overwriting.

### Requirement 2: Profile Page Access

**User Story:** As a user, I want to access my profile by clicking on my email address in the header, so that I can manage my profile information.

#### Acceptance Criteria

1. THE Profile_Page SHALL be accessible by clicking the email address displayed in the protected routes header navigation.
2. THE Profile_Page SHALL display editable fields for display name, GitHub profile URL, and LinkedIn profile URL.
3. THE Profile_Page SHALL display the current email verification status (verified or not verified).
4. THE Profile_Page SHALL display a progress indicator showing which profile completion steps are done and which remain.
5. WHEN the user is not authenticated, THE Profile_Page SHALL redirect the user to the landing page.

### Requirement 3: Display Name Management

**User Story:** As a user, I want to add and update my display name, so that I can personalize my profile.

#### Acceptance Criteria

1. WHEN the user submits a display name, THE Profile_System SHALL validate that the display name is between 2 and 100 characters in length.
2. WHEN the user submits a valid display name, THE Profile_System SHALL store the display name in the Profile_Document.
3. IF the user submits a display name shorter than 2 characters or longer than 100 characters, THEN THE Profile_System SHALL return a descriptive validation error message.
4. THE Profile_System SHALL trim leading and trailing whitespace from the display name before storing.

### Requirement 4: Email Verification

**User Story:** As a user, I want to verify my email address via a confirmation link, so that I can prove ownership of my email and progress toward the token upgrade.

#### Acceptance Criteria

1. WHEN the user requests email verification on the Profile_Page, THE Email_Verifier SHALL generate a unique Verification_Token and send a verification email to the user's registered email address using Amazon SES.
2. THE Email_Verifier SHALL set the Verification_Token to expire after 24 hours.
3. WHEN the user clicks the verification link containing a valid and non-expired Verification_Token, THE Email_Verifier SHALL set `email_verified` to true in the Profile_Document.
4. IF the user clicks a verification link containing an expired Verification_Token, THEN THE Email_Verifier SHALL display an error message and offer the option to resend a new verification email.
5. IF the user clicks a verification link containing an invalid Verification_Token, THEN THE Email_Verifier SHALL display an error message indicating the link is invalid.
6. WHEN the user's email is already verified, THE Profile_Page SHALL hide the verification request button and display a "Verified" status indicator.
7. THE Email_Verifier SHALL use Amazon SES as the email delivery service, configured with IAM credentials for the backend service account.

### Requirement 5: Professional Link Management

**User Story:** As a user, I want to add my GitHub or LinkedIn profile URL, so that I can complete my profile and earn the token upgrade.

#### Acceptance Criteria

1. WHEN the user submits a GitHub URL, THE Profile_System SHALL validate that the URL matches the format `https://github.com/{username}` where `{username}` contains only alphanumeric characters, hyphens, and is between 1 and 39 characters.
2. WHEN the user submits a LinkedIn URL, THE Profile_System SHALL validate that the URL matches the format `https://linkedin.com/in/{slug}` or `https://www.linkedin.com/in/{slug}` where `{slug}` contains only alphanumeric characters, hyphens, and is between 3 and 100 characters.
3. WHEN the user submits a valid professional link URL, THE Profile_System SHALL store the URL in the corresponding field of the Profile_Document.
4. IF the user submits a URL that does not match the expected format, THEN THE Profile_System SHALL return a descriptive validation error specifying the expected format.
5. THE Profile_System SHALL require at least one professional link (GitHub or LinkedIn) for Profile_Completeness, but both are optional individually.

### Requirement 6: Profile Completeness Evaluation and Token Upgrade

**User Story:** As a user, I want to receive 150 daily tokens immediately when I complete my profile, so that I am rewarded for providing my information.

#### Acceptance Criteria

1. WHEN the user saves a profile update that results in Profile_Completeness, THE Profile_System SHALL set `profile_completed_at` to the current server timestamp in the Profile_Document.
2. WHEN Profile_Completeness is achieved, THE Token_System SHALL immediately set the user's Daily_Token_Limit to 150.
3. WHEN Profile_Completeness is achieved and the user's current token balance is based on the default 100-token allowance, THE Token_System SHALL add 50 tokens to the user's current Waitlist_Document `token_balance`.
4. WHEN the Token_System resets tokens at midnight UTC for a user with a completed profile, THE Token_System SHALL reset the `token_balance` to 150 instead of 100.
5. THE Profile_System SHALL evaluate Profile_Completeness on every profile save operation by checking all three conditions: display name is set, email is verified, and at least one professional link is present.

### Requirement 7: Permanent Token Bonus

**User Story:** As a user, I want my token bonus to be permanent once earned, so that I do not lose my reward if I later modify my profile.

#### Acceptance Criteria

1. WHEN a user has a non-null `profile_completed_at` timestamp in the Profile_Document, THE Token_System SHALL use 150 as the Daily_Token_Limit regardless of the current state of the profile fields.
2. THE Token_System SHALL determine the Daily_Token_Limit by checking the `profile_completed_at` field, not by re-evaluating Profile_Completeness on each token reset.

### Requirement 8: Token Display Update

**User Story:** As a user, I want the token display to reflect my upgraded allowance, so that I can see my correct daily limit.

#### Acceptance Criteria

1. WHEN the user has a completed profile, THE Token_System SHALL display "Tokens: X / 150" instead of "Tokens: X / 100" in the TokenDisplay component.
2. WHEN the user completes their profile on the Profile_Page, THE Token_System SHALL update the token display immediately without requiring a page refresh.
3. THE Token_System SHALL fetch the user's Daily_Token_Limit from the Profile_Document `profile_completed_at` field to determine whether to show 100 or 150 as the maximum.

### Requirement 9: Profile API Endpoints

**User Story:** As a developer, I want RESTful API endpoints for profile management, so that the frontend can interact with the profile system.

#### Acceptance Criteria

1. THE Profile_System SHALL expose a `GET /api/v1/profile/{email}` endpoint that returns the Profile_Document for the given email.
2. THE Profile_System SHALL expose a `PUT /api/v1/profile/{email}` endpoint that updates the Profile_Document fields (display_name, github_url, linkedin_url).
3. THE Profile_System SHALL expose a `POST /api/v1/profile/{email}/verify-email` endpoint that triggers the email verification flow.
4. THE Profile_System SHALL expose a `GET /api/v1/profile/verify/{token}` endpoint that validates a Verification_Token and marks the email as verified.
5. IF a request targets a non-existent profile, THEN THE Profile_System SHALL return a 404 status code with a descriptive error message.
6. THE Profile_System SHALL validate all input fields using Pydantic V2 models before processing.

### Requirement 10: Token Reset Integration

**User Story:** As a developer, I want the token reset logic to account for profile completion status, so that upgraded users receive the correct daily allowance.

#### Acceptance Criteria

1. WHEN the Token_System resets a user's tokens, THE Token_System SHALL check the `profiles` collection for a Profile_Document with a non-null `profile_completed_at` field.
2. WHEN a Profile_Document with a non-null `profile_completed_at` exists, THE Token_System SHALL reset the `token_balance` to 150 in the Waitlist_Document.
3. WHEN no Profile_Document exists or `profile_completed_at` is null, THE Token_System SHALL reset the `token_balance` to 100 in the Waitlist_Document.
