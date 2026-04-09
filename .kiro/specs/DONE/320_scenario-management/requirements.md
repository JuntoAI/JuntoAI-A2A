# Requirements Document

## Introduction

Scenario Management enables users to delete, rename, and manually edit their self-built (custom) scenarios. Deletion cascades to all connected negotiation sessions for data consistency, with an explicit user warning. Manual editing provides a JSON text editor with Pydantic validation before save. All operations apply exclusively to user-created custom scenarios — built-in scenarios remain immutable.

## Glossary

- **Custom_Scenario**: A user-created scenario stored in the `custom_scenarios` Firestore sub-collection or SQLite table, distinct from built-in file-based scenarios
- **Built_In_Scenario**: A scenario loaded from `.scenario.json` files in the scenarios data directory, managed by the ScenarioRegistry — not editable or deletable by users
- **Scenario_Management_API**: The set of backend REST endpoints that handle delete, rename, and update operations for custom scenarios
- **Session**: A negotiation session stored in the `negotiation_sessions` collection/table, linked to a scenario via the `scenario_id` field
- **Cascade_Delete**: The operation of deleting all Sessions linked to a Custom_Scenario when that scenario is deleted
- **JSON_Editor**: A frontend text editor component that allows users to view and modify the raw JSON of a Custom_Scenario
- **Validation_Gate**: The Pydantic V2 ArenaScenario model validation that scenario JSON must pass before it can be saved
- **Custom_Scenario_Store**: The persistence layer for custom scenarios (Firestore `CustomScenarioStore` or `SQLiteCustomScenarioStore`)
- **Session_Store**: The persistence layer for negotiation sessions (Firestore `FirestoreSessionClient` or `SQLiteSessionClient`)

## Requirements

### Requirement 1: Delete Custom Scenario with Cascade

**User Story:** As a user, I want to delete a custom scenario I built, so that I can remove scenarios I no longer need and keep my scenario list clean.

#### Acceptance Criteria

1. WHEN a user requests deletion of a Custom_Scenario, THE Scenario_Management_API SHALL identify all Sessions where `scenario_id` matches the Custom_Scenario being deleted
2. WHEN a user requests deletion of a Custom_Scenario, THE Scenario_Management_API SHALL delete all identified connected Sessions from the Session_Store before deleting the Custom_Scenario from the Custom_Scenario_Store
3. WHEN a user requests deletion of a Custom_Scenario, THE Scenario_Management_API SHALL return the count of deleted Sessions in the response body
4. IF the Custom_Scenario does not exist or is not owned by the requesting user, THEN THE Scenario_Management_API SHALL return HTTP 404 with a descriptive error message
5. IF deletion of any connected Session fails, THEN THE Scenario_Management_API SHALL abort the entire operation and return HTTP 500 with a descriptive error message
6. THE Scenario_Management_API SHALL reject deletion requests for Built_In_Scenarios by returning HTTP 403

### Requirement 2: Cascade Delete User Warning

**User Story:** As a user, I want to be warned about connected simulations before deleting a scenario, so that I do not accidentally lose simulation history.

#### Acceptance Criteria

1. WHEN a user initiates deletion of a Custom_Scenario, THE JSON_Editor SHALL display a confirmation dialog that lists the number of connected Sessions that will be deleted
2. WHEN the confirmation dialog is displayed, THE JSON_Editor SHALL require the user to explicitly confirm or cancel the deletion
3. IF the user cancels the confirmation dialog, THEN THE JSON_Editor SHALL abort the deletion and leave the Custom_Scenario unchanged
4. WHEN a user confirms deletion, THE JSON_Editor SHALL display a loading state until the Scenario_Management_API responds

### Requirement 3: Rename Custom Scenario

**User Story:** As a user, I want to rename a custom scenario, so that I can give it a more descriptive or accurate name without recreating it.

#### Acceptance Criteria

1. WHEN a user submits a new name for a Custom_Scenario, THE Scenario_Management_API SHALL update the `name` field inside the stored `scenario_json` and set the `updated_at` timestamp
2. THE Scenario_Management_API SHALL validate that the new name is a non-empty string with a minimum length of 1 character and a maximum length of 100 characters
3. IF the new name fails validation, THEN THE Scenario_Management_API SHALL return HTTP 422 with a descriptive error message
4. IF the Custom_Scenario does not exist or is not owned by the requesting user, THEN THE Scenario_Management_API SHALL return HTTP 404
5. THE Scenario_Management_API SHALL reject rename requests for Built_In_Scenarios by returning HTTP 403

