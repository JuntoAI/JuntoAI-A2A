# JuntoAI Mini → EspoCRM Integration

## Purpose of This Document

This is the **reference specification** for building the user registration ingest from JuntoAI Mini services into EspoCRM. It is designed to be used as input for a **Kiro spec** in the JuntoAI Mini workspace to implement the Cloud Function and publisher-side integration.

## Overview

JuntoAI Mini users register through three services — **Echo**, **Kinetic**, and **A2A**. Each registration must be synced into EspoCRM (`crm.juntoai.org`) as a **Contact** belonging to the **"JuntoAI Mini"** account (type: Customer) and assigned to the **"JuntoAI"** team.

Additionally, the **JuntoAI website** collects waitinglist signups which flow through **GoHighLevel (GHL)** and are synced into EspoCRM under a separate **"JuntoAI Waitinglist"** account. This keeps active product users cleanly separated from pre-signup interest.

## Problem

Each JuntoAI Mini service manages its own user registration independently. The website waitinglist lives in GHL with no CRM visibility. Without integration, the CRM has no visibility into who signed up, where they came from, or when — making outreach, support, and retention tracking impossible.

## Architecture

```text
┌──────────┐
│  Echo    │──┐
└──────────┘  │
┌──────────┐  │    ┌─────────────────┐    ┌──────────────────────┐    ┌──────────────────────┐
│ Kinetic  │──┼───→│  GCP Pub/Sub    │───→│  Cloud Function      │───→│  EspoCRM REST API    │
└──────────┘  │    │  (topic:        │    │  (espocrm-sync)      │    │  POST/PUT Contact    │
┌──────────┐  │    │   user-reg)     │    │                      │    │  crm.juntoai.org     │
│   A2A    │──┘    └─────────────────┘    └──────────────────────┘    └──────────────────────┘
└──────────┘              │ (on failure)
                          ▼
                   ┌─────────────────┐
                   │  Dead-letter    │
                   │  topic + alert  │
                   └─────────────────┘

┌──────────────┐    ┌─────────────────┐    ┌──────────────────────┐
│  JuntoAI     │───→│  GoHighLevel    │───→│  EspoCRM REST API    │
│  Website     │    │  (GHL)          │    │  (via GHL workflow)  │
│  Waitinglist │    │  Workflow        │    │  "JuntoAI Waitinglist│
└──────────────┘    └─────────────────┘    │   account"           │
                                           └──────────────────────┘
```

### Why Pub/Sub + Cloud Function (not direct API calls)

- **Decoupled**: Services don't need to know about EspoCRM. They publish an event; the CRM integration is a subscriber.
- **Resilient**: If EspoCRM is down during a registration, the message stays in Pub/Sub and retries automatically. No lost users.
- **Extensible**: Adding a fourth service (or a second subscriber like analytics) requires zero changes to existing services.
- **Auditable**: Dead-letter topic captures any failures for investigation.

Direct API calls from each service would tightly couple every service to EspoCRM's availability and API contract. That's a bad trade for a multi-product platform.

### Why separate accounts for Mini vs Waitinglist

- **"JuntoAI Mini"** = active product users who have registered and are using Echo, Kinetic, or A2A.
- **"JuntoAI Waitinglist"** = people who expressed interest via the website but haven't used a product yet.
- Different lifecycle stages. Mixing them pollutes customer data and makes reporting useless.
- When a waitinglist contact signs up for a Mini service, the Cloud Function's upsert logic will update their existing Contact (add the Mini service to their `juntoaiServices` field) and move them to the "JuntoAI Mini" account.

## CRM Entity Model

### Key decisions (non-negotiable)

| Decision | Value | Rationale |
| --- | --- | --- |
| Entity type | **Contact** (not Lead) | JuntoAI Mini users are customers, not unqualified leads |
| Mini Account | **"JuntoAI Mini"** (type: Customer) | All active Mini users belong to this account |
| Waitinglist Account | **"JuntoAI Waitinglist"** (type: Customer) | Website waitinglist signups, separate from active users |
| Team | **"JuntoAI"** | Team-based access control in EspoCRM |
| Contact uniqueness | **One Contact per email** | Upsert pattern — never duplicate, always update |

