---
marp: true
theme: default
paginate: true
backgroundColor: #1C1C1E
color: #FAFAFA
style: |
  section {
    font-family: 'Inter', sans-serif;
  }
  h1 {
    color: #00E676;
  }
  h2 {
    color: #00E676;
  }
  code {
    background: #2d2d30;
    color: #00E676;
    padding: 2px 6px;
    border-radius: 4px;
  }
  pre {
    background: #2d2d30;
    border-radius: 8px;
    padding: 16px;
  }
  pre code {
    color: #E0E0E0;
  }
  pre code .hljs-string {
    color: #CE9178;
  }
  pre code .hljs-number {
    color: #B5CEA8;
  }
  pre code .hljs-attr, pre code .hljs-property {
    color: #9CDCFE;
  }
  pre code .hljs-keyword {
    color: #C586C0;
  }
  pre code .hljs-comment {
    color: #6A9955;
  }
  pre code .hljs-literal {
    color: #569CD6;
  }
  a {
    color: #007BFF;
  }
  blockquote {
    border-left: 4px solid #00E676;
    padding-left: 16px;
    color: #ccc;
  }
  table {
    font-size: 0.85em;
    width: 100%;
    border-collapse: collapse;
  }
  th {
    background: #007BFF;
    color: #FAFAFA;
    padding: 10px 16px;
    text-align: left;
  }
  td {
    background: #2d2d30;
    color: #FAFAFA;
    padding: 8px 16px;
    border-bottom: 1px solid #444;
  }
  tr:nth-child(even) td {
    background: #363638;
  }
  .highlight {
    color: #00E676;
    font-weight: bold;
  }
  img[alt~="center"] {
    display: block;
    margin: 0 auto;
  }
---

<!-- _class: lead -->
<!-- _backgroundColor: #0d0d0f -->

# Building an Agent-to-Agent Negotiation Network

### When AI Agents Discuss Real-World Challenges

<br>

**ai.lnu.edu.ua** | June 2026

<br>

*JuntoAI — The Next-Generation Business Network*

---

## Dr. Markus Schmidberger

- **Co-Founder & CTO** — JuntoAI (AI-native professional network)
- **20+ years** in data strategy, AI systems & leadership
- **PhD** (Dr. rer. nat.) — LMU Munich, parallel computing
- Published researcher (ACM) · Advisor to executives on modern data practices
- Previously: data & AI leadership roles in enterprise (insurance, real estate, tech)

<br>

> Today: I'll show you **how** to build agents that negotiate,
> **why** it matters, and **what's next** — agents that find
> your best professional connections automatically.

<br>

