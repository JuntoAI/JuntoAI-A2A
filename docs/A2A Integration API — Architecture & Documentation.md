# A2A Integration API — Architecture & Documentation

> **Purpose**: Defines the Integration API layer that sits on top of the existing A2A engine, enabling external systems (CRM plugins, partner platforms, custom integrations) to trigger and monitor simulations programmatically.
>
> **Audience**: Backend developers implementing the API, and integration developers consuming it.

---

## 1. Architecture Overview

```
External Systems                    A2A Backend
┌──────────────┐                   ┌─────────────────────────────────────┐
│ EspoCRM      │                   │                                     │
│ HubSpot      │  HTTPS + API Key  │  ┌─────────────────────────────┐   │
│ Salesforce   │──────────────────►│  │  Integration API Router     │   │
│ Custom Apps  │                   │  │  /api/v1/integrations/*     │   │
└──────────────┘                   │  └──────────┬──────────────────┘   │
                                   │             │                       │
                                   │  ┌──────────▼──────────────────┐   │
                                   │  │  Integration Service        │   │
                                   │  │  - API key validation       │   │
                                   │  │  - Context mapping          │   │
                                   │  │  - Rate limiting            │   │
                                   │  └──────────┬──────────────────┘   │
                                   │             │                       │
                                   │  ┌──────────▼──────────────────┐   │
                                   │  │  Existing A2A Core          │   │
                                   │  │  - Scenario Registry        │   │
                                   │  │  - Negotiation Orchestrator │   │
                                   │  │  - Session Store            │   │
                                   │  │  - Share Service            │   │
                                   │  └─────────────────────────────┘   │
                                   └─────────────────────────────────────┘
```

**Key principle**: The Integration API is a thin wrapper. It does NOT duplicate any core engine logic. It translates external requests into the same internal calls that the frontend uses, adds API key auth, and returns structured results.

---

## 2. Authentication — API Keys

### 2.1 Key Format

```
a2a_live_<32 random bytes, base64url encoded>
```

Example: `a2a_live_k7Bx9mPqR2sT4vW6yA1cD3eF5gH7jK9L`

- Prefix `a2a_live_` makes keys identifiable in logs and config files
- 32 bytes of randomness = 256 bits of entropy
- Base64url encoding (no `+`, `/`, or `=`) for safe use in headers

### 2.2 Key Storage

Keys are stored in Firestore (cloud) or SQLite (local):

```
Collection: integration_api_keys
Document ID: key_id (auto-generated)

{
  "key_id": "intg_abc123def456",
  "key_hash": "sha256:<hex digest>",
  "key_prefix": "a2a_live_k7Bx",          // First 4 chars after prefix, for identification
  "org_name": "Acme Corp",
  "created_by_email": "admin@acme.com",
  "scopes": ["simulate", "read_sessions", "list_scenarios"],
  "rate_limit_daily": 100,
  "rate_limit_per_minute": 10,
  "active": true,
  "created_at": "2026-04-19T10:00:00Z",
  "last_used_at": "2026-04-19T14:30:00Z",
  "usage_today": 7
}
```

**Security rules:**
- Only the SHA-256 hash is stored — the raw key is shown once at creation and never again
- `key_prefix` stores the first 4 chars after `a2a_live_` for admin identification in dashboards
- Keys can be deactivated (`active: false`) without deletion for audit trail

### 2.3 Key Validation Flow

```
Request arrives with header: X-API-Key: a2a_live_k7Bx9mPq...
    │
    ▼
Compute SHA-256 of the full key value
    │
    ▼
Query integration_api_keys where key_hash == computed hash
    │
    ├── No match → 401 Unauthorized
    │
    ├── Match found, active == false → 403 Forbidden ("API key deactivated")
    │
    ├── Match found, usage_today >= rate_limit_daily → 429 Too Many Requests
    │
    └── Match found, active, within limits → ✅ Proceed
        │
        ▼
    Update last_used_at and increment usage_today
```

### 2.4 Scopes

| Scope | Grants Access To |
|---|---|
| `simulate` | `POST /integrations/simulate` |
| `read_sessions` | `GET /integrations/sessions/{id}` |
| `list_scenarios` | `GET /integrations/scenarios` |
| `manage_keys` | `POST/DELETE /integrations/keys` (admin only) |