### Current CRM state

| Entity | Exists | Action needed |
| --- | --- | --- |
| Team "JuntoAI" | Yes | None — already exists |
| Account "JuntoAI Mini" | **No** | Must be created before deployment (type: Customer) |
| Account "JuntoAI Waitinglist" | **No** | Must be created before deployment (type: Customer) |

## Event Schema (Publisher Side)

Each service publishes a JSON message to the `user-registration` Pub/Sub topic **after successful registration** (post email verification if applicable).

```json
{
  "event": "user.registered",
  "source": "echo",
  "timestamp": "2026-04-17T14:30:00Z",
  "user": {
    "first_name": "Jane",
    "last_name": "Doe",
    "email": "jane@example.com",
    "phone": "+1-555-0100"
  },
  "metadata": {
    "registration_id": "550e8400-e29b-41d4-a716-446655440000",
    "plan": "pro",
    "referral_source": "organic"
  },
  "consent": {
    "marketing_email": true,
    "marketing_sms": false,
    "consent_timestamp": "2026-04-17T14:30:00Z",
    "consent_source": "echo_registration_form"
  }
}
```

### Field reference

| Field | Type | Required | Validation |
| --- | --- | --- | --- |
| `event` | string | yes | Must be `user.registered` |
| `source` | string | yes | One of: `echo`, `kinetic`, `a2a` |
| `timestamp` | ISO 8601 | yes | UTC, e.g. `2026-04-17T14:30:00Z` |
| `user.first_name` | string | yes | Non-empty, max 100 chars |
| `user.last_name` | string | yes | Non-empty, max 100 chars |
| `user.email` | string | yes | Valid email format. **Dedup key** in EspoCRM |
| `user.phone` | string | no | E.164 format preferred (e.g. `+15550100`) |
| `metadata.registration_id` | UUID v4 | yes | Idempotency key — must be unique per registration |
| `metadata.plan` | string | no | One of: `free`, `pro`, `enterprise` |
| `metadata.referral_source` | string | no | Free text: `organic`, `referral`, or a campaign ID |
| `consent.marketing_email` | boolean | yes | Whether user consented to marketing emails |
| `consent.marketing_sms` | boolean | yes | Whether user consented to marketing SMS |
| `consent.consent_timestamp` | ISO 8601 | yes | When consent was given/denied (UTC) |
| `consent.consent_source` | string | yes | Which form/service collected consent (e.g. `echo_registration_form`) |

> **Note**: The `user.company` field from the previous version has been removed. All Contacts are hardcoded to the "JuntoAI Mini" account. The `consent` object is **required** — every registration must record marketing consent status, even if both values are `false`.

## EspoCRM Entity Mapping

### New registrations → Contact (upsert)

The Cloud Function uses an **upsert** pattern: search by email, update if exists, create if not. There are never duplicate Contacts for the same email address.

| Event field | EspoCRM Contact field | Type | Notes |
| --- | --- | --- | --- |
| `user.first_name` | `firstName` | string | — |
| `user.last_name` | `lastName` | string | — |
| `user.email` | `emailAddress` | string | Primary email, **dedup key** |
| `user.phone` | `phoneNumber` | string | — |
| *(hardcoded)* | `accountId` | string | ID of "JuntoAI Mini" account |
| *(hardcoded)* | `teamsIds` | array | `["<juntoai-team-id>"]` |
| `source` | `juntoaiServices` | custom **Multi-Enum** | Accumulates: `echo`, `kinetic`, `a2a` |
| `metadata.plan` | `juntoaiPlan` | custom Enum | `free`, `pro`, `enterprise` — updated to latest |
| `metadata.referral_source` | `juntoaiReferral` | custom Varchar | Free text |
| `metadata.registration_id` | `juntoaiRegistrationId` | custom Varchar | UUID of the **first** registration |
| `timestamp` | `juntoaiRegisteredAt` | custom DateTime | Timestamp of the **first** registration |
| `consent.marketing_email` | `juntoaiMarketingEmail` | custom Boolean | Marketing email consent |
| `consent.marketing_sms` | `juntoaiMarketingSms` | custom Boolean | Marketing SMS consent |
| `consent.consent_timestamp` | `juntoaiConsentTimestamp` | custom DateTime | When consent was recorded |
| `consent.consent_source` | `juntoaiConsentSource` | custom Varchar | Which form collected consent |

