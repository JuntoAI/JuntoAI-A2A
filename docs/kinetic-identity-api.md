# Kinetic Identity API

Cross-product persona access layer for JuntoAI services.

## Problem

Kinetic (CareerGraph) produces the richest professional identity data in the JuntoAI ecosystem — archetype classification, verified war stories, values, communication patterns, depth scores. Multiple products need this data:

- **Echo (CopyWriter)**: Seed persona for voice interviews, enrich post generation with verified professional DNA
- **GCP Mini Service**: Persona import for its own product flow (runs on Google Cloud, not in this repo)
- **Future JuntoAI products**: Any service that benefits from knowing the user's professional identity

Currently there is no cross-product access path. Each service would need to understand Kinetic's S3 storage internals, hold AWS credentials, and parse raw Career Graph JSON. That doesn't scale.

### The Identity Matching Challenge

Users across JuntoAI products use different OAuth providers and different email addresses:

- **Echo**: Mostly LinkedIn OAuth → `john.doe@company.com`
- **Kinetic**: Mostly Google OAuth → `john@gmail.com`
- **GCP Service**: Mostly Google OAuth → `john@gmail.com` (or different)

The same human may have completely different emails across products. Email-based matching is unreliable. OAuth subject IDs don't match across providers. There is no shared user registry.

**Conclusion:** Automatic identity matching is not possible. The user must explicitly link their accounts across products.

## Solution: REST API + Explicit Account Linking

A versioned REST endpoint on the CareerGraph service that returns a curated, consent-gated "Identity Envelope." Cross-product identity is established via an explicit linking flow where the user proves ownership of both accounts.

### Why REST API (Not Other Approaches)

| Approach | Verdict |
|----------|---------|
| Direct S3 access | Tight coupling, credential sprawl, no consent layer. Rejected. |
| **REST API on CareerGraph** | **Clean contract, works from any cloud, consent enforcement, minimal new infra. Chosen.** |
| Dedicated Identity Microservice | Right architecture at scale, wrong timing. Revisit at 10K+ users / 5+ products. |
| S3 + CloudFront signed URLs | Auth layer ends up being a mini-service anyway. Extra steps for same result. |
| Event-driven (SNS/EventBridge) | Great complement for push notifications. Add later as Phase 2. |

### Why Explicit Linking (Not Email/OAuth Matching)

| Approach | Verdict |
|----------|---------|
| Email-based matching | Broken. Same human uses different emails across products. |
| OAuth subject ID matching | Only works if user uses same provider on both products. Partial at best. |
| Shared Identity Table (central registry) | Massive infrastructure change. Still needs linking for cross-provider cases. Overkill. |
| **Explicit Account Linking** | **User proves ownership of both accounts. Works regardless of provider/email. Industry standard.** |

## Authentication: Two Layers

### Layer 1 — Service Auth (API Keys)

Each consuming product gets one static API key. The key identifies the product, not the user.

- Echo: one API key stored in AWS SSM (`/juntoai/{env}/identity-api/echo-api-key`)
- GCP Service: one API key stored in GCP Secret Manager

Passed as a header on every request:

```
GET /v1/identity/:kineticUserId
X-Api-Key: <service-api-key>
```

CareerGraph validates the key and resolves which service is calling:

```javascript
const SERVICE_KEYS = {
  echo: process.env.IDENTITY_API_KEY_ECHO,
  'gcp-service': process.env.IDENTITY_API_KEY_GCP
};

function authenticateService(req, res, next) {
  const apiKey = req.headers['x-api-key'];
  const serviceId = Object.entries(SERVICE_KEYS)
    .find(([_, key]) => key === apiKey)?.[0];

  if (!serviceId) return res.status(401).json({ error: 'Invalid API key' });

  req.serviceId = serviceId;
  next();
}
```

**Why API keys (not JWTs) for now:** Two consumers. Static keys in secret stores are secure enough and trivial to implement. When a third consumer arrives or key rotation without redeployment becomes necessary, upgrade to service-to-service JWTs (short-lived tokens via a token endpoint).

### Layer 2 — User Consent (Via Account Linking)

Consent is established during the account linking flow. When a user links their Echo account to their Kinetic profile, they explicitly confirm "Allow Echo to access my professional identity" on Kinetic's domain. No separate consent mechanism needed — linking IS consent.

## Account Linking Flow

