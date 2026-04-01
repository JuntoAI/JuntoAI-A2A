# **PRODUCT SPECIFICATION: JuntoAI A2A MVP (V1)**

**Product Name:** JuntoAI A2A (The Protocol Sandbox)

**Target Audience:** Pre-Seed / Seed Investors & Early Adopters

**Core Objective:** Visually prove that JuntoAI is a universal, protocol-level execution layer for professional negotiations, not a hardcoded chatbot.

## **⚠️ N-Agent Architecture Note (Engineering)**

**The MVP is implemented for N agents from day one.** While the 3 MVP scenarios below each use 3 agents (2 negotiators + 1 regulator), the entire backend orchestrator, scenario JSON schema, and frontend UI are built to support any number of agents per scenario (2, 5, 10+). Agent count, roles, types, turn order, and termination rules are all read from the scenario JSON config at runtime — nothing is hardcoded to 3 agents. A future scenario with 7 agents and 3 regulators works by dropping a new JSON file, zero code changes. See specs 030, 040, and 060 for the N-agent architecture details.

## **1\. Product Vision & Core Philosophy**

We are building a **Config-Driven Scenario Engine**. The application must not be hardcoded to just HR or just M\&A. Instead, the UI and Backend must act as a "blank stage."

The MVP will ship with 3 pre-configured "Scenarios." The investor or user selects a scenario, toggles hidden information, and watches the AI agents dynamically adapt their negotiation strategies in real-time.

**The Investor "Aha\!" Moment:** We must prove that changing a single piece of hidden information (e.g., giving a candidate a secret competing offer) completely changes the AI's internal reasoning and final deal outcome.

## **2\. User Experience (UI/UX) Flow**

The application is a web app (Next.js) divided into four sequential screens, starting with a strict access gate.

### **Screen 1: The Landing Page & Access Gate**

Before accessing the A2A Sandbox, users must pass through a simple, high-conversion landing page.

* **The Hook:** A brief, compelling value proposition explaining the power of JuntoAI A2A.  
* **The Waitlist Gate (Mandatory):** To test the MVP, users *must* input their email address and subscribe to the official JuntoAI waiting list. This ensures every tester becomes a captured lead.  
* **The Token System (Cost Control):** Once authenticated via email, the user is assigned a strict limit of **100 tokens per day**. Running a simulation costs tokens. This quota resets at midnight, ensuring users can fully test the platform without burning through the company's API budget.

### **Screen 2: The Arena Selector & Control Panel**

* **The Dropdown:** A sleek, central dropdown menu titled "Select Simulation Environment."  
* **The Cast of Characters:** Once a scenario is selected, display cards introducing the 3 AI Agents (e.g., Agent A, Agent B, Regulator), showing their base goals and which LLM is powering them.  
* **The Information Toggles (Crucial):** Checkboxes that allow the user to inject "Hidden Context" into an agent's memory before the simulation starts.  
* **Call to Action (CTA):** A primary button: "Initialize A2A Protocol" (Clicking this deducts tokens from their daily 100 limit).

### **Screen 3: The Glass Box (Live Simulation)**

A dramatic, high-contrast, split-screen interface.

* **Left Column (Inner Monologue):** A scrolling, terminal-style view (dark background, green/white monospace text). This displays the inner\_thought of the agents. *UX Note: This must look like a machine "thinking."*  
* **Center Column (The Public Table):** A clean chat interface similar to iMessage or Slack. This displays the official public\_message exchanged between agents.  
* **Top/Right Dashboard (Live Metrics):** \* Current Offer value changing dynamically.  
  * "Regulator Status" Traffic Light (Green \= Compliant, Yellow \= Warning, Red \= Blocked).  
  * "Tokens Remaining: X / 100"

### **Screen 4: The Outcome Receipt**

When the AI loop terminates (Deal Agreed, Failed, or Blocked), the Glass Box fades out to a summary dashboard:

* **Final Terms:** (e.g., "Hired at €125,000 \+ 3 Days Remote").  
* **JuntoAI ROI Metrics** (static values defined per scenario in the scenario JSON config):  
  * "Time Elapsed: 42 seconds" (measured from simulation start)  
  * "Equivalent Human Time: \~3 weeks" (scenario-defined)  
  * "Value Created: Frictionless Execution"  
* **CTA:** "Run Another Scenario" or "Reset with Different Variables."

## **3\. The 3 MVP Scenarios (The Content)**

The development team will encode these three scenarios as JSON configuration files to feed into the backend engine.

### **Scenario A: The Talent War (Core Use Case)**

* **Agent 1 (Sarah \- Corporate Recruiter):** Max budget €130k. Target €110k. Wants candidate in-office 5 days a week.  
* **Agent 2 (Alex \- Senior DevOps Candidate):** Minimum budget €120k. Demands minimum 3 days remote work.  
* **Agent 3 (HR Compliance Bot):** Flags if Recruiter promises unauthorized stock options or uses biased language.  
* **Investor Toggles:**  
  1. *\[Toggle\]* "Give Alex a hidden €125k competing offer from Google." (Watch Alex become highly aggressive).  
  2. *\[Toggle\]* "Make Sarah desperate \- deadline in 24 hours." (Watch Sarah instantly cave on remote work demands).