LinkedIn: [linkedin.com/in/schmidberger](https://www.linkedin.com/in/schmidberger/) · Email: markus@juntoai.org

---

<!-- _class: lead -->
<!-- _backgroundColor: #0d0d0f -->

# Part 1
## What Is an AI Agent? And Why A2A?

---

## Poll #1: Quick Pulse Check

![center](slido-qr.png)

**Join at [app.sli.do/event/pqBzUc4rJqvZkmAGFJ5QUK](https://app.sli.do/event/pqBzUc4rJqvZkmAGFJ5QUK)**

---

## What Is an AI Agent?

A program that **perceives**, **decides**, and **acts** — autonomously.

```
┌─────────────────────────────────────────────────┐
│                    AI AGENT                       │
│                                                  │
│  [Perception]  →  [Reasoning]  →  [Action]      │
│                                                  │
│  "Read the       "Decide what     "Make an      │
│   situation"      to do next"      offer"       │
│                                                  │
│  + Memory (state across turns)                   │
│  + Goals (what success looks like)               │
│  + Constraints (rules it cannot break)           │
└─────────────────────────────────────────────────┘
```

**Not a chatbot.** A chatbot responds. An agent *pursues objectives*.

---

## From Single Agent to Agent-to-Agent (A2A)

| | Single Agent | Agent-to-Agent (A2A) |
|--|-------------|---------------------|
| **Structure** | Human ↔ Agent | Agent ↔ Agent (↔ Agent...) |
| **Goal** | Help the user | Each agent has its OWN goal |
| **Conflict** | None — agent serves you | Built-in — agents negotiate |
| **Outcome** | Response | Agreement, failure, or block |
| **Example** | "Summarize this doc" | "Negotiate a €50M acquisition" |

<br>

> A2A = multiple agents, each with their own persona, goals, and constraints,
> interacting autonomously until they reach (or fail to reach) an agreement.

---

## Why A2A Matters: Real-World Applications

```
Today                          Tomorrow
─────                          ────────
Salary negotiation             Agent negotiates your package
Contract review                Agents find optimal terms
Due diligence                  Agent researches counterparty
Networking                     Agent finds + introduces people
Compliance checks              Regulator agent enforces in real-time
```

<br>

**The pattern:** Any process with multiple parties, competing interests,
and structured rules can be modeled as A2A interaction.

<br>

Now let me show you why this matters with numbers...

---

## The Problem: Humans Are the Bottleneck

| Process | Human Time | Agent Time |
|---------|-----------|------------|
| Salary negotiation | ~3 weeks | 42 seconds |
| M&A deal structure | ~6 months | 90 seconds |
| B2B contract terms | ~4 weeks | 55 seconds |

<br>

Not because humans are slow thinkers —
because **scheduling, ego, and information asymmetry** slow everything down.

---

## What If Agents Could...

1. **Negotiate** salary, contracts, acquisitions autonomously
2. **Regulate** fairness in real-time (no waiting for lawyers)
3. **Discover** the right people in your network you didn't know about
4. **Introduce** you with personalized communication guidance

<br>

> This isn't science fiction. We built it. Let me show you.

---

## JuntoAI A2A: What We Built

A **config-driven scenario engine** where:

- Drop a JSON file → get a new negotiation (zero code changes)
- Autonomous AI agents negotiate with distinct personas
- A **Glass Box UI** streams inner reasoning + public messages
- Flip one hidden toggle → deal outcome changes visibly

<br>

**Open source:** [github.com/JuntoAI/JuntoAI-A2A](https://github.com/JuntoAI/JuntoAI-A2A)
`docker compose up` → full stack on localhost

---

<!-- _class: lead -->
<!-- _backgroundColor: #0d0d0f -->

# Part 2
## The 5 Building Blocks of A2A Interaction

---

## Building Block 1: State Machines (LangGraph)

Conversations need **memory** and **structure** — not just prompt → response.

```
Scenario JSON → FastAPI Orchestrator → LangGraph State Machine
    → AI Agents (Gemini/Claude) → SSE Stream → Glass Box UI
```

<br>

**Why LangGraph?**
- Each agent is a **node** in a directed graph
- A central **dispatcher** routes turns and checks terminal conditions
- State persists across turns: offers, warnings, agreement detection

---

## The State Machine in Code

```python
class NegotiationState(TypedDict):
    session_id: str
    turn_count: int
    max_turns: int
    current_speaker: str
    deal_status: str          # Negotiating | Agreed | Failed | Blocked
    current_offer: float
    history: Annotated[list[dict], add]  # append-only
    hidden_context: dict      # toggle injections
    warning_count: int
    agent_states: dict        # per-agent memory
    active_toggles: list[str]
    turn_order: list[str]     # ["Buyer", "Regulator", "Seller", "Regulator"]
```

Every field is **typed** and **deterministic**. No magic strings.

---

## Graph Construction: Dynamic from Config

```python
def build_graph(scenario_config: dict) -> CompiledStateGraph:
    agents = scenario_config["agents"]
    graph = StateGraph(NegotiationState)

    # One node per agent role
    for role in unique_roles:
        graph.add_node(role, create_agent_node(role))

    # Central dispatcher for routing
    graph.add_node("dispatcher", _dispatcher)

    # Every agent feeds back to dispatcher
    for role in unique_roles:
        graph.add_edge(role, "dispatcher")

    # Conditional routing: dispatcher → next agent or END
    graph.add_conditional_edges("dispatcher", _route_dispatcher)
    return graph.compile()
```

**N-agent architecture from day one** — nothing hardcoded to 3 agents.

---

## Building Block 2: Structured Personas

Each agent has a **full persona prompt**, not just a role label:

```json
{
  "role": "Seller",
  "name": "Elena",
  "type": "negotiator",
  "persona_prompt": "You are Elena, founder and CEO of Innovate Tech,
    a cutting-edge AI startup with 50 employees, 8M EUR ARR growing
    120% YoY. You NEVER accept earn-out structures that exceed 20%
    of total deal value...",
  "goals": [
    "Achieve minimum 50M EUR valuation",
    "Limit earn-out to max 20%",
    "Require 2-year no-layoff clause"
  ],
  "budget": { "min": 45000000, "max": 80000000, "target": 55000000 },
  "tone": "confident and protective",
  "model_id": "gemini-3.1-pro-preview"
}
```

---

## Building Block 3: Config-Driven Scenarios

Adding a new scenario = **dropping a JSON file**. Zero code changes.

```
backend/app/scenarios/data/
├── talent-war.scenario.json      # HR salary negotiation
├── ma-buyout.scenario.json       # Corporate acquisition
├── b2b-sales.scenario.json       # SaaS contract
└── your-scenario.scenario.json   # YOUR creation
```

<br>

The scenario defines:
- **Agents** (roles, personas, budgets, models)
- **Toggles** (hidden information injections)
- **Negotiation params** (max turns, agreement threshold, turn order)
- **Outcome receipt** (equivalent human time, process label)

---

## Building Block 4: The Regulator Pattern

An autonomous **oversight agent** that enforces rules in real-time:

```json
{
  "role": "Regulator",
  "name": "Dr. Fischer",
  "type": "regulator",
  "persona_prompt": "You are Dr. Fischer, EU Regulatory Compliance
    Advisor. You calculate market concentration using HHI indices.
    Issue WARNINGs for: insufficient market share data, missing GDPR
    assessments. BLOCK deals with unresolved competition concerns.",
  "output_fields": ["status", "reasoning"]
}
```

<br>

**Rule: 3 warnings = deal BLOCKED.** No human intervention needed.

---

## The Regulator's Output Schema

```json
{
  "status": "WARNING",
  "reasoning": "Post-merger market share in NLP services exceeds 35%.
    Buyer has not provided binding FRAND licensing commitments.
    This is Warning 2 of 3. Provide concrete remedies or
    the deal will be BLOCKED."
}
```

<br>

The dispatcher reads `status` and increments `warning_count` in state.
At `warning_count >= 3` → `deal_status = "Blocked"` → negotiation ends.

---

## Building Block 5: The Toggle Mechanism

One hidden variable changes **everything**:

```json
{
  "id": "hidden_debt",
  "label": "James discovers 5M EUR undisclosed debt",
  "target_agent_role": "Buyer",
  "hidden_context_payload": {
    "hidden_debt_intelligence": true,
    "debt_amount": 5000000,
    "debt_details": "Your due diligence team discovered 5M EUR
      in undisclosed debt. Use this strategically: raise it to
      justify a 5-8M EUR reduction in your offer."
  }
}
```

**Only the target agent sees this.** Others negotiate blind.
The `hidden_context` is injected into the system prompt at runtime.

---

## How Toggles Work in the Agent Node

```python
# Inside create_agent_node → _build_messages()

# Inject hidden context for this specific agent
hidden_ctx = state.get("hidden_context", {})
agent_hidden = {k: v for k, v in hidden_ctx.items()
                if toggle["target_agent_role"] == agent_role}

if agent_hidden:
    system_prompt += f"\n\n## CLASSIFIED INTELLIGENCE\n"
    system_prompt += json.dumps(agent_hidden, indent=2)
```

<br>

The same scenario with different toggles → **reproducibly different outcomes**.
This is the investor "Aha!" moment. And it works for research too.

---

<!-- _class: lead -->
<!-- _backgroundColor: #0d0d0f -->

# Part 3
## Live Demo

### Let's Watch Agents Negotiate — and Break Them

---

## Poll #2: Predict the Outcome

![center](slido-qr.png)

**Join at [app.sli.do/event/pqBzUc4rJqvZkmAGFJ5QUK](https://app.sli.do/event/pqBzUc4rJqvZkmAGFJ5QUK)**

---

## Demo: The M&A Buyout

**Cast:**
- 🏢 **James** (Titan Corp CEO) — Budget: €25M-€50M, Target: €38M
- 🚀 **Elena** (Innovate Tech Founder) — Floor: €45M, Target: €55M
- ⚖️ **Dr. Fischer** (EU Regulator) — Enforces competition law

**Turn order:** Buyer → Regulator → Seller → Regulator → ...

<br>

> First run: no toggles. Let's watch the natural negotiation.

---

## The Glass Box: What You See

| Panel | Content |
|-------|---------|
| 🖥️ **Terminal** (left) | Inner thoughts — machine "thinking" |
| 💬 **Chat** (center) | Public messages between agents |
| 📊 **Metrics** (top) | Current offer, regulator status, turn count |

<br>

**Key insight:** Inner thoughts stream **BEFORE** public messages.
You see the reasoning, then the action. Proves sequential thinking.

---

## Now Let's Flip a Toggle

**Toggle ON:** *"James discovers 5M EUR undisclosed debt"*

<br>

Watch what happens:
- James's inner thought references the debt
- His public message uses it as leverage
- His offer drops by 5-8M EUR
- Elena's response changes because of the new anchor
- The entire deal trajectory shifts

<br>

> **Same agents. Same scenario. One hidden variable. Different outcome.**

---

## Toggle #2: Maximum Regulator Strictness

**Toggle ON:** *"Dr. Fischer applies Phase II EU merger investigation"*

Now the regulator demands:
1. Binding FRAND licensing commitments for 5 years
2. Structural data separation between entities
3. Independent monitoring trustee for 3 years

<br>

**BLOCK if fewer than 2 of 3 remedies accepted.**

> The regulator becomes the most powerful agent in the room.

---

## What Just Happened (Architecture View)

```
Toggle activated
    ↓
hidden_context_payload merged into state.hidden_context
    ↓
Agent node builds prompt → injects CLASSIFIED INTELLIGENCE
    ↓
LLM generates response with hidden knowledge
    ↓
Public message reflects new strategy
    ↓
Other agents react to the public behavior (not the hidden info)
    ↓
Cascade effect → different outcome
```

---

## Agreement Detection: How Deals Close

```python
def _check_agreement(state) -> bool:
    # Collect last_proposed_price from all negotiators
    prices = [info["last_proposed_price"]
              for info in agent_states.values()
              if info["agent_type"] == "negotiator"]

    # Check: max - min <= agreement_threshold
    return max(prices) - min(prices) <= state["agreement_threshold"]
```

When prices converge within threshold → **confirmation round** →
both parties confirm → `deal_status = "Agreed"`.

No hardcoded "accept" logic. Pure numerical convergence.

---

<!-- _class: lead -->
<!-- _backgroundColor: #0d0d0f -->

# Part 4
## Infrastructure: Under the Hood

---

## Infrastructure Stack

| Layer | Cloud Mode | Local Mode |
|-------|-----------|------------|
| **Compute** | GCP Cloud Run (serverless) | Docker Compose |
| **Database** | Firestore (Native mode) | SQLite |
| **LLM Router** | Vertex AI Model Garden | LiteLLM (any provider) |
| **Auth** | Email waitlist + 100 tokens/day | Bypassed |
| **IaC** | Terraform + Terragrunt | N/A |
| **CI/CD** | Google Cloud Build | N/A |
| **State** | GCS (remote locking) | Local file |

<br>

**Same scenario JSONs work in both modes** — zero config changes.

---

## LLM Heterogeneity: Multi-Model by Design

```
┌─────────────────────────────────────────────────┐
│            Vertex AI Model Garden                │
├──────────────┬──────────────┬───────────────────┤
│ Gemini Flash │ Claude 3.5   │ Claude Sonnet 4   │
│ (Buyer)      │ (Seller)     │ (Regulator)       │
│ Fast, cheap  │ Empathetic   │ Deep reasoning    │
└──────────────┴──────────────┴───────────────────┘
```

Each agent's `model_id` in the scenario JSON → Model Router → correct LLM.
**One IAM credential** handles all models. No separate API keys.

<br>

Local mode: LiteLLM routes to OpenAI, Anthropic, or Ollama transparently.

---

## Terragrunt: DRY Infrastructure

```hcl
# infra/terragrunt.hcl
remote_state {
  backend = "gcs"
  config = {
    bucket   = "juntoai-terraform-state-prod"
    prefix   = "${path_relative_to_include()}/terraform.tfstate"
    project  = "juntoai-project-id"
    location = "eu"
  }
}
```

**GCP resources provisioned:**
- Cloud Run (backend + frontend)
- Artifact Registry (Docker images)
- Firestore (sessions, waitlist, tokens)
- Vertex AI API
- IAM Service Accounts (least-privilege)

---

## SSE Streaming: Real-Time Glass Box

```python
# Backend streams events as SSE
async def stream_negotiation(session_id: str):
    async for event in run_graph(session_id):
        yield f"data: {json.dumps(event)}\n\n"

# Event types:
# - agent_thought  → Terminal panel (inner reasoning)
# - agent_message  → Chat panel (public message)
# - negotiation_complete → Outcome receipt
# - error → Error handling
```

**Inner thoughts stream BEFORE public messages** — proves sequential reasoning.
Frontend renders them in separate panels with different visual treatment.

---

<!-- _class: lead -->
<!-- _backgroundColor: #0d0d0f -->

# Part 5
## From Simulation to Real Agents

### What If Agents Acted On YOUR Behalf?

---

## Poll #3: Your Networking Pain

![center](slido-qr.png)

**Join at [app.sli.do/event/pqBzUc4rJqvZkmAGFJ5QUK](https://app.sli.do/event/pqBzUc4rJqvZkmAGFJ5QUK)**

---

## The Leap: Simulation → Action

What we just saw: agents negotiating **simulated** deals.

What's next: agents that **find real connections** for you.

<br>

> "The same architecture that lets agents negotiate a €50M acquisition
> can match you with the right person in a network of 10,000."

<br>

Same building blocks:
- State machines for multi-step pipelines
- Structured personas (your identity model)
- Config-driven matching criteria
- Agent-to-agent cross-network discovery

---

## Network Matching: The Concept

```
Your LinkedIn connections (500+)
    ↓
Two-tier AI enrichment pipeline
    ↓
Match against YOUR goals + identity
    ↓
Top 5 matches with personalized communication guidance
    ↓
"Here's who to talk to, what to say, and why NOW"
```

<br>

**The killer feature:** When multiple users import connections →
matches **OUTSIDE** your own network become possible.

*"A JuntoAI member can introduce you."*

---

## Two-Tier Dossier Architecture

| | Tier 1: Simple Dossier | Tier 2: Full Dossier Agent |
|--|----------------------|--------------------------|
| **Purpose** | Fast screening of ALL connections | Deep research on top 20 |
| **Model** | Gemini Flash + Search Grounding | 3-8 Gemini rounds + page fetches |
| **Cost** | ~$0.005-0.01 per connection | ~$0.10-0.15 per connection |
| **Time** | 3-8 min for 500 connections | 60-90 sec each, 5x parallel |
| **Output** | Role, company, focus areas, signals | Full personal DNA profile |

<br>

**Total cost per user: ~$4-8** for 500 connections analyzed.

---

## What You Get: The Match Card

```
┌─────────────────────────────────────────┐
│ 🏷 In Your Network  |  Fit: 91%         │
│                                         │
│ Sarah Chen                              │
│ VP Engineering, Platform @ Acme Corp    │
│                                         │
│ Why this match:                         │
│ "Building the exact platform infra you  │
│  need; actively advising pre-Series A"  │
│                                         │
│ How to reach out:                       │
│ "Sarah, I saw your QCon talk on         │
│  platform teams — we're solving a       │
│  similar challenge."                    │
│                                         │
│ Your approach:                          │
│ "Lead with the problem, not your        │
│  credentials. She values directness."   │
└─────────────────────────────────────────┘
```

---

## Cross-User Matching: Agent-to-Agent Discovery

```
User A imports 500 connections → enriched
User B imports 600 connections → enriched
User C imports 400 connections → enriched
         ...
Pool: 1,500 enriched professionals
         ↓
User A's goals scored against ENTIRE pool
         ↓
Matches found in User B's network
         ↓
"JuntoAI Network Match — a member can introduce you"
```

<br>

**Privacy:** Other users' connections appear as "JuntoAI Network Match" —
never reveals who imported them.

---

## The Matching Pipeline (7 Stages)

| Stage | What Happens |
|-------|-------------|
| 1. Import | LinkedIn DPA API → parse → deduplicate → store |
| 2. Tier 1 | Simple Dossier on ALL connections (batched) |
| 3. Filter | Score Tier 1 against user goals → top 20 |
| 4. Tier 2 | Full DossierAgent on top 20 (cache-aware) |
| 5. Cross-User | Query pool for matches NOT in user's network |
| 6. Final Rank | personalDNA vs user identity → top 5 + guidance |
| 7. Deliver | Admin approval → email with match cards |

<br>

**Total time: ~15 minutes per user.** All async.

---

## Communication Guidance: Per Match

A single Gemini call produces for each match:

<br>

1. **Conversation opener** — personalized to both parties
   *(their interests + your communication style)*

2. **Approach strategy** — 1-2 sentences on HOW to engage
   *(based on their values + your identity model)*

3. **Timing signal** — why NOW
   *(from public signals: recent talks, job changes, fundraising)*

<br>

> Not generic "you should connect" advice.
> Actionable, personalized, context-aware.

---

<!-- _class: lead -->
<!-- _backgroundColor: #0d0d0f -->

# Part 6
## Try It Yourself + Q&A

---

## Get Started: Open Source A2A

**Try it now:** [a2a.juntoai.org](https://a2a.juntoai.org/) — no setup needed

**Or run the full engine locally:**

```bash
git clone https://github.com/JuntoAI/JuntoAI-A2A.git
cd JuntoAI-A2A
docker compose up
# Open http://localhost:3000
```

<br>

- Works with Ollama (free, local), OpenAI, Anthropic, or any LiteLLM provider
- All 3 scenarios included — run them, flip toggles, see outcomes change
- **Challenge:** Write your own scenario JSON and submit a PR

---

## Build Your Own Scenario

```json
{
  "id": "your_scenario",
  "name": "Your Custom Negotiation",
  "agents": [
    { "role": "...", "persona_prompt": "...", "goals": [...] },
    { "role": "...", "persona_prompt": "...", "goals": [...] },
    { "role": "Regulator", "type": "regulator", ... }
  ],
  "toggles": [
    { "id": "...", "label": "...", "hidden_context_payload": {...} }
  ],
  "negotiation_params": {
    "max_turns": 12,
    "agreement_threshold": 5000,
    "turn_order": ["Agent1", "Regulator", "Agent2", "Regulator"]
  }
}
```

Drop it in `backend/app/scenarios/data/` → restart → it works.

---

## Network Matching Pilot: Be a Tester

We're looking for **5-10 people** to test the network matching system.

<br>

**What you'd get:**
- AI analysis of your LinkedIn connections
- Top 5 matches with personalized communication guidance
- Cross-network matches from other pilot participants

**What we'd learn:**
- Are the matches actually useful?
- Does communication guidance feel personalized?
- Is cross-user matching a "wow" moment?

<br>

**Interested?** → [sign-up link / QR code here]

---

## Key Takeaways

<br>

1. **State machines** make multi-agent interactions controllable
2. **Structured personas** create distinct, predictable agent behavior
3. **Config-driven design** lets you ship new scenarios without code
4. **The Regulator pattern** enables autonomous oversight
5. **One toggle** can reproducibly change outcomes — this is testable AI

<br>

> The same architecture that powers negotiation simulations
> will power real-world agent-to-agent matchmaking.

---

## Stop Building Chatbots. Start Building Agents.

<br>

| Chatbot | Agent |
|---------|-------|
| Answers questions | Pursues objectives |
| Stateless (each message = fresh) | Stateful (remembers, plans, adapts) |
| Serves one user | Interacts with other agents |
| You prompt it | It acts autonomously |
| Output: text | Output: decisions, deals, actions |

<br>

**Your challenge:**
1. Clone the repo → run a scenario → understand the architecture
2. Write YOUR own scenario JSON — a negotiation from your domain
3. Build an agent that acts on your behalf — not just responds to you

<br>

*The future isn't "ask AI a question." It's "give AI a goal and let it negotiate."*

---

## Resources & Contact

| | |
|--|------|
| 🔗 **Open Source Repo** | [github.com/JuntoAI/JuntoAI-A2A](https://github.com/JuntoAI/JuntoAI-A2A) |
| 🌐 **Live Demo** | [a2a.juntoai.org](https://a2a.juntoai.org/) |
| 📄 **Docs** | [github.com/JuntoAI/JuntoAI-A2A/docs](https://github.com/JuntoAI/JuntoAI-A2A/tree/main/docs) |
| 🧪 **Network Pilot** | Email markus@juntoai.org to join |

<br>

| | |
|--|------|
| **LinkedIn** | [linkedin.com/in/schmidberger](https://www.linkedin.com/in/schmidberger/) |
| **Email** | markus@juntoai.org |
| **JuntoAI** | [juntoai.org](https://juntoai.org) |

<br>

**Questions?**

---

<!-- _class: lead -->
<!-- _backgroundColor: #0d0d0f -->

# Q&A

### 15 minutes

<br>

*Seed questions if needed:*
- *How do you prevent agents from hallucinating during negotiations?*
- *What happens when the regulator disagrees with both parties?*
- *How does matching work with 50 connections vs 5,000?*
- *Can this work for non-English negotiations?*
