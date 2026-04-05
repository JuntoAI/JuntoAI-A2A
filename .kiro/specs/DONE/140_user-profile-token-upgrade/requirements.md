# Requirements Document

## Introduction

Users progress through a 3-tier daily token system based on their engagement level. Tier 1 (Unverified) grants 20 tokens/day upon waitlist signup with any email. Tier 2 (Verified Email) grants 50 tokens/day once the user clicks an email verification link. Tier 3 (Full Profile) grants 100 tokens/day when the user has a verified email, a display name, and at least one professional link (GitHub or LinkedIn). Token cost per simulation remains dynamic: 1 user token per 1,000 AI tokens consumed, rounded up. Profile data is stored in a dedicated `profiles` Firestore collection to support future user-centric features (custom scenarios, preferences, etc.). The profile page is accessed by clicking the user's email address displayed in the protected routes header. Once a user reaches Tier 3, the 100-token allowance is permanent and cannot be revoked even if profile fields are later removed.

Additionally, the system supports password-based account protection: users can set a password during or after email verification to protect their account. When a returning user enters an email that already has a password set, the login form prompts for the password. Users who have not set a password continue to use the existing email-only login flow. Each user profile includes a country field to support an upcoming performance leaderboard that displays high scores by country. Users can also link their account to Google OAuth after account creation, enabling Google-based login as an alternative to email/password.

## Glossary

- **Profile_System**: The backend service responsible for creating, reading, updating, and validating user profile documents in the `profiles` Firestore collection.
- **Profile_Page**: The frontend page where authenticated users can view and edit their profile information (display name, email verification status, GitHub URL, LinkedIn URL, country).
- **Token_System**: The existing backend and frontend logic that manages daily token allowances, resets at midnight UTC, and deducts tokens after negotiations.
- **Email_Verifier**: The backend service responsible for generating, sending, and validating email verification tokens. Uses Amazon SES for email delivery.
- **Token_Tier**: The user's current token allocation level. Tier 1 (Unverified) = 20 tokens/day, Tier 2 (Verified Email) = 50 tokens/day, Tier 3 (Full Profile) = 100 tokens/day.
- **Tier_1_Unverified**: The default tier assigned at waitlist signup. Grants 20 tokens/day (~2-3 simulations). Triggered by entering any email on the waitlist form.
- **Tier_2_Verified**: The mid-level tier. Grants 50 tokens/day (~5-8 simulations). Triggered by clicking the email verification link.
- **Tier_3_Full_Profile**: The highest tier. Grants 100 tokens/day (~10-15 simulations). Requires a verified email, a display name, and at least one professional link (GitHub or LinkedIn).
- **Profile_Completeness**: A profile is considered complete (Tier_3_Full_Profile) when all three conditions are met: (1) display name is set, (2) email is verified, and (3) at least one professional link (GitHub or LinkedIn) is provided with a valid URL format.
- **Daily_Token_Limit**: The maximum number of tokens a user receives per day, determined by Token_Tier: 20 (Tier 1), 50 (Tier 2), or 100 (Tier 3).
- **Waitlist_Document**: The existing Firestore document in the `waitlist` collection keyed by email, containing `email`, `signed_up_at`, `token_balance`, and `last_reset_date`.
- **Profile_Document**: A Firestore document in the `profiles` collection keyed by email, containing `display_name`, `email_verified`, `github_url`, `linkedin_url`, `profile_completed_at`, `created_at`, `password_hash`, `country`, and `google_oauth_id`.
- **Verification_Token**: A unique, time-limited token sent to the user's email address to confirm ownership.
- **Auth_System**: The backend service responsible for password hashing, password verification, and Google OAuth token validation. Handles login authentication for accounts with passwords or linked Google accounts.
- **Password_Hash**: A bcrypt-hashed representation of the user's password stored in the Profile_Document. Null if the user has not set a password.
- **Country_Code**: An ISO 3166-1 alpha-2 country code (e.g., "US", "DE", "JP") stored in the Profile_Document to identify the user's country for leaderboard features.
- **Google_OAuth_ID**: The unique Google account identifier (`sub` claim from Google ID token) stored in the Profile_Document when a user links their Google account. Null if Google OAuth is not linked.
- **Login_Form**: The frontend waitlist/login form that captures the user's email and, conditionally, their password when the email is associated with a password-protected account.

