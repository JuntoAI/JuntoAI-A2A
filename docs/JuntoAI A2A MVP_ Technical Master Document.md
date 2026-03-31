# **TECHNICAL SPECIFICATION: JuntoAI A2A MVP (V1)**

**Project Code:** "The M\&A War Room"

**Target Cloud Environment:** Google Cloud Platform (GCP)

**Infrastructure as Code (IaC):** Terraform & Terragrunt

## **1\. Project Overview & Architecture**

The objective is to build a standalone, fully functional V1 MVP demonstrating the JuntoAI Agent-to-Agent (A2A) negotiation protocol. The application simulates a high-stakes Mergers & Acquisitions negotiation between three autonomous AI agents (Buyer, Seller, Regulator) with a real-time UI showing both public dialogue and private "inner thoughts."

**Core Technology Stack:**

* **Frontend:** Next.js 14+ (App Router), React, Tailwind CSS, Lucide React.  
* **Frontend Hosting:** Firebase App Hosting (or GCP Cloud Run).  
* **Backend API:** Python 3.11+, FastAPI (using Server-Sent Events/SSE for streaming).  
* **Backend Compute:** GCP Cloud Run (Containerized, Serverless).  
* **AI Orchestration:** Google Agent Development Kit (ADK) or LangGraph.  
* **LLM Provider:** Google Vertex AI (Model Garden).  
* **State & Database:** GCP Firestore (NoSQL) or Vertex AI Agent Engine Memory Bank.  
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
    bucket  \= "juntoai-terraform-state-prod"  
    prefix  \= "${path\_relative\_to\_include()}/terraform.tfstate"  
    project \= "juntoai-project-id"  
    location \= "eu" \# EU region for compliance  
  }  
}

### **2.2. Core GCP Resources to Provision**

1. **Cloud Run Services:** One for the Python FastAPI backend, one for the Next.js frontend (if not using Firebase App Hosting).  
2. **Artifact Registry:** Repositories for Docker images.  
3. **Firestore:** Native mode database for state management.  
4. **Vertex AI API Enablers:** Enabling the Vertex AI API for the project.  
5. **IAM Service Accounts:** Strict least-privilege roles for Cloud Run to access Vertex AI and Firestore.

## **3\. AI Orchestration & LLM Heterogeneity (Vertex AI)**

To prove protocol agnosticism and "LLM Heterogeneity" to investors, the orchestration layer will route to different foundational models hosted natively within **Vertex AI Model Garden**.

* **Agent 1 (The Buyer):** Powered by **Google Gemini 3.1 Flash** (Fast, logical, cost-effective).  
* **Agent 2 (The Seller):** Powered by **Anthropic Claude 3.5/3.7 Sonnet** via Vertex AI (Empathetic, nuanced negotiation).  
* **Agent 3 (The Regulator):** Powered by **Anthropic Claude 4 Opus** or **Gemini 3.1 Pro** via Vertex AI (Deep reasoning, legal analysis, massive context window).

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

class NegotiationState(BaseModel):  
    session\_id: str  
    turn\_count: int \= 0  
    max\_turns: int \= 15  
    current\_speaker: str \= "Buyer"  
    deal\_status: str \= "Negotiating" \# Negotiating, Agreed, Blocked, Failed  
    current\_offer: float \= 0.0  
    history: List\[Dict\[str, Any\]\] \# Array of public messages and private thoughts

## **5\. API Endpoints (FastAPI)**

1. POST /api/v1/negotiation/start  
   * **Payload:** Investor UI settings (e.g., { "information\_asymmetry": true, "regulator\_strictness": "high" }).  
   * **Action:** Initializes the Graph/ADK state, persists to Firestore, returns session\_id.  
2. GET /api/v1/negotiation/stream/{session\_id}  
   * **Action:** Opens a Server-Sent Events (SSE) stream.  
   * **Yields:** Real-time JSON chunks as the LLMs generate their "inner\_thought" and "public\_message".

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

1. **Repo Setup:** Initialize a monorepo containing /frontend, /backend, and /infrastructure (for Terragrunt).  
2. **IaC Provisioning:** Write terragrunt.hcl files for GCP Cloud Run, Artifact Registry, and Firestore. Apply the infrastructure to a sandbox GCP project.  
3. **Backend Core:** Scaffold the FastAPI application. Implement the LangGraph/ADK state machine defining the three agent nodes and routing edges.  
4. **Vertex AI Integration:** Connect the backend to the Vertex AI SDK, configuring the specific models (Gemini Flash, Claude Sonnet, Claude Opus) for each agent role.  
5. **Streaming API:** Implement the SSE endpoint in FastAPI to yield agent steps as they happen.  
6. **Frontend Build:** Scaffold Next.js. Build the 3-pane "Glass Box" UI and connect it to the backend SSE stream.  
7. **Containerize & Deploy:** Create Dockerfiles for frontend/backend, push to Artifact Registry, and deploy to Cloud Run.