Default key creation grants: `simulate`, `read_sessions`, `list_scenarios`.

---

## 3. API Endpoints

All endpoints are prefixed with `/api/v1/integrations`.

### 3.1 Health Check

```
GET /api/v1/integrations/health
Headers: X-API-Key: a2a_live_...

Response 200:
{
  "status": "ok",
  "version": "0.1.0",
  "key_valid": true,
  "org_name": "Acme Corp",
  "rate_limit": {
    "daily_limit": 100,
    "used_today": 7,
    "remaining": 93,
    "resets_at": "2026-04-20T00:00:00Z"
  }
}
```

### 3.2 List Scenarios

```
GET /api/v1/integrations/scenarios
Headers: X-API-Key: a2a_live_...

Response 200:
{
  "scenarios": [
    {
      "id": "talent_war",
      "name": "The Talent War",
      "description": "HR salary and remote work negotiation",
      "category": "Corporate",
      "difficulty": "intermediate",
      "agents": [
        {
          "role": "recruiter",
          "name": "Sarah",
          "type": "negotiator"
        },
        {
          "role": "candidate",
          "name": "Alex",
          "type": "negotiator"
        },
        {
          "role": "hr_compliance",
          "name": "HR Compliance Bot",
          "type": "regulator"
        }
      ],
      "toggles": [
        {
          "id": "competing_offer",
          "label": "Give Alex a competing offer from Google",
          "target_agent_role": "candidate"
        },
        {
          "id": "deadline_pressure",
          "label": "Make Sarah desperate — 24h deadline",
          "target_agent_role": "recruiter"
        }
      ],
      "context_fields": {
        "required": [],
        "optional": ["contact_name", "company", "role", "industry", "deal_value"]
      }
    }
  ]
}
```

**Notes:**
- `context_fields` tells the CRM plugin which fields to auto-fill
- `toggles` are returned so the CRM plugin can render toggle checkboxes
- Agent `model_id` and `persona_prompt` are NOT exposed (internal implementation detail)

### 3.3 Create Simulation

```
POST /api/v1/integrations/simulate
Headers:
  X-API-Key: a2a_live_...
  Content-Type: application/json

Body:
{
  "scenario_id": "talent_war",
  "active_toggles": ["competing_offer"],
  "context": {
    "contact_name": "Jane Smith",
    "company": "Acme Corp",
    "role": "CTO",
    "industry": "Fintech",
    "deal_value": 500000,
    "custom_fields": {
      "funding_stage": "Series B",
      "team_size": 50
    }
  },
  "callback_url": "https://your-crm.com/api/v1/a2a-webhook"
}

Response 201:
{
  "session_id": "a1b2c3d4e5f6",
  "status": "running",
  "viewer_url": "https://app.juntoai.org/share/Xk9mP2qR",
  "estimated_duration_seconds": 120,
  "created_at": "2026-04-19T14:30:00Z"
}
```

**What happens internally:**
1. Validate API key and check rate limits
2. Look up scenario in ScenarioRegistry
3. Inject `context` fields into agent persona prompts as additional context
4. Create session via existing `create_initial_state` flow
5. Start negotiation asynchronously (background task)
6. Create a share record immediately (for the `viewer_url`)
7. Return session reference

**Context injection**: The `context` object is merged into each agent's system prompt as structured context. For example, if `contact_name` is "Jane Smith", each agent's prompt gets prepended with:

```
[Integration Context]
Contact: Jane Smith
Company: Acme Corp
Role: CTO
Industry: Fintech
Deal Value: $500,000
```

This influences agent behavior without modifying the scenario config.

### 3.4 Get Session Status