## Requirements

### Requirement 1: Profile Document Creation

**User Story:** As a user, I want a profile document to be created when I first access the profile page, so that I can start filling in my profile information.

#### Acceptance Criteria

1. WHEN an authenticated user navigates to the Profile_Page for the first time, THE Profile_System SHALL create a Profile_Document in the `profiles` collection keyed by the user's email address.
2. THE Profile_System SHALL initialize the Profile_Document with `display_name` set to empty string, `email_verified` set to false, `github_url` set to null, `linkedin_url` set to null, `profile_completed_at` set to null, `created_at` set to the current server timestamp, `password_hash` set to null, `country` set to null, and `google_oauth_id` set to null.
3. WHEN an authenticated user navigates to the Profile_Page and a Profile_Document already exists, THE Profile_System SHALL return the existing Profile_Document without overwriting.

### Requirement 2: Profile Page Access

**User Story:** As a user, I want to access my profile by clicking on my email address in the header, so that I can manage my profile information.

#### Acceptance Criteria

1. THE Profile_Page SHALL be accessible by clicking the email address displayed in the protected routes header navigation.
2. THE Profile_Page SHALL display editable fields for display name, GitHub profile URL, LinkedIn profile URL, and country.
3. THE Profile_Page SHALL display the current email verification status (verified or not verified).
4. THE Profile_Page SHALL display a progress indicator showing which profile completion steps are done and which remain.
5. WHEN the user is not authenticated, THE Profile_Page SHALL redirect the user to the landing page.
6. THE Profile_Page SHALL display the Google OAuth link status (linked or not linked) and provide a button to link or unlink a Google account.

### Requirement 3: Display Name Management

**User Story:** As a user, I want to add and update my display name, so that I can personalize my profile.

#### Acceptance Criteria

1. WHEN the user submits a display name, THE Profile_System SHALL validate that the display name is between 2 and 100 characters in length.
2. WHEN the user submits a valid display name, THE Profile_System SHALL store the display name in the Profile_Document.
3. IF the user submits a display name shorter than 2 characters or longer than 100 characters, THEN THE Profile_System SHALL return a descriptive validation error message.
4. THE Profile_System SHALL trim leading and trailing whitespace from the display name before storing.

### Requirement 4: Email Verification

**User Story:** As a user, I want to verify my email address via a confirmation link, so that I can prove ownership of my email and unlock Tier_2_Verified token allowance.

#### Acceptance Criteria

1. WHEN the user requests email verification on the Profile_Page, THE Email_Verifier SHALL generate a unique Verification_Token and send a verification email to the user's registered email address using Amazon SES.
2. THE Email_Verifier SHALL set the Verification_Token to expire after 24 hours.
3. WHEN the user clicks the verification link containing a valid and non-expired Verification_Token, THE Email_Verifier SHALL set `email_verified` to true in the Profile_Document.
4. WHEN the user clicks the verification link and `email_verified` is set to true, THE Token_System SHALL immediately upgrade the user to Tier_2_Verified by setting the Waitlist_Document `token_balance` to 50 if the current balance is less than 50.
5. IF the user clicks a verification link containing an expired Verification_Token, THEN THE Email_Verifier SHALL display an error message and offer the option to resend a new verification email.
6. IF the user clicks a verification link containing an invalid Verification_Token, THEN THE Email_Verifier SHALL display an error message indicating the link is invalid.
7. WHEN the user's email is already verified, THE Profile_Page SHALL hide the verification request button and display a "Verified" status indicator.
8. THE Email_Verifier SHALL use Amazon SES as the email delivery service, configured with IAM credentials for the backend service account.