The user is the bridge between their own accounts. They prove ownership of both by logging into both.

### Step-by-Step Flow

```
Echo (or GCP Service)                    Kinetic (CareerGraph)
        │                                       │
        │  1. User clicks "Connect Kinetic"     │
        │                                       │
        │  2. Redirect to:                      │
        │     kinetic.juntoai.org/link?         │
        │     service=echo&                     │
        │     callback=echo.juntoai.org/        │
        │     link/callback                     │
        │──────────────────────────────────────→│
        │                                       │
        │                          3. User logs into Kinetic
        │                             (Google OAuth — whatever
        │                              they used on Kinetic)
        │                                       │
        │                          4. Kinetic shows consent page:
        │                             "Allow Echo to access your
        │                              professional identity?"
        │                                       │
        │                          5. User confirms
        │                                       │
        │                          6. Kinetic generates one-time
        │                             linking code (5-min TTL)
        │                             Stores: code → kineticUserId
        │                                       │
        │  7. Redirect back:                    │
        │     echo.juntoai.org/link/callback?   │
        │     code=abc123                       │
        │←──────────────────────────────────────│
        │                                       │
        │  8. Echo backend calls:               │
        │     POST /v1/identity/link            │
        │     X-Api-Key: <echo-key>             │
        │     { "code": "abc123" }              │
        │──────────────────────────────────────→│
        │                                       │
        │                          9. Kinetic validates code
        │                         10. Stores consent:
        │                             identityConsent.echo = {
        │                               grantedAt, serviceId
        │                             }
        │                         11. Returns kineticUserId
        │                                       │
        │  { "kineticUserId": "cg-123",         │
        │    "linked": true }                   │
        │←──────────────────────────────────────│
        │                                       │
        │  12. Echo stores mapping:             │
        │      echoUserId → kineticUserId       │
        │      in its own DynamoDB              │
```

### After Linking

Echo (or GCP service) uses the `kineticUserId` for all subsequent Identity API calls:

```
GET /v1/identity/cg-123
X-Api-Key: <echo-key>
```

CareerGraph checks:
1. Valid API key → identifies "echo"
2. `identityConsent.echo` exists on user `cg-123`
3. If no consent → 403
4. If consent → return Identity Envelope

### Why This Works

- **Different emails?** Doesn't matter. User logs into each product with whatever OAuth they used there.
- **Different OAuth providers?** Doesn't matter. The linking flow doesn't compare providers or emails.
- **Consent is real.** User explicitly confirms on Kinetic's domain. No trust assumption.
- **Same pattern for every product.** GCP service, future products — identical flow.
- **One-time action.** Link once, access forever (until revoked).

### Linking Endpoints (Kinetic Side)

**Initiate linking (browser redirect):**
```
GET /v1/link?service=echo&callback=https://echo.juntoai.org/link/callback
```
- Renders Kinetic login page (if not already authenticated)
- Shows consent screen: "Allow [service] to access your professional identity?"
- On confirm: generates one-time code, redirects to callback URL with `?code=<code>`

**Exchange code (server-to-server):**
```
POST /v1/identity/link
X-Api-Key: <service-api-key>
Content-Type: application/json

{
  "code": "abc123"
}

Response (200):
{
  "kineticUserId": "cg-123",
  "linked": true,
  "archetype": "The Fixer"
}

Response (400):
{ "error": "Invalid or expired linking code" }
```

**Linking code rules:**
- One-time use (deleted after exchange)
- 5-minute TTL
- Stored in DynamoDB with TTL: `{ code, kineticUserId, serviceId, expiresAt }`

## Consent Data Model

Stored on the CareerGraph user record in DynamoDB (`juntoai-careergraph-users-v2-{env}`):

```json
{
  "userId": "cg-123",
  "email": "john@gmail.com",
  "identityConsent": {
    "echo": {
      "grantedAt": "2026-04-05T10:00:00Z",
      "linkedAt": "2026-04-05T10:00:00Z"
    },
    "gcp-service": {
      "grantedAt": "2026-04-05T11:00:00Z",
      "linkedAt": "2026-04-05T11:00:00Z"
    }
  }
}
```

### Consent Revocation

**User-initiated (Kinetic settings):**
User goes to Kinetic settings → sees "Connected products: Echo ✓, GCP Service ✓" → clicks "Revoke" on Echo → `identityConsent.echo` deleted → next Echo API call returns 403.

