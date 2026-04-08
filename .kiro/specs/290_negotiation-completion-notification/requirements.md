# Requirements Document

## Introduction

Negotiations in JuntoAI take 3–10 minutes. Users frequently switch to another browser tab while waiting for the outcome. When a negotiation reaches a terminal state (Agreed, Blocked, or Failed), the application has no mechanism to recapture the user's attention. This feature adds browser notifications via the Web Notification API to alert users when their negotiation finishes, bringing them back to the Glass Box page to review the outcome.

This is a frontend-only feature. The backend already emits `NegotiationCompleteEvent` via SSE, and the reducer already processes `NEGOTIATION_COMPLETE` actions. The new behavior hooks into the existing dispatch flow.

## Glossary

- **Notification_Service**: A frontend module responsible for requesting notification permissions, constructing browser notifications, and handling notification click events.
- **Glass_Box_Page**: The session page (`/arena/session/[sessionId]`) that renders the live negotiation and outcome receipt.
- **Terminal_State**: A negotiation outcome of "Agreed", "Blocked", or "Failed" as set by the `NEGOTIATION_COMPLETE` reducer action.
- **Notification_API**: The W3C Web Notification API (`window.Notification`) supported by modern browsers for displaying system-level notifications.
- **Permission_State**: The browser's notification permission value: "default" (not yet asked), "granted", or "denied".
- **Document_Visibility**: Whether the current browser tab is visible to the user, determined by `document.visibilityState` or the `document.hidden` property.

## Requirements

### Requirement 1: Request Notification Permission

**User Story:** As a user starting a negotiation, I want the app to request notification permission, so that I can receive alerts when my negotiation finishes.

#### Acceptance Criteria

1. WHEN the Glass_Box_Page mounts and the Permission_State is "default", THE Notification_Service SHALL call `Notification.requestPermission()` to prompt the user for permission.
2. WHEN the Permission_State is "granted" or "denied", THE Notification_Service SHALL skip the permission request and proceed without prompting.
3. IF `Notification.requestPermission()` rejects with an error, THEN THE Notification_Service SHALL log the error to the console and continue normal operation without notifications.
4. IF the Notification_API is not available in the browser environment, THEN THE Notification_Service SHALL skip all notification logic and continue normal operation.

### Requirement 2: Send Browser Notification on Negotiation Completion

**User Story:** As a user who switched tabs during a negotiation, I want to receive a browser notification when the negotiation finishes, so that I can return to review the outcome.

#### Acceptance Criteria

1. WHEN a Terminal_State is reached and the Document_Visibility is "hidden" and the Permission_State is "granted", THE Notification_Service SHALL display a browser notification.
2. WHEN a Terminal_State is reached and the Document_Visibility is "visible", THE Notification_Service SHALL not display a browser notification.
3. WHEN a Terminal_State of "Agreed" is reached, THE Notification_Service SHALL display a notification with the title "Deal Agreed" and a body containing the final offer value from `finalSummary.current_offer` when available.
4. WHEN a Terminal_State of "Blocked" is reached, THE Notification_Service SHALL display a notification with the title "Deal Blocked" and a body containing the blocked-by agent name from `finalSummary.blocked_by` when available.
5. WHEN a Terminal_State of "Failed" is reached, THE Notification_Service SHALL display a notification with the title "Negotiation Failed" and a body containing the failure reason from `finalSummary.reason` when available.
6. THE Notification_Service SHALL include the JuntoAI application icon in the notification payload.
7. THE Notification_Service SHALL set the notification `tag` to the session ID to prevent duplicate notifications for the same session.

### Requirement 3: Handle Notification Click

**User Story:** As a user who received a notification, I want to click it to return to the negotiation results, so that I can review the outcome immediately.

#### Acceptance Criteria

1. WHEN the user clicks a browser notification, THE Notification_Service SHALL focus the originating browser tab or window.
2. WHEN the user clicks a browser notification, THE Notification_Service SHALL close the notification after focusing the tab.

### Requirement 4: Graceful Degradation

**User Story:** As a user on a browser or device that does not support notifications, I want the app to work normally without errors, so that my experience is not disrupted.

#### Acceptance Criteria

1. WHILE the Notification_API is unavailable, THE Glass_Box_Page SHALL render and function identically to the current behavior with no errors or visual changes.
2. WHILE the Permission_State is "denied", THE Notification_Service SHALL skip notification dispatch and produce no errors or console warnings.
3. IF the `new Notification()` constructor throws an error, THEN THE Notification_Service SHALL catch the error, log it to the console, and continue normal operation.

### Requirement 5: Notification Fires Only Once Per Session

**User Story:** As a user, I want to receive at most one notification per negotiation session, so that I am not spammed with duplicate alerts.

#### Acceptance Criteria

1. THE Notification_Service SHALL track whether a notification has already been sent for the current session ID.
2. WHEN a Terminal_State is reached and a notification has already been sent for the current session ID, THE Notification_Service SHALL skip sending a duplicate notification.
3. WHEN the Glass_Box_Page unmounts, THE Notification_Service SHALL reset the sent-notification tracking state for the session.