### Requirement 5: Professional Link Management

**User Story:** As a user, I want to add my GitHub or LinkedIn profile URL, so that I can complete my profile and earn the Tier_3_Full_Profile token allowance.

#### Acceptance Criteria

1. WHEN the user submits a GitHub URL, THE Profile_System SHALL validate that the URL matches the format `https://github.com/{username}` where `{username}` contains only alphanumeric characters, hyphens, and is between 1 and 39 characters.
2. WHEN the user submits a LinkedIn URL, THE Profile_System SHALL validate that the URL matches the format `https://linkedin.com/in/{slug}` or `https://www.linkedin.com/in/{slug}` where `{slug}` contains only alphanumeric characters, hyphens, and is between 3 and 100 characters.
3. WHEN the user submits a valid professional link URL, THE Profile_System SHALL store the URL in the corresponding field of the Profile_Document.
4. IF the user submits a URL that does not match the expected format, THEN THE Profile_System SHALL return a descriptive validation error specifying the expected format.
5. THE Profile_System SHALL require at least one professional link (GitHub or LinkedIn) for Profile_Completeness, but both are optional individually.

### Requirement 6: Tier Determination and Token Upgrade

**User Story:** As a user, I want my daily token allowance to increase as I complete profile milestones, so that I am rewarded for deeper engagement.

#### Acceptance Criteria

1. WHEN a user signs up via the waitlist form, THE Token_System SHALL assign Tier_1_Unverified with a Daily_Token_Limit of 20 by setting the Waitlist_Document `token_balance` to 20.
2. WHEN the user verifies their email address, THE Token_System SHALL upgrade the user to Tier_2_Verified with a Daily_Token_Limit of 50.
3. WHEN the user saves a profile update that results in Profile_Completeness, THE Token_System SHALL upgrade the user to Tier_3_Full_Profile with a Daily_Token_Limit of 100.
4. WHEN Profile_Completeness is achieved, THE Profile_System SHALL set `profile_completed_at` to the current server timestamp in the Profile_Document.
5. WHEN a tier upgrade occurs and the user's current `token_balance` is less than the new Daily_Token_Limit, THE Token_System SHALL set the `token_balance` to the new Daily_Token_Limit in the Waitlist_Document.
6. THE Profile_System SHALL evaluate Profile_Completeness on every profile save operation by checking all three conditions: display name is set, email is verified, and at least one professional link is present.
7. THE Token_System SHALL determine the user's Token_Tier by checking: (a) if `profile_completed_at` is non-null in the Profile_Document, the tier is Tier_3_Full_Profile (100); (b) else if `email_verified` is true in the Profile_Document, the tier is Tier_2_Verified (50); (c) otherwise the tier is Tier_1_Unverified (20).

### Requirement 7: Permanent Tier 3 Token Bonus

**User Story:** As a user, I want my Tier 3 token bonus to be permanent once earned, so that I do not lose my reward if I later modify my profile.

#### Acceptance Criteria

1. WHEN a user has a non-null `profile_completed_at` timestamp in the Profile_Document, THE Token_System SHALL use 100 as the Daily_Token_Limit regardless of the current state of the profile fields.
2. THE Token_System SHALL determine the Tier_3_Full_Profile status by checking the `profile_completed_at` field, not by re-evaluating Profile_Completeness on each token reset.

### Requirement 8: Token Display Update

**User Story:** As a user, I want the token display to reflect my current tier allowance, so that I can see my correct daily limit.

#### Acceptance Criteria