```
GET /api/v1/integrations/sessions/{session_id}
Headers: X-API-Key: a2a_live_...

Response 200 (running):
{
  "session_id": "a1b2c3d4e5f6",
  "scenario_id": "talent_war",
  "scenario_name": "The Talent War",
  "status": "running",
  "viewer_url": "https://app.juntoai.org/share/Xk9mP2qR",
  "turns_completed": 3,
  "current_offer": 125000,
  "created_at": "2026-04-19T14:30:00Z"
}

Response 200 (completed):
{
  "session_id": "a1b2c3d4e5f6",
  "scenario_id": "talent_war",
  "scenario_name": "The Talent War",
  "status": "completed",
  "viewer_url": "https://app.juntoai.org/share/Xk9mP2qR",
  "outcome": {
    "deal_status": "Agreed",
    "summary": "Deal reached — €125,000 base salary with 3 days remote work per week.",
    "final_offer": 125000,
    "turns_completed": 6,
    "warning_count": 1,
    "duration_seconds": 87,
    "participant_summaries": [
      {
        "role": "recruiter",
        "name": "Sarah",
        "agent_type": "negotiator",
        "summary": "Ended at €125,000. Conceded on remote work after deadline pressure."
      },
      {
        "role": "candidate",
        "name": "Alex",
        "agent_type": "negotiator",
        "summary": "Ended at €125,000. Leveraged competing offer to secure remote work."
      },
      {
        "role": "hr_compliance",
        "name": "HR Compliance Bot",
        "agent_type": "regulator",
        "summary": "Issued 1 warning about unauthorized stock option promises."
      }
    ],
    "evaluation_scores": {
      "fairness": 8,
      "mutual_respect": 7,
      "value_creation": 9,
      "satisfaction": 8,
      "overall_score": 8
    }
  },
  "created_at": "2026-04-19T14:30:00Z",
  "completed_at": "2026-04-19T14:31:27Z"
}
```

### 3.5 Webhook Callback (A2A → CRM)

When a simulation completes and `callback_url` was provided:

```
POST {callback_url}
Headers:
  Content-Type: application/json
  X-A2A-Signature: sha256=<HMAC of body using API key as secret>

Body:
{
  "event": "simulation.completed",
  "session_id": "a1b2c3d4e5f6",
  "scenario_id": "talent_war",
  "status": "completed",
  "outcome": {
    "deal_status": "Agreed",
    "summary": "Deal reached — €125,000 base salary with 3 days remote work.",
    "final_offer": 125000,
    "turns_completed": 6
  },
  "viewer_url": "https://app.juntoai.org/share/Xk9mP2qR",
  "timestamp": "2026-04-19T14:31:27Z"
}
```

**Webhook security:**
- Body is signed with HMAC-SHA256 using the API key as the secret
- CRM plugin verifies signature before processing
- A2A retries failed deliveries 3 times with exponential backoff (5s, 30s, 120s)

### 3.6 API Key Management

```
POST /api/v1/integrations/keys
Headers: X-API-Key: a2a_live_... (must have manage_keys scope)
Body:
{
  "org_name": "Acme Corp",
  "scopes": ["simulate", "read_sessions", "list_scenarios"],
  "rate_limit_daily": 100
}

Response 201:
{
  "key_id": "intg_abc123def456",
  "api_key": "a2a_live_k7Bx9mPqR2sT4vW6yA1cD3eF5gH7jK9L",
  "org_name": "Acme Corp",
  "scopes": ["simulate", "read_sessions", "list_scenarios"],
  "rate_limit_daily": 100,
  "created_at": "2026-04-19T10:00:00Z",
  "warning": "Save this API key now. It will not be shown again."
}
```

```
DELETE /api/v1/integrations/keys/{key_id}
Headers: X-API-Key: a2a_live_... (must have manage_keys scope)

Response 200:
{
  "key_id": "intg_abc123def456",
  "status": "deactivated"
}
```

**Note:** DELETE does not remove the key — it sets `active: false`. This preserves the audit trail.

---

## 4. Data Flow — End to End

