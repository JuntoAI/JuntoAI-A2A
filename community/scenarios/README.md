# Community Scenarios

Community-contributed negotiation scenarios for the JuntoAI A2A Battle Arena.

## How to Contribute

1. Fork this repo
2. Create a new `.scenario.json` file in `backend/app/scenarios/data/`
3. Follow the schema below
4. Test locally with `docker compose up`
5. Open a PR — we'll review and merge

## Scenario Schema (Minimal Example)

```json
{
  "id": "your_scenario_id",
  "name": "Your Scenario Name",
  "description": "One-paragraph description of the negotiation.",
  "difficulty": "beginner | intermediate | advanced | fun",
  "category": "Community",
  "agents": [
    {
      "role": "Agent Role Name",
      "name": "Agent First Name",
      "type": "negotiator | regulator | observer",
      "persona_prompt": "Detailed persona and strategy instructions...",
      "goals": ["Goal 1", "Goal 2"],
      "budget": { "min": 0, "max": 100, "target": 50 },
      "tone": "descriptive tone",
      "output_fields": ["offer", "reasoning", "counter_terms"],
      "model_id": "gemini-3-flash-preview"
    }
  ],
  "toggles": [
    {
      "id": "toggle_id",
      "label": "What the user sees in the UI",
      "target_agent_role": "Agent Role Name",
      "hidden_context_payload": {
        "key": "Hidden context injected when toggle is ON"
      }
    }
  ],
  "negotiation_params": {
    "max_turns": 8,
    "agreement_threshold": 5000,
    "turn_order": ["Role A", "Regulator", "Role B", "Regulator"]
  },
  "outcome_receipt": {
    "equivalent_human_time": "~30 minutes",
    "process_label": "Your Negotiation Type"
  }
}
```

## Guidelines

- **2–4 agents** — at least 2 negotiators, optionally a regulator/observer
- **1–2 toggles** — hidden context that changes agent behavior when flipped
- **Realistic personas** — the more specific the persona prompt, the better the negotiation
- **Clear goals with numbers** — agents need concrete targets to negotiate toward
- Use `"category": "Community"` so your scenario groups correctly in the UI

## Available Models

Use any of these in `model_id`:

- `gemini-3-flash-preview` — fast, good for buyers/simpler roles
- `gemini-3.1-flash-lite-preview` — lightweight, good for straightforward roles
- `gemini-3.1-pro-preview` — strongest reasoning

In local mode (Ollama/OpenAI/Anthropic), models are mapped automatically via LiteLLM.

## Ideas for Scenarios

- Startup co-founder equity split
- Landlord-tenant lease renewal
- Open source maintainer vs corporate sponsor
- Wedding budget negotiation
- Band contract negotiation with a venue
- International trade deal (tariffs, quotas)

Build something interesting. We'll feature the best community scenarios in the Arena.