1. WHEN the user is at Tier_1_Unverified, THE Token_System SHALL display "Tokens: X / 20" in the TokenDisplay component.
2. WHEN the user is at Tier_2_Verified, THE Token_System SHALL display "Tokens: X / 50" in the TokenDisplay component.
3. WHEN the user is at Tier_3_Full_Profile, THE Token_System SHALL display "Tokens: X / 100" in the TokenDisplay component.
4. WHEN the user completes a tier upgrade on the Profile_Page, THE Token_System SHALL update the token display immediately without requiring a page refresh.
5. THE Token_System SHALL fetch the user's Token_Tier by checking the Profile_Document fields (`profile_completed_at` and `email_verified`) to determine the correct Daily_Token_Limit for display.

### Requirement 9: Profile API Endpoints

**User Story:** As a developer, I want RESTful API endpoints for profile management, so that the frontend can interact with the profile system.

#### Acceptance Criteria

1. THE Profile_System SHALL expose a `GET /api/v1/profile/{email}` endpoint that returns the Profile_Document for the given email.
2. THE Profile_System SHALL expose a `PUT /api/v1/profile/{email}` endpoint that updates the Profile_Document fields (display_name, github_url, linkedin_url, country).
3. THE Profile_System SHALL expose a `POST /api/v1/profile/{email}/verify-email` endpoint that triggers the email verification flow.
4. THE Profile_System SHALL expose a `GET /api/v1/profile/verify/{token}` endpoint that validates a Verification_Token and marks the email as verified.
5. IF a request targets a non-existent profile, THEN THE Profile_System SHALL return a 404 status code with a descriptive error message.
6. THE Profile_System SHALL validate all input fields using Pydantic V2 models before processing.
7. THE Auth_System SHALL expose a `POST /api/v1/auth/set-password` endpoint that accepts an email and password, hashes the password using bcrypt, and stores the Password_Hash in the Profile_Document.
8. THE Auth_System SHALL expose a `POST /api/v1/auth/login` endpoint that accepts an email and password, verifies the password against the stored Password_Hash, and returns the user session data on success.
9. THE Auth_System SHALL expose a `GET /api/v1/auth/check-email/{email}` endpoint that returns whether the given email has a Password_Hash set, enabling the Login_Form to conditionally show the password input.
10. THE Auth_System SHALL expose a `POST /api/v1/auth/google/link` endpoint that accepts a Google OAuth ID token, validates the token with Google, and stores the Google_OAuth_ID in the Profile_Document.
11. THE Auth_System SHALL expose a `POST /api/v1/auth/google/login` endpoint that accepts a Google OAuth ID token, validates the token with Google, looks up the Profile_Document by Google_OAuth_ID, and returns the user session data on success.
12. THE Auth_System SHALL expose a `DELETE /api/v1/auth/google/link/{email}` endpoint that removes the Google_OAuth_ID from the Profile_Document.

### Requirement 10: Tier-Aware Token Reset

**User Story:** As a developer, I want the token reset logic to account for the user's current tier, so that each user receives the correct daily allowance at midnight UTC.

#### Acceptance Criteria

1. WHEN the Token_System resets a user's tokens, THE Token_System SHALL check the `profiles` collection for the user's Profile_Document.
2. WHEN a Profile_Document with a non-null `profile_completed_at` exists, THE Token_System SHALL reset the `token_balance` to 100 in the Waitlist_Document.
3. WHEN a Profile_Document exists with `email_verified` set to true and `profile_completed_at` is null, THE Token_System SHALL reset the `token_balance` to 50 in the Waitlist_Document.
4. WHEN no Profile_Document exists or `email_verified` is false and `profile_completed_at` is null, THE Token_System SHALL reset the `token_balance` to 20 in the Waitlist_Document.

### Requirement 11: Password-Based Account Protection

**User Story:** As a user, I want to set a password on my account after verifying my email, so that other users cannot access my account by entering my email address.

#### Acceptance Criteria