**Service-initiated:**
```
DELETE /v1/identity/:kineticUserId/consent
X-Api-Key: <service-api-key>
```

Removes consent for the calling service. Immediate effect.

**Consumer-side cleanup:** When Echo receives a 403, it should clear its cached `kineticUserId` mapping and show the user "Kinetic profile disconnected. Reconnect?"

## Identity Envelope Schema

Versioned, curated payload. Sensitive fields (red flags, salary expectations) are excluded by default.

```json
{
  "version": "1.0",
  "kineticUserId": "string",
  "lastUpdated": "ISO-8601",
  "archetype": {
    "name": "The Fixer | The Builder | The Scaler",
    "reasoning": "2-3 sentence explanation"
  },
  "professionalIdentity": {
    "currentRole": "string",
    "company": "string",
    "industry": "string",
    "experienceYears": 15,
    "summary": "2-3 sentence professional summary"
  },
  "skills": {
    "top": ["skill1", "skill2", "skill3", "skill4", "skill5"],
    "verified": [
      {
        "skill": "string",
        "evidence": "string (war story summary)",
        "metrics": "string (quantified impact)",
        "verified": true
      }
    ]
  },
  "communicationStyle": {
    "tone": "authoritative | conversational | analytical | storytelling",
    "formality": "casual | professional | formal",
    "vocabularyComplexity": "simple | moderate | advanced",
    "patterns": {
      "usesMetaphors": false,
      "usesData": true,
      "usesStories": true
    }
  },
  "contentThemes": ["theme1", "theme2", "theme3"],
  "values": ["autonomy", "impact", "collaboration"],
  "depthScore": 85,
  "credibilityIndex": "High | Medium | Fluff"
}
```

### What's Excluded (Privacy Boundary)

These fields exist in the full Career Graph but are never exposed via the Identity API:

- `redFlags` — internal career assessment, not for public-facing products
- Salary/compensation expectations
- Specific employer names from `redFlags` context
- Raw interview transcript
- Audio recordings
- User email (consumers already have their own user's email)

### What Each Consumer Does With It

**Echo (CopyWriter):**
- `archetype` + `professionalIdentity` → persona seed (skip "getting to know you" phase)
- `skills.verified` → ready-made content material with war stories
- `communicationStyle` → pre-built StyleProfile (skip style analysis on first session)
- `contentThemes` → suggested content angles
- `values` → tone calibration for post generation

**GCP Service (and future products):**
- Same envelope, different "lens" — each consumer maps the fields it needs
- The API returns the same contract regardless of who's calling

## API Design

### Endpoints Summary

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| `GET` | `/v1/link?service=X&callback=URL` | Browser (user session) | Initiate account linking |
| `POST` | `/v1/identity/link` | API key | Exchange linking code for kineticUserId |
| `GET` | `/v1/identity/:kineticUserId` | API key | Fetch Identity Envelope |
| `DELETE` | `/v1/identity/:kineticUserId/consent` | API key | Revoke consent for calling service |

### Fetch Identity Envelope

```
GET /v1/identity/:kineticUserId
X-Api-Key: <service-api-key>
```

### Response Codes

| Code | Meaning |
|------|---------|
| 200 | Identity Envelope returned |
| 401 | Invalid or missing API key |
| 403 | User has not granted consent to this service |
| 404 | No Kinetic profile exists for this userId |
| 429 | Rate limit exceeded |

### Rate Limiting

- 100 requests/minute per service
- Consumers should cache the envelope locally (see Caching below)

## Caching Strategy

The Identity Envelope rarely changes (only after a new Kinetic interview). Consumers should cache aggressively.

### AWS Consumers (Echo)

- Store envelope in DynamoDB (`juntoai-copywriter-users` table, `kineticIdentity` field)
- Also store `kineticUserId` mapping on the Echo user record
- TTL: 7 days
- Refresh: on user action ("Refresh Kinetic profile" button) or on `CAREER_GRAPH_COMPLETED` event (Phase 2)

### GCP Consumers

- Store envelope in Firestore or Redis
- Also store `kineticUserId` mapping on the GCP user record
- TTL: 7 days
- Refresh: on user action or webhook notification (Phase 2)

### Cache Invalidation (Phase 2)

When a user completes a new Kinetic interview, publish an event. Consumers that subscribe can refresh their cache proactively. See Phase 2 below.

## Infrastructure

### ALB Routing

Add path rules on the existing ALB for the CareerGraph service:

```
Path: /careergraph/v1/identity/*  →  CareerGraph ECS target group (port 3003)
Path: /careergraph/v1/link*       →  CareerGraph ECS target group (port 3003)
Priority: [next available]
```

This keeps the Identity API on the same service — no new ECS service needed.

### SSM Parameters

```
/juntoai/{env}/identity-api/echo-api-key
/juntoai/{env}/identity-api/gcp-api-key
```

### DynamoDB

No new tables. Uses existing `juntoai-careergraph-users-v2-{env}` table with new fields:
- `identityConsent` (Map): per-service consent records

Linking codes stored as temporary items (5-min TTL) in the same table or a lightweight dedicated table.

### Terraform

New resources in `infra/modules/core/`:
- ALB listener rules for `/careergraph/v1/identity/*` and `/careergraph/v1/link*`
- SSM parameters for service API keys
- No new ECS service, no new DynamoDB table

## Implementation Plan

### Phase 1: REST API + Account Linking (Now)

1. Define Identity Envelope schema (this document)
2. Add `identityConsent` field to CareerGraph DynamoDB user record
3. Build linking flow:
   - `GET /v1/link` — consent page (login + confirm)
   - `POST /v1/identity/link` — code exchange
   - Linking code storage with 5-min TTL
4. Build `GET /v1/identity/:kineticUserId` route with API key auth + consent check
5. Build `DELETE /v1/identity/:kineticUserId/consent` for revocation
6. Build consent management UI in Kinetic settings (view/revoke connected products)
7. Add ALB routing rules via Terraform
8. Create SSM parameters for service API keys
9. Integrate Echo as first consumer:
   - "Connect Kinetic" button in Echo UI
   - Handle linking callback
   - Store `kineticUserId` on Echo user record
   - Fetch + cache Identity Envelope
   - Use envelope to enrich persona and post generation
10. Provide GCP service with API key and integration docs

### Phase 2: Event Notifications (When 3+ Consumers Exist)

1. Add EventBridge event: `CAREER_GRAPH_COMPLETED` with kineticUserId in payload
2. AWS consumers subscribe via SQS → refresh cached envelope
3. GCP consumers subscribe via HTTPS webhook → refresh cached envelope
4. Add EventBridge event: `IDENTITY_CONSENT_REVOKED` for immediate cache invalidation

### Phase 3: Upgrade to Service JWTs (When Key Rotation Becomes Painful)

1. Add token endpoint: `POST /v1/identity/auth/token` (serviceId + serviceSecret → short-lived JWT)
2. Migrate consumers from API key headers to Bearer JWT
3. Deprecate raw API key auth
4. JWT contains `serviceId` claim — consent check uses this instead of key lookup

### Phase 4: Dedicated Identity Service (When Scale Demands)

If the Identity API adds meaningful load to the CareerGraph service, or if the identity data model diverges significantly from the Career Graph:

1. Extract to standalone microservice (new ECS service)
2. Own DynamoDB table for identity data
3. CareerGraph becomes a "writer" via events
4. All consumers read from the Identity Service
5. Consider multi-region deployment for GCP latency optimization

## Cost Impact

### Phase 1

- Zero new infrastructure cost (reuses existing CareerGraph ECS service + ALB)
- SSM parameters: negligible
- API traffic: negligible at current scale (< 1 req/sec expected)

### Phase 2

- EventBridge: $1/million events (negligible)
- SQS: free tier covers expected volume

## Open Questions

1. **Envelope customization**: Should the API support field selection (`?fields=archetype,skills,values`) or always return the full envelope?
2. **Versioning strategy**: URL-based (`/v1/`, `/v2/`) or header-based (`Accept: application/vnd.juntoai.identity.v1+json`)?
3. **GCP latency**: Is 30-50ms cross-cloud latency acceptable for the GCP service's use case, or do we need a regional cache/proxy?
4. **Linking code storage**: Use existing CareerGraph sessions table with a `LINK_CODE#` prefix, or a lightweight dedicated table?
5. **Consent page hosting**: Minimal page on Kinetic frontend (React), or a server-rendered page on the CareerGraph backend (simpler, no frontend dependency)?
