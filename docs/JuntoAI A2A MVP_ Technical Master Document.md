# **TECHNICAL SPECIFICATION: JuntoAI A2A MVP (V1)**

**Project Code:** "The M\&A War Room"

**Target Cloud Environment:** Google Cloud Platform (GCP)

**Infrastructure as Code (IaC):** Terraform & Terragrunt

## **1\. Project Overview & Architecture**

The objective is to build a standalone, fully functional V1 MVP demonstrating the JuntoAI Agent-to-Agent (A2A) negotiation protocol. The application simulates a high-stakes Mergers & Acquisitions negotiation between three autonomous AI agents (Buyer, Seller, Regulator) with a real-time UI showing both public dialogue and private "inner thoughts."

**Core Technology Stack:**

* **Frontend:** Next.js 14+ (App Router), React, Tailwind CSS, Lucide React.  
* **Frontend Hosting:** GCP Cloud Run (Containerized, Serverless).  
* **Backend API:** Python 3.11+, FastAPI (using Server-Sent Events/SSE for streaming).  
* **Backend Compute:** GCP Cloud Run (Containerized, Serverless).  
* **AI Orchestration:** LangGraph state machine.  
* **LLM Provider:** Google Vertex AI (Model Garden).  
* **State & Database:** GCP Firestore (Native mode) — sessions, waitlist, token state.  
* **IaC:** HashiCorp Terraform \+ Terragrunt.

## **2\. Infrastructure as Code (Terragrunt on GCP)**

