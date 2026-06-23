---
inclusion: manual
---

# JuntoAI A2A — Internal Transcript API

## Purpose
Programmatic access to full negotiation session documents for analysis, scenario optimization, and monitoring. Exposes inner thoughts, agent_calls, evaluations, toggle configs — everything the orchestrator produces.

## Endpoints

### Bulk Export
```
GET /api/v1/internal/transcripts
```

Query params:
- `scenario_id` — filter by scenario (e.g. `talent-war`, `mna-buyout`, `b2b-sales`)
- `deal_status` — filter by outcome: `Agreed`, `Blocked`, `Failed`
- `days` — look-back window (default 30, max 365)
- `limit` — max sessions returned (default 50, max 500)

Response:
```json
{
  "count": 12,
  "filters": { "scenario_id": "talent-war", "deal_status": null, "days": 30, "limit": 50 },
  "sessions": [ /* full session documents */ ]
}
```

### Single Transcript
```
GET /api/v1/internal/transcripts/{session_id}
```

Returns the raw session document directly.

## Authentication

### Local Mode (RUN_MODE=local)
No auth required. Hit `http://localhost:8000/api/v1/internal/transcripts` directly.

### Cloud Mode (RUN_MODE=cloud)
Bearer token required:
```
Authorization: Bearer <INTERNAL_API_KEY>
```

**Production key**: Set as `INTERNAL_API_KEY` env var on the Cloud Run backend service.
Generate with: `openssl rand -hex 32`

**Deployed base URL**: `https://api.juntoai.org/api/v1/internal/transcripts`

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

## Code Reference
- Router: #[[file:backend/app/routers/internal.py]]
- Config: #[[file:backend/app/config.py]]
- Session model: #[[file:backend/app/models/negotiation.py]]
- DB clients: #[[file:backend/app/db/firestore_client.py]], #[[file:backend/app/db/sqlite_client.py]]
