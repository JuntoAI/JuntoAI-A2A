# ⚔️ Local Battle Arena — Development Guide

Run the full JuntoAI A2A stack on your machine with zero GCP dependencies.

When `RUN_MODE=local` (the default), the entire cloud stack is swapped for lightweight local alternatives:

| Component | Cloud Mode | Local Mode |
|-----------|-----------|------------|
| Database | Firestore | SQLite |
| LLM Router | Vertex AI | LiteLLM |
| Auth | Waitlist + tokens | Bypassed |
| Hosting | GCP Cloud Run | Docker Compose |

---

## Quick Start

Just one command:

```bash
docker compose up
```

That's it. No `.env` file needed, no API keys. It spins up:

- Ollama on `localhost:11434` (auto-pulls `llama3.1`)
- Backend on `localhost:8000`
- Frontend on `localhost:3000`

Open [http://localhost:3000](http://localhost:3000) — you'll land straight on the Arena Selector (no waitlist gate).

First run takes a few minutes since it pulls the Ollama model (~4GB for `llama3.1`). Subsequent runs are instant thanks to the `ollama-data` volume.

**Want a different model?**

```bash
OLLAMA_MODEL=mistral docker compose up
```

**Prefer OpenAI or Anthropic?**

```bash
cp .env.example .env
# Edit .env: set LLM_PROVIDER=openai and add your OPENAI_API_KEY
docker compose up
```

---

## Docker Compose Services

`docker compose up` starts four services:

| Service | Port | Description |
|---------|------|-------------|
| `ollama` | `11434` | Ollama LLM server (auto-starts, persists models) |
| `ollama-pull` | — | Init service that pulls `${OLLAMA_MODEL:-llama3.1}` before backend starts |
| `backend` | `8000` | FastAPI orchestrator, LangGraph agents, SSE streaming |
| `frontend` | `3000` | Next.js Glass Box UI, Arena Selector |

SQLite data and Ollama models are persisted via named Docker volumes (`sqlite-data`, `ollama-data`), so session history and downloaded models survive container restarts.

### Service Dependency Chain

```
ollama (healthy) → ollama-pull (completed) → backend (healthy) → frontend
```

The backend won't start until the model is pulled. The frontend won't start until the backend health check passes.

---

## Model Mapping

Local mode uses [LiteLLM](https://docs.litellm.ai/) to route `model_id` values from scenario configs to your chosen provider. Control the mapping with these environment variables:

| Variable | Purpose | Example |
|----------|---------|---------|
| `LLM_PROVIDER` | Which provider to route to | `openai`, `anthropic`, `ollama` |
| `LLM_MODEL_OVERRIDE` | Force all agents to use one model | `gpt-4o-mini` |
| `MODEL_MAP` | JSON mapping of scenario `model_id` → local model | `{"gemini-2.5-flash": "gpt-4o-mini"}` |
| `OLLAMA_MODEL` | Which Ollama model to pull and use | `llama3.1`, `mistral` |
| `OLLAMA_BASE_URL` | Ollama API endpoint | `http://ollama:11434` (default) |

**Resolution order:**
1. `LLM_MODEL_OVERRIDE` — if set, every agent uses this model
2. `MODEL_MAP` — per-model-id JSON overrides
3. Default mapping — built-in translations per provider
4. Provider default + warning

### Default Model Mappings

| Scenario `model_id` | OpenAI | Anthropic | Ollama |
|---------------------|--------|-----------|--------|
| `gemini-2.5-flash` | `gpt-4o-mini` | `claude-3-5-haiku-20241022` | `ollama/{OLLAMA_MODEL}` |
| `gemini-2.5-pro` | `gpt-4o` | `claude-sonnet-4-20250514` | `ollama/{OLLAMA_MODEL}` |

---

## Scenario Configs Work Everywhere

The same scenario JSON files in `backend/app/scenarios/data/` work in both cloud and local modes without modification. The orchestrator reads the scenario config identically — only the underlying LLM provider and database change based on `RUN_MODE`.

---

## Environment Variables (Local Mode)

All variables have sensible defaults for zero-config Ollama operation. Copy `.env.example` only if you need to override something.

| Variable | Default | Description |
|----------|---------|-------------|
| `RUN_MODE` | `local` | `local` or `cloud` |
| `LLM_PROVIDER` | `ollama` | `ollama`, `openai`, `anthropic` |
| `OLLAMA_MODEL` | `llama3.1` | Model to pull and use |
| `OLLAMA_BASE_URL` | `http://ollama:11434` | Ollama API endpoint |
| `SQLITE_DB_PATH` | `data/juntoai.db` | SQLite file path |
| `LLM_MODEL_OVERRIDE` | _(empty)_ | Force single model for all agents |
| `MODEL_MAP` | _(empty)_ | JSON per-model-id overrides |
| `OPENAI_API_KEY` | — | Required when `LLM_PROVIDER=openai` |
| `ANTHROPIC_API_KEY` | — | Required when `LLM_PROVIDER=anthropic` |

---

## LiteLLM Provider-Agnostic Routing

LiteLLM supports 100+ providers (OpenAI, Anthropic, Ollama, Azure, Bedrock, Mistral, and more) through a single interface. To use any LiteLLM-supported provider:

```bash
# Mistral
LLM_PROVIDER=mistral
MISTRAL_API_KEY=your-mistral-key

# Azure OpenAI
LLM_PROVIDER=azure
AZURE_API_KEY=your-azure-key
AZURE_API_BASE=https://your-resource.openai.azure.com/
```

Your scenario configs stay unchanged — LiteLLM handles provider-specific API formatting, auth, and model routing.

---

## Auth Bypass

In local mode, the waitlist email gate and 100-token-per-day limit are completely bypassed:
- No email required to start a negotiation
- Token counter shows "Unlimited"
- Landing page redirects straight to the Arena Selector

Cloud mode (`RUN_MODE=cloud`) enforces the full auth flow unchanged.