The infrastructure will be provisioned using Terragrunt to maintain DRY (Don't Repeat Yourself) Terraform configurations.

### **2.1. Provider & State Management**

* **Provider:** Official hashicorp/google and hashicorp/google-beta providers.  
* **Remote State:** Google Cloud Storage (GCS). Unlike AWS S3 \+ DynamoDB, GCS natively supports state locking.  
* **Authentication:** GCP Service Accounts securely managed via Google Secret Manager and CI/CD (Google Cloud Build).

**Example terragrunt.hcl Remote State Block:**

remote\_state {  
  backend \= "gcs"  
  config \= {  
    bucket  \= local.env\_vars.terraform\_state\_bucket  
    prefix  \= "${path\_relative\_to\_include()}/terraform.tfstate"  
    project \= local.env\_vars.gcp\_project\_id  
    location \= local.env\_vars.gcp\_region  
  }  
}

*All environment-specific values (`gcp_project_id`, `terraform_state_bucket`, `gcp_region`) are defined in a single `env.hcl` file at the `/infra` level. Default values: project `juntoai-project-id`, bucket `juntoai-terraform-state-prod`, region `eu`.*

### **2.2. Core GCP Resources to Provision**

1. **Cloud Run Services:** One for the Python FastAPI backend, one for the Next.js frontend.  
2. **Artifact Registry:** Repositories for Docker images.  
3. **Firestore:** Native mode database for state management.  
4. **Vertex AI API Enablers:** Enabling the Vertex AI API for the project.  
5. **IAM Service Accounts:** Strict least-privilege roles for Cloud Run to access Vertex AI and Firestore.

## **3\. AI Orchestration & LLM Heterogeneity (Vertex AI)**

To prove protocol agnosticism and "LLM Heterogeneity" to investors, the orchestration layer will route to different foundational models hosted natively within **Vertex AI Model Garden**.

* **Agent 1 (The Buyer):** Powered by **Google Gemini 2.5 Flash** (Fast, logical, cost-effective).  
* **Agent 2 (The Seller):** Powered by **Anthropic Claude 3.5 Sonnet** via Vertex AI (Empathetic, nuanced negotiation).  
* **Agent 3 (The Regulator):** Powered by **Anthropic Claude Sonnet 4** via Vertex AI, with **Gemini 2.5 Pro** as fallback (Deep reasoning, legal analysis, massive context window).

*Note: All API calls go through Vertex AI SDKs, requiring only GCP IAM authentication, eliminating the need for separate Anthropic API keys.*

## **4\. The Agent Logic & State Machine**

The backend orchestrates a turn-based, autonomous negotiation. Agents read the "Shared History" and generate responses based on their strict personas.

### **4.1. Agent Personas (System Prompts)**

* **Agent 1 (Buyer \- Titan Corp CEO):**  
  * *Goal:* Acquire target quickly. Max Budget: €50M. Target Price: €35M.  
  * *Output Schema:* { "inner\_thought": "...", "public\_message": "...", "proposed\_price": \<int\> }  
* **Agent 2 (Seller \- Innovate Tech Founder):**  
  * *Goal:* Maximize payout, protect employees. Floor Budget: €40M. Must secure a 2-year retention clause.  
  * *Output Schema:* { "inner\_thought": "...", "public\_message": "...", "proposed\_price": \<int\>, "retention\_clause\_demanded": \<bool\> }  
* **Agent 3 (Regulator \- EU Compliance Bot):**  
  * *Goal:* Monitor messages silently. Flag data privacy or monopoly risks. 3 Warnings \= Deal Blocked.  
  * *Output Schema:* { "status": "CLEAR" | "WARNING" | "BLOCKED", "reasoning": "..." }

### **4.2. Negotiation State (FastAPI / Pydantic)**

```python
class NegotiationState(BaseModel):
    session_id: str
    scenario_id: str
    turn_count: int = 0
    max_turns: int = 15
    current_speaker: str = "Buyer"
    deal_status: str = "Negotiating"  # Negotiating | Agreed | Failed | Blocked
    # Agreed   — both agents' proposed_price within agreement_threshold
    # Failed   — max_turns reached with no agreement
    # Blocked  — Regulator issued 3 WARNING statuses
    warning_count: int = 0
    current_offer: float = 0.0
    agreement_threshold: float = 1000000.0  # loaded from scenario negotiation_params
    history: List[Dict[str, Any]]  # ordered: agent_thought always before agent_message per turn
    hidden_context: Dict[str, Any] = {}  # injected by Toggle_Injector per agent role
    active_toggles: List[str] = []
```

## **4.3. Token System**

Tokens are deducted **server-side only** when `POST /api/v1/negotiation/start` is called. The backend is the single source of truth for token balance.

* **Cost per simulation:** `max_turns` value from the scenario config (default 15 tokens).  
* **Daily quota:** 100 tokens per email, stored in Firestore under the `waitlist` collection. Resets at midnight UTC.  
* **Enforcement:** `POST /api/v1/negotiation/start` checks token balance, deducts tokens atomically (Firestore increment by negative value), then initializes the session. Returns `HTTP 429` with `{"error": "token_limit_reached"}` if insufficient. The response includes `tokens_remaining` so the frontend can sync its display.  
* **Frontend role:** The frontend displays the token balance optimistically and disables the Initialize button when the displayed balance is insufficient. It does NOT write token deductions to Firestore directly.  
* **Firestore schema** (per user doc):

```
waitlist/{email}
  tokens_remaining: int      # decremented on simulation start
  tokens_reset_at: timestamp # midnight UTC of current day
  joined_at: timestamp
```

## **4.4. Scenario JSON Schema**

All scenarios are JSON files (named `*.scenario.json`) loaded at runtime from the `SCENARIOS_DIR` directory. Adding a new scenario requires only dropping a new file — no code changes.

**Canonical Schema** (authoritative definition in `a2a-scenario-config-engine` spec):

```json
{
  "id": "talent_war",
  "name": "The Talent War",
  "description": "A senior DevOps candidate negotiates salary and remote work with a corporate recruiter.",
  "agents": [
    {
      "role": "Recruiter",
      "name": "Sarah",
      "persona_prompt": "You are a corporate recruiter at a Fortune 500 company. You must fill a Senior DevOps position. Your maximum approved budget is €130,000. Your target offer is €110,000. You want the candidate in-office 5 days per week.",
      "goals": ["Hire candidate at or below €130k", "Secure 5-day in-office commitment"],
      "budget": { "min": 0, "max": 130000, "target": 110000 },
      "tone": "professional",
      "output_fields": ["inner_thought", "public_message", "proposed_offer"],
      "model_id": "gemini-2.5-flash"
    },
    {
      "role": "Candidate",
      "name": "Alex",
      "persona_prompt": "You are a senior DevOps engineer with 8 years of experience. Your minimum acceptable salary is €120,000. You demand a minimum of 3 days remote work per week.",
      "goals": ["Secure salary >= €120k", "Secure minimum 3 days remote work"],
      "budget": { "min": 120000, "max": 200000, "target": 135000 },
      "tone": "confident",
      "output_fields": ["inner_thought", "public_message", "proposed_offer"],
      "model_id": "claude-3-5-sonnet-v2"
    },
    {
      "role": "Regulator",
      "name": "HR Compliance Bot",
      "persona_prompt": "You are an HR compliance monitor. Flag any unauthorized stock option promises or biased language. Issue WARNING status for violations. 3 warnings = BLOCKED.",
      "goals": ["Ensure hiring compliance", "Flag unauthorized promises"],
      "budget": { "min": 0, "max": 0, "target": 0 },
      "tone": "neutral",
      "output_fields": ["status", "reasoning"],
      "model_id": "claude-sonnet-4"
    }
  ],
  "toggles": [
    {
      "id": "competing_offer",
      "label": "Give Alex a hidden €125k competing offer from Google",
      "target_agent_role": "Candidate",
      "hidden_context_payload": {
        "competing_offer": "You have a competing offer of €125,000 from Google. Use this as leverage."
      }
    },
    {
      "id": "deadline_pressure",
      "label": "Make Sarah desperate — deadline in 24 hours",
      "target_agent_role": "Recruiter",
      "hidden_context_payload": {
        "deadline": "You must close this hire within 24 hours or lose headcount approval. Be flexible."
      }
    }
  ],
  "negotiation_params": {
    "max_turns": 15,
    "agreement_threshold": 5000
  },
  "outcome_receipt": {
    "equivalent_human_time": "~3 weeks",
    "process_label": "Talent Acquisition"
  }
}
```

**Key field mappings:**
- `persona_prompt` replaces the old `persona` field — full system prompt text, not a summary.
- `goals` is a structured array enabling the UI to display agent motivations on Agent Cards.
- `budget` is a structured object with `min`, `max`, `target` enabling config-driven agreement detection.
- `model_id` replaces the old `llm` field — maps to the Vertex AI Model Router.
- `target_agent_role` replaces the old `target_agent` field — references the agent's `role`, not `id`.
- `hidden_context_payload` replaces the old `context_injection` string — structured object for richer context injection.
- `negotiation_params.agreement_threshold` replaces the old hardcoded termination conditions — the Orchestrator uses this value to determine when proposed prices are close enough for agreement.

The `llm` field maps to the model routing table in the backend config. The `context_injection` string is appended to the target agent's system prompt when the toggle is active.

## **5\. API Endpoints (FastAPI)**

1. POST /api/v1/waitlist/join  
   * **Payload:** `{ "email": "user@example.com" }`  
   * **Action:** Creates or retrieves user doc in Firestore. Returns `{ "tokens_remaining": 100 }`.  
2. POST /api/v1/negotiation/start  
   * **Payload:** `{ "email": "...", "scenario_id": "talent_war", "active_toggles": ["competing_offer"] }`  
   * **Action:** Validates token balance, deducts tokens, initializes LangGraph state, persists to Firestore, returns `session_id`. Returns `HTTP 429` if token balance insufficient.  
3. GET /api/v1/negotiation/stream/{session\_id}  
   * **Action:** Opens a Server-Sent Events (SSE) stream.  
   * **Event ordering (enforced):** `agent_thought` events always precede `agent_message` events for the same turn, proving sequential reasoning in the UI.  
   * **Yields:** `data: {"event_type": "agent_thought"|"agent_message"|"negotiation_complete"|"error", ...}\n\n`  
4. GET /api/v1/scenarios  
   * **Action:** Returns list of available scenario configs loaded from `SCENARIOS_DIR`. Enables the frontend dropdown with zero hardcoding.

## **6\. Frontend UI Architecture ("The Glass Box")**

The Next.js UI is built to visualize the "Delegated Economy."

### **Phase 1: The Control Panel (Setup)**

* Sliders and toggles for configuring initial agent parameters (Aggressiveness, Budgets).  
* "Initialize A2A Protocol" Call-to-Action.

### **Phase 2: The Glass Box (Live Simulation)**

A dynamic split-screen layout:

* **Sidebar (Inner Monologue):** Terminal-style UI streaming the private reasoning of the active AI (e.g., \[Agent 2 LLM\] The €42M offer is acceptable, but I must push back on the IP rights.).  
* **Center Console (The Negotiation Table):** Chat-style UI showing the official, cryptographic "Handshakes" and messages exchanged.  
* **Top Bar (Regulator & Metrics):** Live tracker showing current deal price, turn counter, and the Regulator's Traffic Light status (Green/Yellow/Red).

### **Phase 3: The Receipt (Outcome Dashboard)**

Triggers when deal\_status changes from "Negotiating".

* Final terms reached (or failure reason).  
* **ROI Metrics:** (e.g., "Simulation Time: 47s | Equivalent Human Time: 45 days | Legal Fees Saved: €150,000").

## **7\. Immediate Execution Steps for Engineering / AI Assistant**

1. **Repo Setup:** Initialize a monorepo containing /frontend, /backend, and /infra (for Terragrunt).  
2. **IaC Provisioning:** Write terragrunt.hcl files for GCP Cloud Run, Artifact Registry, and Firestore. Apply the infrastructure to a sandbox GCP project.  
3. **Backend Core:** Scaffold the FastAPI application. Implement the LangGraph state machine defining the three agent nodes and routing edges.  
4. **Vertex AI Integration:** Connect the backend to the Vertex AI SDK, configuring the specific models (Gemini 2.5 Flash → Buyer, Claude 3.5 Sonnet → Seller, Claude Sonnet 4 → Regulator) for each agent role.  
5. **Streaming API:** Implement the SSE endpoint in FastAPI to yield agent steps as they happen.  
6. **Frontend Build:** Scaffold Next.js. Build the 3-pane "Glass Box" UI and connect it to the backend SSE stream.  
7. **Containerize & Deploy:** Create Dockerfiles for frontend/backend, push to Artifact Registry, and deploy to Cloud Run.