1. WHEN the user has a verified email, THE Profile_Page SHALL display an option to set a password for the account.
2. WHEN the user submits a password, THE Auth_System SHALL validate that the password is between 8 and 128 characters in length.
3. WHEN the user submits a valid password, THE Auth_System SHALL hash the password using bcrypt and store the Password_Hash in the Profile_Document.
4. IF the user submits a password shorter than 8 characters or longer than 128 characters, THEN THE Auth_System SHALL return a descriptive validation error message.
5. WHEN a user enters an email on the Login_Form and a Profile_Document exists with a non-null Password_Hash for that email, THE Login_Form SHALL display a password input field.
6. WHEN a user enters an email on the Login_Form and no Password_Hash exists for that email, THE Login_Form SHALL proceed with the existing email-only login flow without prompting for a password.
7. WHEN the user submits an email and password on the Login_Form, THE Auth_System SHALL verify the submitted password against the stored Password_Hash using bcrypt comparison.
8. IF the submitted password does not match the stored Password_Hash, THEN THE Auth_System SHALL return a 401 status code with an "Invalid password" error message.
9. WHEN the user submits a correct email and password, THE Auth_System SHALL return the user session data and log the user in.
10. THE Auth_System SHALL allow the user to change their existing password by providing the current password and a new password on the Profile_Page.
11. IF the user provides an incorrect current password when changing their password, THEN THE Auth_System SHALL return a 401 status code and reject the password change.

### Requirement 12: Country Field Management

**User Story:** As a user, I want to set my country on my profile, so that my performance can be displayed on a country-based leaderboard.

#### Acceptance Criteria

1. THE Profile_Page SHALL display a country selection field with a dropdown of all ISO 3166-1 alpha-2 country codes and their corresponding country names.
2. WHEN the user selects a country, THE Profile_System SHALL validate that the submitted value is a valid ISO 3166-1 alpha-2 country code.
3. WHEN the user submits a valid country code, THE Profile_System SHALL store the Country_Code in the Profile_Document.
4. IF the user submits an invalid country code, THEN THE Profile_System SHALL return a descriptive validation error message.
5. THE Profile_Page SHALL display the user's currently selected country name on the profile view.
6. THE Profile_System SHALL include the `country` field in the `GET /api/v1/profile/{email}` response.
7. THE Profile_System SHALL accept the `country` field in the `PUT /api/v1/profile/{email}` request body.

### Requirement 13: Google OAuth Account Linking

**User Story:** As a user, I want to link my Google account to my profile after account creation, so that I can log in with Google instead of email and password.

#### Acceptance Criteria

1. WHEN the user has a verified email and is on the Profile_Page, THE Profile_Page SHALL display a "Link Google Account" button.
2. WHEN the user clicks "Link Google Account", THE Profile_Page SHALL initiate the Google OAuth consent flow using the Google Identity Services library.
3. WHEN the Google OAuth consent flow completes successfully, THE Auth_System SHALL validate the Google ID token with Google's token verification endpoint.
4. WHEN the Google ID token is valid, THE Auth_System SHALL store the Google_OAuth_ID (the `sub` claim from the ID token) in the Profile_Document.
5. IF the Google_OAuth_ID is already associated with a different Profile_Document, THEN THE Auth_System SHALL return a 409 status code with an error message indicating the Google account is already linked to another profile.
6. WHEN a user's Profile_Document has a non-null Google_OAuth_ID, THE Profile_Page SHALL display the linked Google account email and a "Unlink Google Account" button.
7. WHEN the user clicks "Unlink Google Account", THE Auth_System SHALL set the Google_OAuth_ID to null in the Profile_Document.
8. WHEN a user clicks "Sign in with Google" on the Login_Form, THE Auth_System SHALL validate the Google ID token and look up the Profile_Document by Google_OAuth_ID.
9. WHEN a matching Profile_Document is found for the Google_OAuth_ID, THE Auth_System SHALL return the user session data and log the user in.
10. IF no Profile_Document is found for the Google_OAuth_ID, THEN THE Auth_System SHALL return a 404 status code with an error message indicating no linked account was found.
11. THE Login_Form SHALL display a "Sign in with Google" button alongside the email input field.