```
CRM User clicks "Run Investor Pitch" on Contact "Jane Smith"
    │
    ▼
CRM Plugin: Opens scenario picker modal
CRM Plugin: Fetches GET /integrations/scenarios
CRM Plugin: Auto-fills context from Contact fields
    │
    ▼
CRM Plugin: User clicks "Start Simulation"
CRM Plugin: POST /integrations/simulate
    │         {scenario_id, active_toggles, context, callback_url}
    ▼
A2A Integration Service:
    1. Validate API key → ✅
    2. Check rate limit → ✅ (8/100 today)
    3. Load scenario from registry → ✅
    4. Inject context into agent prompts
    5. Create session (same as frontend flow)
    6. Start negotiation in background task
    7. Create share record → viewer_url
    8. Return {session_id, viewer_url, status: "running"}
    │
    ▼
CRM Plugin: Creates A2ASimulation record on Contact
CRM Plugin: Shows "Running..." status with [View Live] link
    │
    ▼
A2A: Negotiation runs (60-180 seconds)
A2A: Agents negotiate, regulator monitors
A2A: Session completes → deal_status set
    │
    ├── If callback_url provided:
    │   A2A: POST webhook to CRM with outcome
    │   CRM: Updates simulation record
    │
    └── If no callback_url:
        CRM: Polls GET /integrations/sessions/{id} every 10s
        CRM: Detects status: "completed"
        CRM: Updates simulation record with outcome
    │
    ▼
CRM Plugin: Shows "Completed — Agreed" with [View Results] link
User: Clicks link → Opens Glass Box viewer in new tab
```

---

## 5. Rate Limiting

### 5.1 Limits

| Limit Type | Default | Configurable |
|---|---|---|
| Daily simulations per key | 100 | Yes, per key |
| Requests per minute per key | 10 | Yes, per key |
| Concurrent simulations per key | 5 | Yes, per key |

### 5.2 Rate Limit Headers

