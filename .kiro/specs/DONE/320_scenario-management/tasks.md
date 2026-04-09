# Implementation Plan: Scenario Management

## Overview

Add delete-with-cascade, rename, and manual JSON editing for custom scenarios. Backend gains new `SessionStore` methods, `CustomScenarioStore.update()`, a PUT endpoint, enhanced DELETE with cascade, and a session count endpoint. Frontend gains a JSON editor modal, updated ScenarioSelector with edit button, and new API functions.

## Tasks

- [x] 1. Extend SessionStore protocol and implementations
  - [x] 1.1 Add `list_sessions_by_scenario` and `delete_session` to SessionStore protocol
    - Add both method signatures to `backend/app/db/base.py` `SessionStore` protocol
    - _Requirements: 6.1, 6.2_

  - [x] 1.2 Implement `list_sessions_by_scenario` and `delete_session` on `FirestoreSessionClient`
    - In `backend/app/db/firestore_client.py`, add `list_sessions_by_scenario` querying by `scenario_id` and `owner_email`
    - Add `delete_session` that deletes a document by `session_id`
    - _Requirements: 6.1, 6.2, 6.3_

  - [x] 1.3 Implement `list_sessions_by_scenario` and `delete_session` on `SQLiteSessionClient`
    - In `backend/app/db/sqlite_client.py`, add `list_sessions_by_scenario` filtering JSON `data` column by `scenario_id` and `owner_email` (consistent with existing `list_sessions_by_owner` pattern)
    - Add `delete_session` with `DELETE FROM negotiation_sessions WHERE session_id = ?`
    - _Requirements: 6.1, 6.2, 6.4, 6.5_

  - [x] 1.4 Write property test: Session lookup returns exactly matching sessions (Property 1)
    - **Property 1: Session lookup returns exactly the matching sessions**
    - Generate random sessions with varying `scenario_id` and `owner_email` in SQLite, query with `list_sessions_by_scenario`, verify exact match set
    - Test location: `backend/tests/property/test_session_lookup.py`
    - **Validates: Requirements 1.1, 6.1, 6.3, 6.4**

  - [x] 1.5 Write property test: Session deletion removes the session (Property 5)
    - **Property 5: Session deletion removes the session**
    - Generate sessions, call `delete_session`, verify `get_session` raises `SessionNotFoundError`
    - Test location: `backend/tests/property/test_session_deletion.py`
    - **Validates: Requirements 6.2, 6.5**

  - [x] 1.6 Write unit tests for SQLiteSessionClient new methods
    - Test `list_sessions_by_scenario` with 0, 1, N matching sessions and mixed scenario_ids/emails
    - Test `delete_session` for existing and nonexistent session_ids
    - Test location: `backend/tests/unit/test_sqlite_session_methods.py`
    - _Requirements: 6.1, 6.2, 6.4, 6.5_

- [x] 2. Add CustomScenarioStore.update() method
  - [x] 2.1 Implement `update()` on `CustomScenarioStore` (Firestore)
    - In `backend/app/builder/scenario_store.py`, add `update(email, scenario_id, scenario_json) -> bool` that overwrites `scenario_json` and `updated_at`
    - Return `False` if document does not exist
    - _Requirements: 5.3, 5.6_

  - [x] 2.2 Implement `update()` on `SQLiteCustomScenarioStore`
    - `UPDATE custom_scenarios SET scenario_json = ?, updated_at = ? WHERE scenario_id = ? AND email = ?`
    - Return `True` if `rowcount > 0`, else `False`
    - _Requirements: 5.3, 5.6_

  - [x] 2.3 Write property test: Scenario update round-trip preserves data (Property 3)
    - **Property 3: Scenario update round-trip preserves data**
    - Generate valid ArenaScenario dicts, save, update, get, verify round-trip equivalence and `updated_at` monotonicity
    - Test location: `backend/tests/property/test_scenario_update.py`
    - **Validates: Requirements 3.1, 4.6, 5.3, 5.6**

  - [x] 2.4 Write unit tests for CustomScenarioStore.update
    - Test update existing scenario, update nonexistent scenario, verify `updated_at` changes
    - Test location: `backend/tests/unit/test_custom_scenario_store.py`
    - _Requirements: 5.3, 5.6_

- [x] 3. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Implement PUT /builder/scenarios/{scenario_id} endpoint
  - [x] 4.1 Add `UpdateScenarioRequest` model and PUT endpoint to builder router
    - In `backend/app/routers/builder.py`, add `UpdateScenarioRequest(BaseModel)` with `scenario_json: dict`
    - Implement `PUT /scenarios/{scenario_id}` that validates against `ArenaScenario`, checks ownership, calls `store.update()`, returns `{scenario_id, name, updated_at}`
    - Handle 404 (not found/not owned), 422 (validation errors), 401 (missing email)
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 4.3, 4.4, 4.6, 5.1, 5.2, 5.3, 5.4, 5.5_

  - [x] 4.2 Write property test: Validation gate accepts valid and rejects invalid scenarios (Property 4)
    - **Property 4: Validation gate accepts valid scenarios and rejects invalid ones**
    - Generate both valid and invalid scenario dicts, verify accept/reject behavior and error list non-empty on rejection
    - Test location: `backend/tests/property/test_validation_gate.py`
    - **Validates: Requirements 3.2, 4.3, 4.4, 5.2, 5.4**

  - [x] 4.3 Write unit tests for PUT endpoint
    - Test valid update, 404 not found, 422 validation error, 401 missing email
    - Test location: `backend/tests/unit/test_builder_update.py`
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