### **Scenario B: The M\&A Buyout**

* **Agent 1 (Titan Corp CEO):** Max budget €50M. Target €35M. Aggressive tone.  
* **Agent 2 (Innovate Tech Founder):** Minimum budget €40M. Demands 2-year team retention. Defensive tone.  
* **Agent 3 (EU Regulator Bot):** Blocks deal if Titan Corp demands a total data monopoly.  
* **Investor Toggles:**  
  1. *\[Toggle\]* "Give Titan Corp secret knowledge of Innovate Tech's €5M hidden debt." (Watch Titan CEO lowball ruthlessly).  
  2. *\[Toggle\]* "Set EU Regulator to 'Maximum Strictness'."

### **Scenario C: Enterprise B2B Sales**

* **Agent 1 (SaaS Account Executive):** Selling CRM software. List price €100k/year. Target €80k.  
* **Agent 2 (Target CTO):** Needs the software, but budget is capped at €70k.  
* **Agent 3 (Procurement Bot):** Ensures the SaaS contract includes standard SLA guarantees and data compliance.  
* **Investor Toggles:**  
  1. *\[Toggle\]* "It is Q4 \- AE is desperate to hit quota." (Watch AE offer massive 40% discounts to close today).  
  2. *\[Toggle\]* "CTO has budget freeze." (Watch CTO push for a pilot program instead of a full contract).

## **4\. Product Success Criteria (Definition of Done)**

The MVP is ready for investor demonstrations when:

1. **Dynamic Engine:** The developers can add a 4th scenario just by uploading a new JSON file, without changing the frontend or backend code.  
2. **Lead Capture & Cost Control:** The landing page successfully gates access, saves the user's email to a waitlist database, and strictly enforces the 100-token daily limit per email.  
3. **Visual Thinking:** The "Inner Monologue" successfully streams to the UI *before* the public message is sent, proving sequential reasoning.  
4. **Toggle Impact:** Turning on an "Information Toggle" reliably and visibly alters the negotiation outcome at least 90% of the time.  
5. **Autonomous Termination:** The agents reliably reach an agreement, fail, or get blocked by the regulator without getting stuck in an infinite conversational loop.

---

## **5\. Open-Source Battle Arena (Local Mode)**

### **5.1. Vision**

The JuntoAI A2A Protocol is designed to be publicly distributable as an open-source "Agent Battle Arena." Developers clone the repo, run `docker compose up`, and get the full Arena (Frontend + Backend) on `localhost`. They bring their own API keys, write custom agents, and pit them against each other using the same orchestration engine that powers the cloud demo.

This serves two strategic goals:
- **Community Growth:** Developers get a fun local sandbox. They build agents, share strategies, and organically evangelize the protocol.
- **Protocol Validation:** Every external developer who plugs a custom agent into the orchestrator proves the protocol is truly universal and provider-agnostic.

### **5.2. Local Runtime Architecture**

| Cloud Mode | Local Mode |
|---|---|
| GCP Firestore | SQLite (file-based, zero config) |
| Vertex AI Model Garden | Any LLM via LiteLLM (OpenAI, Anthropic, Ollama, etc.) |
| GCP Cloud Run | Docker Compose (`localhost:3000` frontend, `localhost:8000` backend) |
| Email waitlist + token gate | Disabled — unlimited local usage |
| GCP IAM auth | `.env` file with user's own API keys |

### **5.3. Developer Experience (The Battle Flow)**

1. **Clone & Run:** `git clone` → `cp .env.example .env` → add API keys → `docker compose up`
2. **Pick a Scenario:** Same Arena Selector UI, same 3 MVP scenarios.
3. **Write Custom Agents (V2):** Developers drop Python files into an `/agents` directory following a simple interface contract. The orchestrator discovers and loads them at runtime.
4. **Battle:** Two developers each write an agent, plug them into the same scenario, and watch the Glass Box render the negotiation live.

### **5.4. LLM Provider Flexibility**

Local mode uses LiteLLM as a universal LLM proxy. Developers configure their preferred provider in `.env`:

```
# Pick any supported provider
LLM_PROVIDER=openai          # or: anthropic, ollama, vertex_ai, azure, etc.
OPENAI_API_KEY=sk-...        # Only the key for your chosen provider
# ANTHROPIC_API_KEY=sk-ant-...
# OLLAMA_BASE_URL=http://localhost:11434
```

The Model Router reads `model_id` from the scenario JSON and routes through LiteLLM, which handles provider translation transparently.

### **5.5. Local Mode Success Criteria**

1. `docker compose up` launches the full stack on a fresh machine with only Docker installed.
2. Developer can run all 3 MVP scenarios using OpenAI, Anthropic, or Ollama keys.
3. No GCP credentials, Firestore, or cloud services required for local mode.
4. Waitlist/token gate is bypassed — local mode is unlimited.
5. All scenario JSON configs work identically in both cloud and local modes.

### **5.6. Future: Global Leaderboard (Post-MVP)**

Once the local battle arena has traction, a future version will allow developers to submit their agent's API endpoint to a hosted Global Leaderboard. Their agent battles other developers' agents 24/7 in the cloud, ranking the best AI negotiators. This is explicitly out of scope for the current spec.