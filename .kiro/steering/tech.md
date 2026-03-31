# JuntoAI A2A MVP — Technology Stack

## Architecture
Monorepo with three top-level directories: `/backend`, `/frontend`, `/infra`.

## Backend
- **Runtime**: Python 3.11+
- **Framework**: FastAPI with Pydantic V2 validation
- **Streaming**: Server-Sent Events (SSE) via `StreamingResponse`
- **AI Orchestration**: LangGraph state machine
- **LLM Provider**: Google Vertex AI Model Garden
  - Buyer agent → Gemini 2.5 Flash
  - Seller agent → Claude 3.5 Sonnet (via Vertex)
  - Regulator agent → Claude Sonnet 4 (via Vertex), fallback Gemini 2.5 Pro
- **Database**: GCP Firestore (Native mode) — sessions, waitlist, token state
- **Hosting**: GCP Cloud Run (containerized, serverless)
- **Dependencies**: `fastapi`, `uvicorn`, `pydantic`, `langgraph`, `langchain-google-vertexai`, `google-cloud-firestore`, `google-cloud-aiplatform`

## Frontend
- **Framework**: Next.js 14+ (App Router)
- **Styling**: Tailwind CSS (utility-first)
- **Icons**: Lucide React
- **Client DB**: Firebase JS SDK (Firestore modular imports)
- **Hosting**: GCP Cloud Run (containerized)
- **Key env vars**: `NEXT_PUBLIC_FIREBASE_API_KEY`, `NEXT_PUBLIC_FIREBASE_PROJECT_ID`, `NEXT_PUBLIC_FIREBASE_APP_ID`, `NEXT_PUBLIC_API_URL`

## Infrastructure
- **IaC**: Terraform + Terragrunt
- **Remote State**: GCS bucket (`juntoai-terraform-state-prod`) with native locking
- **Providers**: `hashicorp/google`, `hashicorp/google-beta`
- **Region**: EU (configurable via variable)
- **GCP Project**: `juntoai-project-id`

## GCP Resources
- Cloud Run (backend + frontend services)
- Artifact Registry (Docker images)
- Firestore (Native mode)
- Vertex AI API
- IAM Service Accounts (Backend_SA, Frontend_SA) with least-privilege roles
- Cloud Build (CI/CD)

## Python Environment
- **Virtual env**: Always use `python -m venv .venv` at the monorepo root
- **Activation**: `source .venv/bin/activate`
- **Install deps**: `pip install -r requirements.txt` (or per-directory requirements files)
- **Infra tests**: `pip install pytest python-hcl2 hypothesis` inside the venv
- When running any Python command (pytest, pip, etc.), ensure the venv is active first

## Key Conventions
- All backend API routes prefixed with `/api/v1`
- Scenario configs are JSON files loaded at runtime from a `SCENARIOS_DIR` directory
- SSE events use `event_type` field: `agent_thought`, `agent_message`, `negotiation_complete`, `error`
- Authentication is email-based waitlist (no OAuth) with 100 tokens/day per email
- All Vertex AI calls use GCP IAM auth — no separate API keys
