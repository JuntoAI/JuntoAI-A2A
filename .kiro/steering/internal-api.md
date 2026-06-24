---
inclusion: manual
---

# JuntoAI A2A — Transcript Access for Analysis

## Preferred Method: Firestore REST API

Transcripts are stored in Firestore (`negotiation_sessions` collection, project `juntoai-a2a-mvp`). Access directly via the Firestore REST API using gcloud credentials. No API keys, no proxy — just a gcloud access token.

**Base URL**: `https://firestore.googleapis.com/v1/projects/juntoai-a2a-mvp/databases/(default)/documents`

### Get latest session(s)
```powershell
$token = gcloud auth print-access-token
$headers = @{ "Authorization" = "Bearer $token"; "Content-Type" = "application/json" }
$body = '{"structuredQuery":{"from":[{"collectionId":"negotiation_sessions"}],"orderBy":[{"field":{"fieldPath":"created_at"},"direction":"DESCENDING"}],"limit":5}}'
$uri = "https://firestore.googleapis.com/v1/projects/juntoai-a2a-mvp/databases/(default)/documents:runQuery"
Invoke-RestMethod -Uri $uri -Headers $headers -Method POST -Body $body
```

### Get specific session by ID
```
GET https://firestore.googleapis.com/v1/projects/juntoai-a2a-mvp/databases/(default)/documents/negotiation_sessions/{session_id}
Authorization: Bearer <gcloud-access-token>
```

### Filter by scenario_id
```json
{
  "structuredQuery": {
    "from": [{"collectionId": "negotiation_sessions"}],
    "where": {
      "fieldFilter": {
        "field": {"fieldPath": "scenario_id"},
        "op": "EQUAL",
        "value": {"stringValue": "ma_buyout"}
      }
    },
    "orderBy": [{"field": {"fieldPath": "created_at"}, "direction": "DESCENDING"}],
    "limit": 10
  }
}
```

### Filter by deal_status
```json
{
  "structuredQuery": {
    "from": [{"collectionId": "negotiation_sessions"}],
    "where": {
      "fieldFilter": {
        "field": {"fieldPath": "deal_status"},
        "op": "EQUAL",
        "value": {"stringValue": "Failed"}
      }
    },
    "limit": 20
  }
}
```

### Filter by owner_email
```json
{
  "structuredQuery": {
    "from": [{"collectionId": "negotiation_sessions"}],
    "where": {
      "fieldFilter": {
        "field": {"fieldPath": "owner_email"},
        "op": "EQUAL",
        "value": {"stringValue": "markus@juntoai.org"}
      }
    },
    "orderBy": [{"field": {"fieldPath": "created_at"}, "direction": "DESCENDING"}],
    "limit": 10
  }
}
```

### Firestore response format
Firestore REST returns typed fields. Key mappings:
- `stringValue` → string fields (session_id, scenario_id, deal_status, etc.)
- `integerValue` → number fields (turn_count, total_tokens_used, etc.)
- `doubleValue` → float fields (current_offer, agreement_threshold)
- `booleanValue` → boolean fields
- `arrayValue.values` → arrays (history, agent_calls, active_toggles)
- `mapValue.fields` → nested objects (content, agent_states, evaluation)

## Session Document Structure

Each session doc contains:
- `session_id`, `scenario_id`, `owner_email`
- `deal_status` — Agreed | Blocked | Failed | Negotiating
- `turn_count`, `max_turns`, `current_offer`, `warning_count`
- `active_toggles` — which scenario toggles were enabled
- `history` — full transcript array:
  ```json
  [
    {
      "role": "Buyer",
      "name": "Alice",
      "agent_type": "negotiator",
      "turn_number": 1,
      "content": {
        "inner_thought": "I should start low...",
        "public_message": "I propose $500,000.",
        "proposed_price": 500000.0
      }
    },
    {
      "role": "Regulator",
      "agent_type": "regulator",
      "turn_number": 1,
      "content": {
        "reasoning": "Offer within range.",
        "public_message": "No issues noted.",
        "status": "CLEAR"
      }
    }
  ]
  ```
- `agent_calls` — per-LLM-call metrics:
  ```json
  [{ "model_id": "gemini-2.5-flash", "input_tokens": 1200, "output_tokens": 340, "latency_ms": 2100 }]
  ```
- `agent_states` — final state per agent (role, name, type, persona)
- `evaluation` — post-negotiation evaluation report with dimension scores
- `participant_summaries` — AI-generated 1-2 sentence summaries per agent
- `tipping_point` — the turn that most shifted the outcome
- `scenario_config` — full scenario JSON used for this session
- `created_at`, `completed_at`, `duration_seconds`
- `total_tokens_used`, `model_overrides`, `custom_prompts`

## Analysis Use Cases
1. **Toggle effectiveness**: Compare outcomes across sessions with different `active_toggles` for the same scenario
2. **Prompt quality**: Review `inner_thought` to assess if agents reason coherently
3. **Convergence patterns**: Track `proposed_price` across turns in history
4. **Model performance**: Aggregate `agent_calls` latency and token usage by model_id
5. **Failure modes**: Filter `deal_status=Failed` and examine final turns for stall patterns
6. **Regulator behavior**: Filter history entries with `agent_type=regulator` and check warning escalation

## Fallback: HTTP API Endpoint

An HTTP API also exists at `/api/v1/internal/transcripts` (bearer token auth in cloud, no auth locally). Use this only for external automation — the Firestore REST approach above is simpler and more reliable for Kiro analysis sessions.

- Local: `http://localhost:8000/api/v1/internal/transcripts`
- Cloud: requires `Authorization: Bearer <INTERNAL_API_KEY>` header
- Key stored in GCP Secret Manager as `internal-api-key`

## Code Reference
- Internal API router: #[[file:backend/app/routers/internal.py]]
- Config: #[[file:backend/app/config.py]]
- Session model: #[[file:backend/app/models/negotiation.py]]
- DB clients: #[[file:backend/app/db/firestore_client.py]], #[[file:backend/app/db/sqlite_client.py]]
