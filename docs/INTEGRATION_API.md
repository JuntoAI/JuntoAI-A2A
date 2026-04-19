# CRM Integration API — Setup & Usage

## Overview

The Integration API allows external CRM systems (EspoCRM, HubSpot, Salesforce) to trigger AI negotiation simulations, poll for results, and receive webhook callbacks.

**Base URL:** `https://api.juntoai.org/api/v1/integrations`  
**Local:** `http://localhost:8000/api/v1/integrations`

## Authentication Model

Every request requires two headers:

| Header | Description |
|--------|-------------|
| `X-Integration-Token` | Org token (one per customer, created by JuntoAI) |
| `X-User-Email` | Email of the CRM user triggering the request |

The email's domain must match the org's registered domain. For example, if the org is registered with domain `acme.com`, only emails like `user@acme.com` are accepted.

## Provisioning a New Customer

When a new customer signs a contract, you create their org token using the CLI script:

```bash
# From the repo root, with the venv active:
python scripts/create_integration_org.py \
    --org-name "Acme Corp" \
    --domain "acme.com" \
    --email "admin@juntoai.org" \
    --rate-limit-daily 500
```

### Parameters

| Flag | Required | Description |
|------|----------|-------------|
| `--org-name` | Yes | Customer organization name |
| `--domain` | Yes | Email domain for this org (e.g., `acme.com`). Only users with `@acme.com` emails can use the token. |
| `--email` | Yes | Your admin email (audit trail) |
| `--rate-limit-daily` | No | Daily simulation limit (default: 100 cloud / 1000 local) |
| `--rate-limit-per-minute` | No | Per-minute request limit (default: 10) |

### Output

The script prints the token once:

```
============================================================
  Integration Org Created Successfully
============================================================

  Org Name:        Acme Corp
  Domain:          acme.com
  Key ID:          a1b2c3d4-...
  Daily Limit:     500
  Per-Min Limit:   10
  Created At:      2026-04-19T10:30:00+00:00

  Integration Token:
  a2a_live_AbCdEfGh...

  ⚠️  Save this token now. It will NOT be shown again.

  CRM Admin Configuration:
  - API URL:   https://api.juntoai.org/api/v1/integrations
  - Token:     (the token above)
  - Users must have @acme.com email addresses
============================================================
```

### What to Send the CRM Admin

Send them:
1. The **Integration Token** (`a2a_live_...`)
2. The **API URL** (`https://api.juntoai.org/api/v1/integrations`)
3. Note that their users must use their `@acme.com` email addresses

They paste these into the EspoCRM A2A extension settings panel.

## Rate Limiting

- Rate limits are **per-org**, not per-user
- Integration API usage does **not** consume the user's web app tokens (separate quota)
- All successful responses include rate limit headers:
  - `X-RateLimit-Limit` — daily limit
  - `X-RateLimit-Remaining` — remaining today
  - `X-RateLimit-Reset` — UTC midnight reset time (ISO 8601)

## Endpoints

### Health Check

```
GET /integrations/health
```

Validates the token and returns rate limit status.

### List Scenarios

```
GET /integrations/scenarios
```

Returns available negotiation scenarios with their toggles and context fields.

### Trigger Simulation

```
POST /integrations/simulate
Content-Type: application/json

{
  "scenario_id": "talent_war",
  "active_toggles": ["competing_offer"],
  "context": {
    "contact_name": "Jane Smith",
    "company": "TechCo",
    "deal_value": 150000,
    "pain_points": ["slow onboarding", "high churn"]
  },
  "callback_url": "https://crm.acme.com/webhooks/a2a"
}
```

Returns `201` with `session_id`, `viewer_url`, and `status: "running"`.

The `triggered_by` field is automatically set from the `X-User-Email` header — the session appears in that user's A2A history when they log into the web app.

### Poll Session Status

```
GET /integrations/sessions/{session_id}
```

Returns session status, turns completed, and outcome (when finished).

## Webhook Callbacks

If `callback_url` is provided in the simulate request, the API sends an HMAC-SHA256 signed POST when the simulation completes:

```
POST {callback_url}
X-A2A-Signature: sha256=<hex digest>
Content-Type: application/json

{
  "event": "simulation.completed",
  "session_id": "...",
  "scenario_id": "talent_war",
  "status": "completed",
  "outcome": {
    "deal_status": "Agreed",
    "summary": "Deal agreed at $125,000.00",
    "final_offer": 125000,
    "turns_completed": 6
  },
  "viewer_url": "https://app.juntoai.org/share/...",
  "timestamp": "2026-04-19T10:35:00+00:00"
}
```

The signature uses the org token as the HMAC secret. Verify it server-side to confirm the callback is authentic.

## Error Responses

All errors follow a consistent format:

```json
{
  "error": "error_code",
  "message": "Human-readable description",
  "details": {}
}
```

| Code | HTTP | Meaning |
|------|------|---------|
| `invalid_token` | 401 | Token not found |
| `invalid_email` | 401 | Bad email format |
| `org_deactivated` | 403 | Org access revoked |
| `domain_mismatch` | 403 | Email domain doesn't match org |
| `rate_limit_exceeded` | 429 | Daily or per-minute limit hit |
| `scenario_not_found` | 404 | Unknown scenario_id |
| `session_not_found` | 404 | Unknown session_id |
| `validation_error` | 422 | Bad request body |
| `simulation_failed` | 500 | Internal error |

## Deactivating an Org

To revoke access (e.g., contract ended):

```python
import asyncio
from app.db import get_api_key_store
from app.services.api_key_service import ApiKeyService

async def deactivate():
    store = get_api_key_store()
    service = ApiKeyService(store)
    await service.deactivate_key("<key_id>")

asyncio.run(deactivate())
```

The token stops working immediately. The record is preserved for audit.