### Requirement 4: Manual JSON Editing

**User Story:** As a user, I want to manually edit the raw JSON of a custom scenario in a text editor, so that I can make precise adjustments to agent configurations, toggles, and negotiation parameters.

#### Acceptance Criteria

1. WHEN a user opens the JSON_Editor for a Custom_Scenario, THE JSON_Editor SHALL display the full scenario JSON formatted with 2-space indentation
2. THE JSON_Editor SHALL provide a text editing area with monospace font and sufficient height for comfortable editing
3. WHEN a user modifies the JSON and submits, THE Scenario_Management_API SHALL validate the modified JSON against the ArenaScenario Pydantic model before saving
4. IF the modified JSON fails Pydantic validation, THEN THE Scenario_Management_API SHALL return HTTP 422 with the list of specific validation errors
5. IF the modified JSON is not valid JSON syntax, THEN THE JSON_Editor SHALL display a parse error message and prevent submission
6. WHEN the modified JSON passes validation, THE Scenario_Management_API SHALL overwrite the stored `scenario_json` and update the `updated_at` timestamp
7. THE JSON_Editor SHALL only be accessible for Custom_Scenarios — Built_In_Scenarios SHALL NOT display an edit option

### Requirement 5: Update Custom Scenario API

**User Story:** As a user, I want a reliable API endpoint to update my custom scenario, so that both rename and full JSON edit operations persist correctly across Firestore and SQLite storage modes.

#### Acceptance Criteria

1. THE Scenario_Management_API SHALL expose a `PUT /builder/scenarios/{scenario_id}` endpoint that accepts `email` (query parameter) and `scenario_json` (request body)
2. WHEN a valid update request is received, THE Scenario_Management_API SHALL validate the `scenario_json` against the ArenaScenario Pydantic model
3. IF validation passes, THEN THE Scenario_Management_API SHALL overwrite the stored scenario document and update the `updated_at` timestamp
4. IF validation fails, THEN THE Scenario_Management_API SHALL return HTTP 422 with the list of Pydantic validation errors
5. IF the scenario does not exist or is not owned by the requesting user, THEN THE Scenario_Management_API SHALL return HTTP 404
6. THE Custom_Scenario_Store SHALL implement an `update` method on both `CustomScenarioStore` (Firestore) and `SQLiteCustomScenarioStore` (SQLite) that overwrites `scenario_json` and `updated_at`

### Requirement 6: Session Lookup by Scenario

**User Story:** As a developer, I want to query sessions by scenario ID, so that cascade delete can identify all connected sessions efficiently.

#### Acceptance Criteria

1. THE Session_Store SHALL expose a `list_sessions_by_scenario` method that accepts `scenario_id` and `owner_email` parameters and returns all matching session documents
2. THE Session_Store SHALL expose a `delete_session` method that accepts `session_id` and removes the session document
3. WHEN `list_sessions_by_scenario` is called on `FirestoreSessionClient`, THE Session_Store SHALL query the `negotiation_sessions` collection filtering by `scenario_id` and `owner_email`
4. WHEN `list_sessions_by_scenario` is called on `SQLiteSessionClient`, THE Session_Store SHALL query the `negotiation_sessions` table filtering by `scenario_id` within the JSON `data` column and `owner_email`
5. WHEN `delete_session` is called, THE Session_Store SHALL remove the session document identified by `session_id`

### Requirement 7: Frontend Scenario Management UI

**User Story:** As a user, I want accessible edit and rename controls for my custom scenarios, so that I can manage them directly from the Arena page.

#### Acceptance Criteria

1. WHEN a Custom_Scenario is selected in the ScenarioSelector, THE ScenarioSelector SHALL display an edit button (Pencil icon) alongside the existing delete button
2. WHEN the user clicks the edit button, THE JSON_Editor SHALL open as a modal dialog displaying the full scenario JSON
3. THE JSON_Editor modal SHALL include a "Save" button that submits the edited JSON to the update endpoint and a "Cancel" button that discards changes
4. THE JSON_Editor modal SHALL include an inline editable name field at the top that allows renaming without opening the full JSON
5. WHEN a save operation succeeds, THE JSON_Editor SHALL close the modal and refresh the custom scenarios list
6. IF a save operation fails with validation errors, THEN THE JSON_Editor SHALL display the errors inline without closing the modal
7. THE ScenarioSelector SHALL NOT display edit or delete buttons for Built_In_Scenarios