### Upsert logic (replaces old dedup logic)

The Cloud Function searches for an existing Contact by `emailAddress` before deciding to create or update.

**If a Contact already exists:**

1. **Update** the existing Contact:
   - Append the new `source` to the `juntoaiServices` Multi-Enum array (if not already present).
   - Update `juntoaiPlan` to the latest value (if provided).
   - Update consent fields **only if the new consent timestamp is more recent** than the existing one (consent can be upgraded but not silently downgraded).
   - If the existing Contact is under the "JuntoAI Waitinglist" account and the new event is from a Mini service, **move** the Contact to the "JuntoAI Mini" account (they've graduated from waitinglist to active user).
2. Add a **Note** to the Contact for audit: `"Additional registration from {source} on {timestamp}. Registration ID: {registration_id}. Services: {updated_services_list}"`.
3. Log the update (registration_id and source only — no PII).
4. Return success (ack the Pub/Sub message).

**If no Contact exists:**

1. **Create** the Contact with all mapped fields.
2. Set `juntoaiServices` to `["{source}"]` (array with single entry).
3. Log success (registration_id and source only).
4. Return success.

### Consent update rules

Consent is a legal record. The Cloud Function follows these rules:

- **Consent can be granted**: If the new event has `marketing_email: true` and the existing Contact has `false`, update to `true` and record the new timestamp/source.
- **Consent can be revoked**: If the new event has `marketing_email: false` and the existing Contact has `true`, update to `false` and record the new timestamp/source.
- **Timestamp wins**: Always use the most recent `consent_timestamp` to determine which consent state is authoritative.
- **Never silently drop consent data**: Every consent change is logged in a Note on the Contact.

## Custom Fields to Add in EspoCRM

Before deploying the integration, add these custom fields to the **Contact** entity.

Path: **Administration → Entity Manager → Contact → Fields → Add Field**

| Field name | Label | Type | Values / Notes |
| --- | --- | --- | --- |
| `juntoaiServices` | JuntoAI Services | **Multi-Enum** | `echo`, `kinetic`, `a2a` — accumulates all services the contact uses |
| `juntoaiPlan` | JuntoAI Plan | Enum | `free`, `pro`, `enterprise` |
| `juntoaiReferral` | Referral Source | Varchar | Free text, max 255 chars |
| `juntoaiRegistrationId` | Registration ID | Varchar | UUID of the first registration, read-only after creation |
| `juntoaiRegisteredAt` | Registered At | DateTime | Timestamp of the first registration (UTC) |
| `juntoaiMarketingEmail` | Marketing Email Consent | Boolean | `true` = opted in, `false` = opted out |
| `juntoaiMarketingSms` | Marketing SMS Consent | Boolean | `true` = opted in, `false` = opted out |
| `juntoaiConsentTimestamp` | Consent Timestamp | DateTime | When consent was last recorded (UTC) |
| `juntoaiConsentSource` | Consent Source | Varchar | Which form/service collected consent, max 255 chars |

> **Note**: `juntoaiSource` (single Enum) from the previous version has been replaced by `juntoaiServices` (Multi-Enum) to support users who register for multiple Mini services.

## Cloud Function: `espocrm-sync`

### Runtime configuration

| Setting | Value |
| --- | --- |
| Runtime | Node.js 20 |
| Trigger | Pub/Sub push subscription on `user-registration` topic |
| Region | `us-central1` (same region as EspoCRM instance) |
| Memory | 256 MB |
| Timeout | 30s |
| Retry | Enabled (Pub/Sub handles retry on failure) |
| Concurrency | 1 (prevent race conditions on upsert) |

### Environment variables

| Variable | Value | Source |
| --- | --- | --- |
| `ESPOCRM_URL` | `https://crm.juntoai.org` | Secret Manager or hardcoded |
| `ESPOCRM_API_KEY` | API key for `juntoai-sync` user | Secret Manager: `espocrm-api-key` |
| `JUNTOAI_MINI_ACCOUNT_ID` | ID of "JuntoAI Mini" account | Secret Manager or hardcoded |
| `JUNTOAI_WAITINGLIST_ACCOUNT_ID` | ID of "JuntoAI Waitinglist" account | Secret Manager or hardcoded |
| `JUNTOAI_TEAM_ID` | ID of "JuntoAI" team | Secret Manager or hardcoded |

### EspoCRM API authentication

Create a dedicated **API User** in EspoCRM:

1. **Administration → API Users → Create**
2. Username: `juntoai-sync`
3. Authentication Method: **API Key**
4. Assign a Role with these permissions:

| Entity | Create | Read | Edit | Delete |
| --- | --- | --- | --- | --- |
| Contact | ✅ | ✅ | ✅ | ❌ |
| Account | ❌ | ✅ | ❌ | ❌ |
| Note | ✅ | ❌ | ❌ | ❌ |

> **Note**: Contact now requires **Edit** permission (previously was Create+Read only). The upsert pattern needs to update existing Contacts when a user registers for an additional Mini service.

5. Assign the user to the **"JuntoAI"** team.
6. Copy the generated API key → store in GCP Secret Manager.

The Cloud Function authenticates via the `X-Api-Key` header on every EspoCRM API request.

### EspoCRM API calls used

| Operation | Method | Endpoint | Purpose |
| --- | --- | --- | --- |
| Search Contact by email | `GET` | `/api/v1/Contact?where[0][type]=equals&where[0][attribute]=emailAddress&where[0][value]={email}` | Upsert: check if exists |
| Create Contact | `POST` | `/api/v1/Contact` | New registration (email not found) |
| Update Contact | `PUT` | `/api/v1/Contact/{id}` | Existing registration (append service, update fields) |
| Add Note | `POST` | `/api/v1/Note` | Audit trail for updates and new registrations |

### Pseudocode

```javascript
async function handleRegistrationEvent(pubsubMessage) {
  const event = JSON.parse(Buffer.from(pubsubMessage.data, 'base64').toString());

  // 1. Validate required fields (including consent)
  validateEvent(event); // throws on invalid

  // 2. Search for existing Contact by email (upsert check)
  const existing = await espocrmGet('/api/v1/Contact', {
    where: [{ type: 'equals', attribute: 'emailAddress', value: event.user.email }]
  });

  if (existing.total > 0) {
    // 3a. UPDATE existing Contact
    const contact = existing.list[0];
    const currentServices = contact.juntoaiServices || [];
    const updatedServices = currentServices.includes(event.source)
      ? currentServices
      : [...currentServices, event.source];

    const updatePayload = {
      juntoaiServices: updatedServices,
    };

    // Update plan if provided
    if (event.metadata.plan) {
      updatePayload.juntoaiPlan = event.metadata.plan;
    }

    // Update consent if newer timestamp
    const existingConsentTime = contact.juntoaiConsentTimestamp
      ? new Date(contact.juntoaiConsentTimestamp)
      : new Date(0);
    const newConsentTime = new Date(event.consent.consent_timestamp);

    if (newConsentTime > existingConsentTime) {
      updatePayload.juntoaiMarketingEmail = event.consent.marketing_email;
      updatePayload.juntoaiMarketingSms = event.consent.marketing_sms;
      updatePayload.juntoaiConsentTimestamp = event.consent.consent_timestamp;
      updatePayload.juntoaiConsentSource = event.consent.consent_source;
    }

    // Move from Waitinglist to Mini account if applicable
    if (contact.accountId === process.env.JUNTOAI_WAITINGLIST_ACCOUNT_ID) {
      updatePayload.accountId = process.env.JUNTOAI_MINI_ACCOUNT_ID;
    }

    await espocrmPut(`/api/v1/Contact/${contact.id}`, updatePayload);

    // Audit note
    await espocrmPost('/api/v1/Note', {
      type: 'Post',
      parentType: 'Contact',
      parentId: contact.id,
      post: `Additional registration from ${event.source} on ${event.timestamp}. Registration ID: ${event.metadata.registration_id}. Services: ${updatedServices.join(', ')}`
    });

    log('info', 'Contact updated', {
      registrationId: event.metadata.registration_id,
      source: event.source,
      action: 'update'
    });
    return; // ack message
  }

  // 3b. CREATE new Contact
  await espocrmPost('/api/v1/Contact', {
    firstName: event.user.first_name,
    lastName: event.user.last_name,
    emailAddress: event.user.email,
    phoneNumber: event.user.phone || null,
    accountId: process.env.JUNTOAI_MINI_ACCOUNT_ID,
    teamsIds: [process.env.JUNTOAI_TEAM_ID],
    juntoaiServices: [event.source],
    juntoaiPlan: event.metadata.plan || null,
    juntoaiReferral: event.metadata.referral_source || null,
    juntoaiRegistrationId: event.metadata.registration_id,
    juntoaiRegisteredAt: event.timestamp,
    juntoaiMarketingEmail: event.consent.marketing_email,
    juntoaiMarketingSms: event.consent.marketing_sms,
    juntoaiConsentTimestamp: event.consent.consent_timestamp,
    juntoaiConsentSource: event.consent.consent_source
  });

  log('info', 'Contact created', {
    registrationId: event.metadata.registration_id,
    source: event.source,
    action: 'create'
  });
}

function validateEvent(event) {
  const required = ['event', 'source', 'timestamp'];
  const requiredUser = ['first_name', 'last_name', 'email'];
  const requiredMeta = ['registration_id'];
  const requiredConsent = ['marketing_email', 'marketing_sms', 'consent_timestamp', 'consent_source'];
  const validSources = ['echo', 'kinetic', 'a2a'];

  // Check top-level
  for (const field of required) {
    if (!event[field]) throw new Error(`Missing required field: ${field}`);
  }
  if (event.event !== 'user.registered') throw new Error(`Invalid event type: ${event.event}`);
  if (!validSources.includes(event.source)) throw new Error(`Invalid source: ${event.source}`);

  // Check user fields
  if (!event.user) throw new Error('Missing user object');
  for (const field of requiredUser) {
    if (!event.user[field]) throw new Error(`Missing required user field: ${field}`);
  }

  // Check metadata
  if (!event.metadata) throw new Error('Missing metadata object');
  for (const field of requiredMeta) {
    if (!event.metadata[field]) throw new Error(`Missing required metadata field: ${field}`);
  }

  // Check consent
  if (!event.consent) throw new Error('Missing consent object');
  for (const field of requiredConsent) {
    if (event.consent[field] === undefined || event.consent[field] === null) {
      throw new Error(`Missing required consent field: ${field}`);
    }
  }
  if (typeof event.consent.marketing_email !== 'boolean') {
    throw new Error('consent.marketing_email must be a boolean');
  }
  if (typeof event.consent.marketing_sms !== 'boolean') {
    throw new Error('consent.marketing_sms must be a boolean');
  }
}

async function espocrmGet(path, params) {
  // GET request to ESPOCRM_URL + path with X-Api-Key header
}

async function espocrmPost(path, body) {
  // POST request to ESPOCRM_URL + path with X-Api-Key header and JSON body
}

async function espocrmPut(path, body) {
  // PUT request to ESPOCRM_URL + path with X-Api-Key header and JSON body
}

function log(level, message, context) {
  // Structured JSON logging — NO PII (no email, name, phone)
  console.log(JSON.stringify({ level, message, ...context, timestamp: new Date().toISOString() }));
}
```

### Error handling

| Scenario | Behavior | Pub/Sub retry? |
| --- | --- | --- |
| Invalid message (validation fails) | Log error, **ack** message | No — bad data won't fix itself |
| EspoCRM API 4xx (client error) | Log error, **ack** message | No — retrying won't help |
| EspoCRM API 5xx (server error) | Log error, **nack** message | Yes — EspoCRM may recover |
| EspoCRM unreachable (network) | Log error, **nack** message | Yes — transient failure |
| Unexpected exception | Log error, **nack** message | Yes — let Pub/Sub retry |

After max retries (Pub/Sub default: 5 attempts with exponential backoff), undeliverable messages go to the dead-letter topic.

## Waitinglist → EspoCRM Integration (via GHL)

### Overview

The JuntoAI website collects waitinglist signups. This data flows into **GoHighLevel (GHL)**, which triggers a workflow to create/update Contacts in EspoCRM under the **"JuntoAI Waitinglist"** account.

### GHL Workflow Design

The GHL workflow should call the EspoCRM REST API directly (or via a webhook → Cloud Function if you want the same upsert logic).

**Option A: GHL → EspoCRM API directly (simpler)**

GHL workflows support HTTP webhook actions. Configure a workflow that fires on new contact creation in GHL and calls:

1. `GET /api/v1/Contact?where[0][type]=equals&where[0][attribute]=emailAddress&where[0][value]={email}` — check if exists
2. If exists: `PUT /api/v1/Contact/{id}` — update fields
3. If not: `POST /api/v1/Contact` — create with `accountId` = "JuntoAI Waitinglist" account ID

**Option B: GHL → Pub/Sub → Cloud Function (reuses existing infra)**

Publish a `user.registered` event from GHL with `source: "waitinglist"`. This requires:
- Adding `waitinglist` to the `validSources` array in the Cloud Function
- Adding `waitinglist` to the `juntoaiServices` Multi-Enum values in EspoCRM
- The Cloud Function would use `JUNTOAI_WAITINGLIST_ACCOUNT_ID` when `source === "waitinglist"`

**Recommendation**: Option B is cleaner long-term. One integration path, one upsert logic, one audit trail. The GHL workflow just needs to publish a Pub/Sub message.

### Waitinglist-specific fields

For waitinglist contacts, marketing consent is **implicit** (they signed up for the waitinglist, which includes marketing consent). The GHL workflow should still pass explicit consent data:

```json
{
  "consent": {
    "marketing_email": true,
    "marketing_sms": true,
    "consent_timestamp": "2026-04-17T14:30:00Z",
    "consent_source": "juntoai_website_waitinglist"
  }
}
```

> **Important**: "Automatic" consent still needs to be recorded with a timestamp and source. GDPR requires proof of when and where consent was given, even if the form auto-opts-in.

### Waitinglist → Mini graduation

When a waitinglist contact later registers for a Mini service (Echo, Kinetic, or A2A), the Cloud Function's upsert logic handles the transition automatically:

1. Finds the existing Contact by email
2. Appends the Mini service to `juntoaiServices` (e.g., `["waitinglist", "echo"]`)
3. Moves the Contact from "JuntoAI Waitinglist" account to "JuntoAI Mini" account
4. Updates plan, consent, and other fields as needed
5. Adds an audit Note

No manual intervention required.

## Publisher-Side Integration Guide

This section is for the **Echo**, **Kinetic**, and **A2A** teams. Each service needs to publish a `user.registered` event to Pub/Sub after a successful user registration.

### Prerequisites

- GCP project access with Pub/Sub Publisher role
- Service account with `roles/pubsub.publisher` on the `user-registration` topic
- Node.js: `@google-cloud/pubsub` package

### Pub/Sub topic

```text
projects/{gcp-project-id}/topics/user-registration
```

### Node.js publisher example

```javascript
const { PubSub } = require('@google-cloud/pubsub');

const pubsub = new PubSub();
const topic = pubsub.topic('user-registration');

async function publishRegistrationEvent(user, source, metadata, consent) {
  const event = {
    event: 'user.registered',
    source: source, // 'echo' | 'kinetic' | 'a2a'
    timestamp: new Date().toISOString(),
    user: {
      first_name: user.firstName,
      last_name: user.lastName,
      email: user.email,
      phone: user.phone || null
    },
    metadata: {
      registration_id: metadata.registrationId, // UUID v4
      plan: metadata.plan || null,
      referral_source: metadata.referralSource || null
    },
    consent: {
      marketing_email: consent.marketingEmail,     // boolean, required
      marketing_sms: consent.marketingSms,         // boolean, required
      consent_timestamp: new Date().toISOString(), // when consent was given
      consent_source: `${source}_registration_form` // which form collected it
    }
  };

  const messageId = await topic.publishMessage({
    data: Buffer.from(JSON.stringify(event))
  });

  console.log(`Published registration event: ${messageId}`);
  return messageId;
}
```

### When to publish

Publish **after** the registration is fully committed (user record saved to your database, email verification sent if applicable). Do NOT publish before the registration is persisted — if your DB write fails after publishing, you'll have a ghost Contact in EspoCRM.

### Consent collection requirements

Each Mini service registration form **must** include:

1. A checkbox (unchecked by default) for marketing email consent
2. A checkbox (unchecked by default) for marketing SMS consent
3. A link to the privacy policy

The consent values (`true`/`false`) must be passed to the publisher function. Do NOT hardcode `true` — that's a GDPR violation.

### Error handling on publish failure

If `topic.publishMessage()` throws:

1. **Log the error** with the registration_id.
2. **Do NOT block the user registration** — the user's registration should succeed even if CRM sync fails.
3. **Queue for retry** — use a local retry mechanism (e.g., a background job queue) or rely on your service's error monitoring to flag missed publishes.

### Authentication

Each service authenticates to Pub/Sub via its GCP service account. Options:

- **GKE/Cloud Run**: Workload Identity (preferred — no key management)
- **VM/other**: Service account JSON key (store in Secret Manager, not in code)

## GCP Resources Required

Add to the existing Terraform configuration in `/terraform/`:

| Resource | Type | Purpose |
| --- | --- | --- |
| `google_pubsub_topic.user_registration` | Pub/Sub Topic | Receives registration events from all services |
| `google_pubsub_topic.user_registration_dlq` | Pub/Sub Topic | Dead-letter for failed messages |
| `google_pubsub_subscription.espocrm_sync` | Pub/Sub Subscription | Pushes to Cloud Function |
| `google_cloudfunctions2_function.espocrm_sync` | Cloud Function v2 | Processes events, calls EspoCRM API |
| `google_secret_manager_secret.espocrm_api_key` | Secret | API key for EspoCRM API user |
| `google_secret_manager_secret.juntoai_mini_account_id` | Secret | EspoCRM Account ID for "JuntoAI Mini" |
| `google_secret_manager_secret.juntoai_waitinglist_account_id` | Secret | EspoCRM Account ID for "JuntoAI Waitinglist" |
| `google_secret_manager_secret.juntoai_team_id` | Secret | EspoCRM Team ID for "JuntoAI" |
| `google_monitoring_alert_policy.dlq_alert` | Monitoring Alert | Alerts on dead-letter messages |

### Estimated cost

Negligible at < 1,000 registrations/month. Pub/Sub, Cloud Functions, and Secret Manager all fall within GCP free tier.

## Rollout Plan

### Phase 1: EspoCRM Setup (manual, ~45 min)

1. Create Account **"JuntoAI Mini"** (type: Customer) — assign to "JuntoAI" team
2. Create Account **"JuntoAI Waitinglist"** (type: Customer) — assign to "JuntoAI" team
3. Add custom fields to **Contact** entity (see custom fields table above — note `juntoaiServices` is Multi-Enum, not Enum)
4. Create API User `juntoai-sync` with API Key auth and permissions: Contact Create+Read+Edit, Account Read, Note Create
5. Store API key in GCP Secret Manager
6. Record the Account IDs (Mini + Waitinglist) and Team ID for use in Cloud Function env vars

### Phase 2: Infrastructure (Terraform, ~1 hour)

1. Add Pub/Sub topics, subscription, Cloud Function, and secrets to Terraform
2. `terraform plan` → review
3. `terraform apply`
4. Verify Cloud Function deploys and can reach `crm.juntoai.org`

### Phase 3: Service Integration (per service, ~2 hours each)

1. Add `@google-cloud/pubsub` to the service
2. Add consent checkboxes to registration forms
3. Implement the publisher with consent data (see publisher example above)
4. Deploy to staging and verify end-to-end with a test registration
5. Verify Contact appears in EspoCRM with correct account, team, services, consent, and field mapping

### Phase 4: Waitinglist Integration (~2 hours)

1. Configure GHL workflow to publish to Pub/Sub (Option B) or call EspoCRM API directly (Option A)
2. Test waitinglist signup → Contact creation under "JuntoAI Waitinglist" account
3. Test graduation: waitinglist contact signs up for a Mini → Contact moves to "JuntoAI Mini" account

### Phase 5: Multi-Service Testing (~1 hour)

1. Register same email on Echo → verify Contact created with `juntoaiServices: ["echo"]`
2. Register same email on Kinetic → verify Contact updated to `juntoaiServices: ["echo", "kinetic"]`
3. Verify plan, consent, and other fields updated correctly
4. Verify audit Notes created on each update

### Phase 6: Monitoring and Validation

1. Verify Contacts appear in EspoCRM with correct field mapping
2. Confirm dead-letter alerting works (publish a malformed message)
3. Test deduplication (register same email from two services)
4. Set up an EspoCRM dashboard: Contacts by Services, Contacts by Plan, Contacts by Account

## Monitoring

| Signal | Tool | Alert threshold |
| --- | --- | --- |
| Dead-letter messages | Cloud Monitoring | DLQ count > 0 in 5 min window |
| Cloud Function errors | Cloud Monitoring | Error rate > 5% |
| Cloud Function latency | Cloud Monitoring | p99 > 10s |
| EspoCRM API errors | Cloud Function logs | Any 4xx/5xx from EspoCRM |
| Contact creation rate | EspoCRM dashboard | Visual — no automated alert |
| Contact update rate | EspoCRM dashboard | Visual — tracks multi-service registrations |

## Security

- **EspoCRM API key**: Stored in Secret Manager. Never in code or env vars at rest.
- **API User**: Minimal permissions — Contact Create+Read+Edit, Account Read, Note Create only.
- **Pub/Sub**: Messages stay within the GCP project. No external exposure.
- **Cloud Function**: Runs in the same VPC as EspoCRM (or uses Serverless VPC Access). Traffic stays internal.
- **No PII in logs**: Cloud Function logs `registration_id` and `source` only. Never email, name, or phone.
- **Publisher auth**: Service accounts with `roles/pubsub.publisher` only. No broader permissions.
- **Consent data**: Stored in EspoCRM with timestamp and source. Every consent change is audited via Notes.

## Kiro Spec Guidance

When creating a Kiro spec in the JuntoAI Mini workspace to implement this integration, structure it as follows:

### Suggested spec requirements

1. Cloud Function `espocrm-sync` that subscribes to the `user-registration` Pub/Sub topic
2. Event validation matching the schema defined in this document (including consent fields)
3. **Upsert by email address** — search, update if exists, create if not. Never duplicate.
4. Multi-Enum `juntoaiServices` field accumulates all services per Contact
5. Contact creation with hardcoded account ("JuntoAI Mini") and team ("JuntoAI") assignment
6. Waitinglist → Mini account graduation on subsequent Mini registration
7. Marketing consent tracking with timestamp-based update logic
8. Audit Notes on every create and update
9. Structured logging with no PII
10. Error handling with correct ack/nack behavior per error type
11. Publisher utility function for each Mini service (Echo, Kinetic, A2A) with consent data

### Suggested spec tasks

1. **Scaffold Cloud Function project** — Node.js 20, TypeScript, with `@google-cloud/functions-framework` and `@google-cloud/pubsub`
2. **Implement event validation** — validate all required fields including consent, reject invalid messages
3. **Implement EspoCRM API client** — GET/POST/PUT with `X-Api-Key` auth, retry on 5xx, structured error handling
4. **Implement upsert logic** — search Contact by email, update if exists (append service, update consent), create if not
5. **Implement account graduation** — move Contact from Waitinglist to Mini account when applicable
6. **Implement consent tracking** — timestamp-based consent updates, audit Notes on changes
7. **Implement publisher utility** — reusable function for Echo/Kinetic/A2A to publish events with consent
8. **Add Terraform resources** — Pub/Sub topics, subscription, Cloud Function, secrets (including waitinglist account ID), monitoring alerts
9. **Write tests** — unit tests for validation, upsert logic, consent rules, account graduation, field mapping; integration test against EspoCRM sandbox

### Reference files for the spec

Include this document as a reference in the spec:

```markdown
#[[file:docs/juntoai-mini-espocrm-integration.md]]
```