- [x] 5. Enhance DELETE endpoint with cascade logic and add session count endpoint
  - [x] 5.1 Enhance DELETE /builder/scenarios/{scenario_id} with cascade delete
    - Inject `SessionStore` dependency into `delete_scenario`
    - Before deleting scenario: call `list_sessions_by_scenario`, delete each session, abort on failure with 500
    - After all sessions deleted: delete the scenario
    - Return `{scenario_id, deleted_sessions_count, detail}`
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6_

  - [x] 5.2 Add GET /builder/scenarios/{scenario_id}/sessions/count endpoint
    - Returns `{count: N}` for the number of sessions linked to the scenario for the given email
    - Handle 404 if scenario not found/not owned, 401 if missing email
    - _Requirements: 2.1, 6.1_

  - [x] 5.3 Write property test: Cascade delete removes all sessions and returns correct count (Property 2)
    - **Property 2: Cascade delete removes all connected sessions and returns correct count**
    - Generate scenario + N sessions in SQLite, delete via endpoint, verify empty session list and correct count
    - Test location: `backend/tests/property/test_cascade_delete.py`
    - **Validates: Requirements 1.2, 1.3**

  - [x] 5.4 Write unit tests for enhanced DELETE and session count endpoint
    - Test cascade with 0, 1, N sessions; 404 scenario not found; 500 on session deletion failure
    - Test session count with 0, N sessions; 404 scenario not found
    - Test location: `backend/tests/unit/test_builder_cascade_delete.py`, `backend/tests/unit/test_session_count.py`
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.1_

- [x] 6. Checkpoint — Ensure all backend tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Frontend: Add new API functions in builder/api.ts
  - [x] 7.1 Add `updateCustomScenario` and `getScenarioSessionCount` to `frontend/lib/builder/api.ts`
    - `updateCustomScenario(email, scenarioId, scenarioJson)` → PUT to `/builder/scenarios/{id}`
    - `getScenarioSessionCount(email, scenarioId)` → GET `/builder/scenarios/{id}/sessions/count`
    - _Requirements: 5.1, 2.1_

  - [x] 7.2 Write tests for new builder API functions
    - Mock fetch, verify correct URL/method/body for both functions
    - Test location: `frontend/__tests__/lib/builder/api.test.ts`
    - _Requirements: 5.1, 2.1_

- [x] 8. Frontend: ScenarioEditorModal component
  - [x] 8.1 Create `ScenarioEditorModal` component
    - New file: `frontend/components/arena/ScenarioEditorModal.tsx`
    - Props: `isOpen`, `onClose`, `scenarioId`, `scenarioJson`, `onSave`
    - Inline editable name field (max 100 chars) at top
    - `<textarea>` with monospace font, 2-space indented JSON
    - Client-side `JSON.parse` validation (red border + error on invalid JSON, Save disabled)
    - Save button calls `onSave` with parsed JSON; Cancel discards changes
    - Display backend validation errors inline below textarea on 422
    - Loading state during save
    - _Requirements: 3.1, 3.2, 4.1, 4.2, 4.3, 4.5, 4.7, 7.2, 7.3, 7.4, 7.5, 7.6_

  - [x] 8.2 Write tests for ScenarioEditorModal
    - Test render with JSON, edit name, invalid JSON error state, save success, save with validation error, cancel
    - Test location: `frontend/__tests__/components/arena/ScenarioEditorModal.test.tsx`
    - _Requirements: 4.1, 4.2, 4.5, 7.3, 7.5, 7.6_

- [x] 9. Frontend: Delete confirmation dialog and updated ScenarioSelector
  - [x] 9.1 Create delete confirmation dialog component
    - New file: `frontend/components/arena/DeleteConfirmDialog.tsx`
    - Fetches session count via `getScenarioSessionCount` and displays "This will delete N connected simulations"
    - Confirm and Cancel buttons; loading state during delete
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

  - [x] 9.2 Update ScenarioSelector with edit button and wire modal/dialog
    - Add `onEditCustom` callback prop to `ScenarioSelectorProps`
    - Add Pencil icon button (Lucide `Pencil`) next to delete button, visible only for custom scenarios
    - Wire edit button to open `ScenarioEditorModal`, wire delete button to open `DeleteConfirmDialog`
    - Edit/delete buttons hidden for built-in scenarios
    - _Requirements: 7.1, 7.2, 7.3, 7.7_

  - [x] 9.3 Write tests for delete confirmation dialog
    - Test shows session count, confirm triggers delete, cancel aborts
    - Test location: `frontend/__tests__/components/arena/DeleteConfirmDialog.test.tsx`
    - _Requirements: 2.1, 2.2, 2.3_

  - [x] 9.4 Write tests for ScenarioSelector edit button
    - Test edit button visible for custom scenarios, hidden for built-in
    - Test location: `frontend/__tests__/components/arena/ScenarioSelector.test.tsx`
    - _Requirements: 7.1, 7.7_

- [x] 10. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Property tests use Hypothesis (already in project dependencies) with minimum 100 iterations
- Backend uses Python (FastAPI + Pydantic V2), frontend uses TypeScript (Next.js + React)
- All property tests tagged with `# Feature: 320_scenario-management, Property N: <title>`
- SQLite in-memory (`:memory:`) for database client tests per project conventions