All responses include:

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 93
X-RateLimit-Reset: 2026-04-20T00:00:00Z
```

### 5.3 429 Response

```json
{
  "error": "rate_limit_exceeded",
  "message": "Daily simulation limit reached. Resets at midnight UTC.",
  "retry_after_seconds": 34200,
  "limit": 100,
  "used": 100
}
```

---

## 6. Error Responses

All errors follow a consistent format:

```json
{
  "error": "error_code",
  "message": "Human-readable description",
  "details": {}
}
```

| Status | Error Code | When |
|---|---|---|
| 401 | `invalid_api_key` | Missing or invalid X-API-Key header |
| 403 | `key_deactivated` | API key exists but is deactivated |
| 403 | `insufficient_scope` | Key lacks required scope for this endpoint |
| 404 | `scenario_not_found` | Requested scenario_id doesn't exist |
| 404 | `session_not_found` | Requested session_id doesn't exist |
| 422 | `validation_error` | Request body fails Pydantic validation |
| 429 | `rate_limit_exceeded` | Daily or per-minute limit hit |
| 500 | `simulation_failed` | Internal error during simulation creation |
| 503 | `service_unavailable` | A2A engine temporarily unavailable |

---

## 7. Implementation Plan — What Needs to Be Built

### 7.1 New Files (Backend)

| File | Purpose |
|---|---|
| `backend/app/routers/integrations.py` | FastAPI router for all `/integrations/*` endpoints |
| `backend/app/services/integration_service.py` | Business logic: key validation, context injection, simulation orchestration |
| `backend/app/services/api_key_service.py` | API key generation, hashing, validation, rate limiting |
| `backend/app/models/integrations.py` | Pydantic V2 models for request/response schemas |
| `backend/app/db/api_key_store.py` | API key persistence (Firestore + SQLite implementations) |
| `backend/app/middleware/api_key_auth.py` | FastAPI dependency for API key authentication |

### 7.2 Modified Files (Backend)

| File | Change |
|---|---|
| `backend/app/main.py` | Register integrations router |
| `backend/app/db/__init__.py` | Add `get_api_key_store()` factory |
| `backend/app/db/base.py` | Add `ApiKeyStore` protocol |
| `backend/app/config.py` | Add integration-related settings (webhook retry config, etc.) |

### 7.3 No Changes Required

- Scenario registry, loader, models — used as-is
- Negotiation orchestrator — called as-is
- Share service — used to generate viewer URLs
- Session store — used as-is for session persistence
- Frontend — no changes (Glass Box viewer already works via share URLs)

---

## 8. Context Injection — How CRM Data Influences Agents

The `context` object from the simulate request is NOT stored in the scenario config. Instead, it's injected as a preamble to each agent's system prompt at runtime.

### 8.1 Injection Format

```python
def build_context_preamble(context: dict) -> str:
    """Build a structured context block for agent prompts."""
    lines = ["[Integration Context — Real CRM Data]"]
    
    field_map = {
        "contact_name": "Contact",
        "company": "Company",
        "role": "Role/Title",
        "industry": "Industry",
        "deal_value": "Deal Value",
        "deal_stage": "Deal Stage",
        "pain_points": "Known Pain Points",
        "competing_vendors": "Competing Vendors",
        "budget_approved": "Budget Approved",
    }
    
    for key, label in field_map.items():
        if key in context and context[key]:
            value = context[key]
            if isinstance(value, list):
                value = ", ".join(str(v) for v in value)
            elif isinstance(value, bool):
                value = "Yes" if value else "No"
            elif isinstance(value, (int, float)):
                value = f"${value:,.0f}" if key == "deal_value" else str(value)
            lines.append(f"  {label}: {value}")
    
    # Custom fields
    custom = context.get("custom_fields", {})
    for key, value in custom.items():
        label = key.replace("_", " ").title()
        lines.append(f"  {label}: {value}")
    
    lines.append("")
    lines.append("Use this context to inform your negotiation strategy.")
    lines.append("Adapt your arguments and proposals based on this real data.")
    
    return "\n".join(lines)
```

### 8.2 Where It's Injected

The context preamble is prepended to each agent's `persona_prompt` before the negotiation starts. This happens in the integration service layer, before calling `create_initial_state`.

---

## 9. Async Simulation Execution

Simulations are long-running (60-180 seconds). The API must not block.

### 9.1 Background Task Pattern

```python
from fastapi import BackgroundTasks

@router.post("/simulate")
async def create_simulation(
    body: SimulateRequest,
    background_tasks: BackgroundTasks,
    api_key: ApiKeyDoc = Depends(validate_api_key),
):
    # 1. Create session synchronously
    session_id = create_session(...)
    
    # 2. Create share record synchronously (for viewer_url)
    share = create_share(...)
    
    # 3. Start negotiation in background
    background_tasks.add_task(
        run_integration_negotiation,
        session_id=session_id,
        callback_url=body.callback_url,
        api_key_id=api_key.key_id,
    )
    
    # 4. Return immediately
    return SimulateResponse(
        session_id=session_id,
        status="running",
        viewer_url=share.share_url,
    )
```

### 9.2 Webhook Delivery

After simulation completes, if `callback_url` was provided:

```python
async def deliver_webhook(callback_url: str, payload: dict, api_key: str):
    """Deliver webhook with HMAC signature and retry logic."""
    body = json.dumps(payload)
    signature = hmac.new(api_key.encode(), body.encode(), hashlib.sha256).hexdigest()
    
    headers = {
        "Content-Type": "application/json",
        "X-A2A-Signature": f"sha256={signature}",
    }
    
    delays = [5, 30, 120]  # Retry delays in seconds
    for attempt, delay in enumerate(delays):
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(callback_url, content=body, headers=headers, timeout=10)
                if resp.status_code < 400:
                    return  # Success
        except Exception:
            pass
        await asyncio.sleep(delay)
    
    logger.error("Webhook delivery failed after 3 retries: %s", callback_url)
```

---

## 10. Local Mode Support

The Integration API works in both cloud and local modes:

| Aspect | Cloud Mode | Local Mode |
|---|---|---|
| API key storage | Firestore | SQLite |
| Rate limiting | Enforced | Relaxed (1000/day default) |
| Webhook delivery | Full retry logic | Best-effort, single attempt |
| Share URLs | `https://app.juntoai.org/share/...` | `http://localhost:3000/share/...` |
| Key management | Admin API + dashboard | Admin API only |

---

## 11. Security Considerations

1. **API keys are secrets** — transmitted only over HTTPS, stored as SHA-256 hashes
2. **No session data leakage** — integration API returns only public-facing data (same as share payloads)
3. **Webhook signatures** — HMAC-SHA256 prevents spoofed callbacks
4. **Rate limiting** — prevents abuse and controls LLM API costs
5. **Scope-based access** — keys can be restricted to read-only or simulate-only
6. **Audit trail** — all key usage is logged with timestamps
7. **Key rotation** — deactivate old key, create new one (no downtime needed)
