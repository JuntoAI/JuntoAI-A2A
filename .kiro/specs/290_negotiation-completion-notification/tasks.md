# Tasks

## Task 1: Create `buildNotificationContent` pure function

- [ ] 1.1 Create `frontend/lib/notificationContent.ts` with the `NotificationContent` interface and `buildNotificationContent` function
- [ ] 1.2 Implement status-to-title mapping: "Agreed" → "Deal Agreed", "Blocked" → "Deal Blocked", "Failed" → "Negotiation Failed"
- [ ] 1.3 Implement status-to-body mapping: extract `current_offer`, `blocked_by`, or `reason` from finalSummary with fallback strings

## Task 2: Create `useNotification` hook

- [ ] 2.1 Create `frontend/hooks/useNotification.ts` with the `UseNotificationOptions` interface
- [ ] 2.2 Implement Notification API availability guard (skip all logic if `window.Notification` is undefined)
- [ ] 2.3 Implement permission request on mount when `Notification.permission === "default"`
- [ ] 2.4 Implement notification dispatch on terminal state: check `document.hidden`, permission granted, and dedup ref
- [ ] 2.5 Implement click handler: `window.focus()` then `notification.close()`
- [ ] 2.6 Implement deduplication tracking via `useRef<Set<string>>` keyed by session ID, reset on unmount
- [ ] 2.7 Implement error handling: try/catch around `requestPermission()` and `new Notification()`, log to console

## Task 3: Integrate hook into GlassBoxPage

- [ ] 3.1 Add `useNotification({ sessionId, dealStatus: state.dealStatus, finalSummary: state.finalSummary })` call in `frontend/app/(protected)/arena/session/[sessionId]/page.tsx`

## Task 4: Add application icon for notifications

- [ ] 4.1 Ensure a notification icon exists at `frontend/public/icon-192.png` (or reference existing favicon/logo) and reference it in the hook's Notification options

## Task 5: Write property-based tests

- [ ] 5.1 Create `frontend/__tests__/properties/notificationContent.property.test.ts` — Property 2: Status-specific content mapping
- [ ] 5.2 Create `frontend/__tests__/properties/useNotification.property.test.ts` — Property 1: Visibility gate and Property 3: Deduplication

## Task 6: Write unit tests

- [ ] 6.1 Create `frontend/__tests__/hooks/useNotification.test.ts` with tests for: permission request on mount, skip when granted/denied, requestPermission rejection, API unavailable, click handler, permission denied skip, constructor throws, unmount resets tracking
