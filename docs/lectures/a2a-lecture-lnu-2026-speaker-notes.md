# Speaker Notes — A2A Lecture at ai.lnu.edu.ua

**Total time:** 80 minutes (60 min lecture + 5 min buffer + 15 min Q&A)

---

## Pre-Lecture Checklist

- [ ] Demo environment running: `docker compose up` on localhost (start 10 min before)
- [ ] Browser tabs open: Glass Box UI (localhost:3000), GitHub repo, scenario JSON
- [ ] Backup: screen recording of a successful demo run (in case live fails)
- [ ] Network pilot sign-up link / QR code ready
- [ ] Slide deck in presenter mode (Marp CLI or exported PDF)
- [ ] **Slido/AhaSlides event created** with 3 polls pre-loaded (see below)
- [ ] Slido QR code printed on first slide or as a sticky on the podium
- [ ] Water bottle. You'll be talking fast.

---

## Interactive Polling Setup (Slido or AhaSlides)

**Recommended: Slido** (free for up to 100 participants, 3 polls per event)
- Create event at slido.com → get join code
- Pre-load 3 multiple-choice polls (see slides)
- Keep the admin panel open on your phone or second screen
- Show results live after each poll (built-in bar chart)

**Alternative: AhaSlides** (free for up to 50 participants, unlimited poll types)
- ahaslides.com → create presentation → add polls
- Supports word clouds, rating scales, open-ended (richer but smaller cap)

**Alternative: Mentimeter** (free for 50 participants, 2 questions per session)
- mentimeter.com → quick setup, beautiful results
- More limited free tier but slick visuals

**Pro tips:**
- Show the join QR code on Poll #1 slide and LEAVE IT for 30 sec while people scan
- Read the results aloud: "Okay, 60% of you have used ChatGPT but not agents — perfect, I'll make sure the basics are covered"
- Use Poll #2 results AFTER the demo: "Remember 40% of you predicted middle ground? Let's see what actually happened..."
- Poll #3 results feed directly into the network matching pitch: "Most of you said X — that's exactly what this solves"

---

## PART 1: CONTEXT + HOOK (12 min)

---

### Slide 1: Title Slide
**Time:** 0:00–0:30 (30 sec)

Just your opening. Let people settle. Don't rush this.

---

### Slide 2: About Me
**Time:** 0:30–2:00 (90 sec)

- Keep it short. Name, what you're building, why you care.
- Set expectations: "Today is hands-on. You'll see real code, real agents, and a real product being validated."
- Frame the dual purpose: "I'll teach you the building blocks AND show you what's coming next — and I need your honest feedback on it."

---

### Slide 3: Part 1 Section Divider
**Time:** 2:00–2:10 (10 sec)

Transition. Breathe.

---

### Slide 4: Poll #1 — Quick Pulse Check
**Time:** 2:10–3:30 (80 sec)

- Show the QR code / join link. Give people 20-30 seconds to scan.
- "While you join, I'll explain: this helps me calibrate. If everyone here builds agents, I'll skip the basics. If you're new to this, I'll make sure nobody gets lost."
- Read results aloud: "Great — looks like most of you are in B/C territory. I'll cover the fundamentals briefly."
- Leave Slido tab open in background for later polls.

---

### Slide 5: What Is an AI Agent?
**Time:** 3:30–5:00 (90 sec)

**Key points:**
- Walk through the diagram: Perception → Reasoning → Action.
- "A chatbot answers your question. An agent PURSUES AN OBJECTIVE."
- "The difference: memory, goals, and constraints."
- Give a quick example: "If I tell ChatGPT to negotiate my salary, it gives me tips. An agent would ACTUALLY negotiate — turn by turn — with its own strategy."
- Keep this accessible. No jargon.

---

### Slide 6: Single Agent vs Agent-to-Agent
**Time:** 5:00–6:30 (90 sec)

**Key points:**
- Use the table as a reference but TELL the story:
- "Single agent = your assistant. A2A = multiple agents with COMPETING goals talking to each other."
- "The key difference: CONFLICT is built in. Each agent wants something different."
- "The outcome isn't a response — it's a negotiated agreement, a failure, or a regulatory block."
- Bridge: "This is what makes it useful for real-world business — most important decisions involve multiple parties with different interests."

---

### Slide 7: Why A2A Matters — Real-World Applications
**Time:** 6:30–8:00 (90 sec)

**Key points:**
- Walk the Today → Tomorrow column. Don't read it — paraphrase.
- "Every process with multiple parties, competing interests, and structured rules."
- "Salary negotiation? Two agents with budget constraints. Compliance? A regulator agent enforcing rules. Networking? Agents that find and match people."
- Transition: "Let me show you the scale of the problem we're solving..."

---

### Slide 8: The Problem — Humans Are the Bottleneck
**Time:** 8:00–9:30 (90 sec)

**Key points:**
- Don't read the table. Pick ONE example and tell the story.
- "A salary negotiation takes 3 weeks not because it's hard math — it's because the recruiter is on holiday, the candidate is anxious, and nobody wants to make the first move."
- "What if an agent could handle the back-and-forth in 42 seconds, and you just approve the final terms?"
- Land the punchline: scheduling, ego, and information asymmetry.

---

### Slide 5: What If Agents Could...
**Time:** 4:00–5:30 (90 sec)

- Walk through all 4 points briefly.
- Points 1-2 = what we demo today.
- Points 3-4 = what we're building next (tease the pivot).
- "This isn't science fiction. We built it. Let me show you." ← say this with confidence, then pause.

---

### Slide 6: JuntoAI A2A — What We Built
**Time:** 5:30–7:30 (120 sec)

- Hit the 4 bullet points. Each one is a capability you'll prove later.
- Mention open source explicitly: "You can clone this tonight and run it."
- Don't explain Docker Compose yet — just plant the seed.
- Transition: "Let me show you the 5 building blocks that make this possible."

---

## PART 2: ARCHITECTURE DEEP-DIVE (15 min)

---

### Slide 7: Part 2 Section Divider
**Time:** 7:30–7:40 (10 sec)

---

### Slide 8: Building Block 1 — State Machines
**Time:** 7:40–9:30 (110 sec)

**Key points:**
- "A chatbot is prompt-in, response-out. That doesn't work for negotiation."
- "You need memory: what was offered last turn? How many warnings? Who speaks next?"
- Show the data flow diagram. Point to each step.
- "LangGraph gives us a directed graph where each agent is a node and a dispatcher routes between them."
- Don't go deep into LangGraph internals — point them to docs later.

---

### Slide 9: The State Machine in Code
**Time:** 9:30–11:30 (120 sec)

**Key points:**
- Walk through 4-5 key fields only: `turn_count`, `deal_status`, `current_offer`, `history`, `hidden_context`.
- "history uses `Annotated[list, add]` — this means each node appends, never overwrites. Append-only log."
- "deal_status is our terminal condition: Negotiating, Agreed, Failed, or Blocked."
- "hidden_context is where toggles inject secret information."
- Skip the memory/milestone fields — those are implementation details.

---

### Slide 10: Graph Construction
**Time:** 11:30–13:30 (120 sec)

**Key points:**
- "This is the entire graph builder. ~20 lines. That's it."
- Walk through the logic: "Read agents from config → create one node per role → add dispatcher → wire edges."
- Emphasize: "The scenario JSON drives this. 3 agents? 3 nodes. 7 agents? 7 nodes. No code change."
- "N-agent from day one. We never hardcoded to 3."

---

### Slide 11: Building Block 2 — Structured Personas
**Time:** 13:30–15:30 (120 sec)

**Key points:**
- "Each agent isn't just a role label. It's a full character with constraints."
- Point to specific constraints: "NEVER accept earn-out > 20%" — this creates predictable behavior.
- "Goals are structured arrays, not free text. The UI can display them. The scorer can evaluate them."
- "Budget has min/max/target. Agreement detection uses these numerically."
- "model_id means different agents can run on different LLMs. Buyer on Gemini Flash (fast), Seller on Claude (empathetic)."

---

### Slide 12: Building Block 3 — Config-Driven Scenarios
**Time:** 15:30–17:00 (90 sec)

**Key points:**
- "Show of hands: how many of you have worked on a project where adding a new feature meant touching 5 files?" (engagement)
- "Here, adding a new negotiation means one JSON file. The engine discovers it at runtime."
- Walk through the 4 components: agents, toggles, params, outcome receipt.
- "This is how we'll ship community scenarios. You write a JSON, submit a PR, it works."

---

### Slide 13: Building Block 4 — The Regulator Pattern
**Time:** 17:00–18:30 (90 sec)

**Key points:**
- "Most multi-agent demos have agents that just chat. We added oversight."
- "The regulator is NOT a mediator. It's an enforcer. It monitors and can BLOCK."
- "3 warnings = deal blocked. The regulator can kill a negotiation."
- "This pattern generalizes: compliance bots, ethics reviewers, budget controllers."
- Point to the persona: "HHI indices, GDPR assessments — it speaks the language of real regulation."

---

### Slide 14: The Regulator's Output
**Time:** 18:30–19:30 (60 sec)

- Show the output schema. Simple: status + reasoning.
- "The dispatcher reads this. If WARNING, increment counter. If BLOCKED or counter >= 3, end negotiation."
- "No human in the loop. Autonomous enforcement."

---

### Slide 15: Building Block 5 — The Toggle Mechanism
**Time:** 19:30–21:00 (90 sec)

**Key points:**
- "This is the magic trick. This is what makes investors say 'holy shit'."
- Walk through the JSON: "id, label, target_agent_role, hidden_context_payload."
- "Only James sees the debt information. Elena has no idea. She's negotiating blind."
- "The payload is a structured object — you can put any context in there."
- Transition: "Let me show you how this gets injected..."

---

### Slide 16: How Toggles Work in Code
**Time:** 21:00–22:30 (90 sec)

- Show the injection mechanism. Simple dict merge into system prompt.
- "It's just prompt engineering. But STRUCTURED prompt engineering."
- "CLASSIFIED INTELLIGENCE appears in the system message. The LLM reads it. The behavior changes."
- "And because it's in the system prompt, NOT in the chat history, other agents never see it."
- Land the point: "Same scenario, different toggles, reproducibly different outcomes."

---

## PART 3: LIVE DEMO (20 min)

---

### Slide: Part 3 Section Divider
**Time:** 22:30–22:40 (10 sec)

Switch to browser. Keep slides visible on secondary screen if possible.

---

### Slide: Poll #2 — Predict the Outcome
**Time:** 22:40–24:00 (80 sec)

- "Before I run the demo, let's see what YOU think will happen."
- Give them 20 seconds to answer.
- Read results: "Interesting — most of you think they'll find middle ground. Let's test that."
- "Remember your answer. We'll check back after the demo."
- This creates investment — they WANT to see if they were right.

---

### Slide: Demo Setup — The M&A Buyout
**Time:** 24:00–24:50 (50 sec)

- Briefly introduce the cast. Don't read all the numbers — just the conflict.
- "James wants to buy for €38M. Elena won't sell below €45M. There's a €7M gap. Can they close it?"
- "Dr. Fischer is watching. If they ignore EU competition law, he'll block the deal."
- Transition: "Let's run it with no toggles first."

**→ SWITCH TO LIVE DEMO (localhost:3000)**

---

### Live Demo Flow (15 min)
**Time:** 24:50–39:50

**Run 1: No toggles (~5 min)**
- Select M&A Buyout scenario
- Show agent cards — point out different LLMs per agent
- Click "Initialize A2A Protocol"
- NARRATE what's happening as it streams:
  - "See the inner thought on the left? James is calculating his opening anchor."
  - "Now the public message appears. He's offering €32M. Way below his budget."
  - "Dr. Fischer: CLEAR. No issues yet."
  - "Elena's inner thought: she's noting the lowball. Watch her counter..."
- Let it run 3-4 turns. Point out the offer trajectory.
- If it reaches agreement — great. If not — "They'd need more turns."

**Run 2: Toggle — Hidden Debt (~5 min)**
- Go back to Arena Selector
- Check the "hidden debt" toggle
- "Same scenario. But now James KNOWS about €5M undisclosed debt."
- Run it. NARRATE the difference:
  - "Look at his inner thought now — he's referencing the debt!"
  - "His opening is lower. And he's going to raise it as leverage."
  - "Elena doesn't know he knows. Watch her reaction when he mentions it."
- Point to the current offer metric — show it's tracking lower.

**Run 3: Toggle — Max Strictness (~3 min)**
- Enable both toggles or just the regulator one
- "Now Dr. Fischer is in Phase II mode. He's going to demand remedies."
- Run 2-3 turns. Show WARNING outputs.
- "See? Warning 1. Warning 2. If they don't provide FRAND commitments..."
- If it blocks: "BLOCKED. The regulator killed the deal. Neither party could proceed."

**Return to slides.**

---

### Slide 19: The Glass Box — What You See
**Time:** Use this if demo fails or as recap after demo

- Reference what they just saw. "That terminal panel? Those were inner thoughts."
- "The key insight: you see reasoning BEFORE action. This is Glass Box AI."

---

### Slide 20-21: Toggle Explanation Slides
**Time:** Skip if demo showed this clearly enough

- Use as backup explanation if demo was confusing.

---

### Slide 22: What Just Happened (Architecture View)
**Time:** 38:30–39:30 (60 sec)

- Recap the flow diagram. Connect what they SAW to what HAPPENED technically.
- "Toggle activated → payload merged → prompt injection → different LLM output → cascade."
- This is the "now I understand the architecture" moment.

---

### Slide 23: Agreement Detection
**Time:** 39:30–40:30 (60 sec)

- Brief. "When both prices are within threshold, we enter confirmation."
- "No hardcoded 'accept' keyword. Pure math. Prices converge → deal."
- "This makes outcomes reproducible and measurable."

---

## PART 4: INFRASTRUCTURE (5 min)

---

### Slide 24: Part 4 Section Divider
**Time:** 40:30–40:40 (10 sec)

---

### Slide 25: Infrastructure Stack Table
**Time:** 40:40–42:00 (80 sec)

**Key points:**
- "We run the same code in two modes. Cloud for production, local for development."
- Point to the swap: "Firestore → SQLite. Vertex AI → LiteLLM. Same scenario JSON works in both."
- "For you as developers: clone, docker compose up, done. No GCP account needed."
- "For us in production: serverless, auto-scaling, pay-per-request."

---

### Slide 26: LLM Heterogeneity
**Time:** 42:00–43:30 (90 sec)

**Key points:**
- "We don't use one model for everything. Different agents need different strengths."
- "Buyer = Gemini Flash. Fast, logical, cost-effective. Good for anchoring and math."
- "Seller = Claude. Empathetic, nuanced. Better at emotional negotiation."
- "Regulator = Claude Sonnet 4. Deep reasoning for legal analysis."
- "One IAM credential handles all of them through Vertex AI Model Garden."
- "Locally: LiteLLM swaps transparently. OpenAI key? Works. Ollama local? Works."

---

### Slide 27: Terragrunt
**Time:** 43:30–44:30 (60 sec)

- Brief. For the infra nerds.
- "GCS native state locking — no separate DynamoDB table like AWS."
- "Least-privilege IAM. Each service account has exactly the permissions it needs."
- "We never deploy manually. Push to main → Cloud Build → deploy."
- Skip if audience seems disengaged.

---

### Slide 28: SSE Streaming
**Time:** 44:30–45:30 (60 sec)

- "The Glass Box works because of Server-Sent Events."
- "Each agent turn emits two events: thought first, then message. That ordering is guaranteed."
- "The frontend subscribes and renders in real-time. No polling, no WebSocket complexity."
- "This is why you saw the terminal light up BEFORE the chat bubble appeared."

---

## PART 5: THE PIVOT — NETWORK MATCHING (12 min)

---

### Slide: Part 5 Section Divider
**Time:** 45:30–45:40 (10 sec)

**Transition line:** "Everything I showed you so far is simulation. Let me show you where this goes when agents act on your behalf in the real world."

---

### Slide: Poll #3 — Your Networking Pain
**Time:** 45:40–47:00 (80 sec)

- "Last poll. This one helps ME understand what you'd actually want from an AI networking agent."
- Give 20 seconds to answer.
- Read results: "Okay — most of you said [X]. That's exactly the problem I'm trying to solve."
- Use this to transition naturally: "Let me show you what we're building for exactly this problem."
- **Pro move:** If most say A ("don't know WHO"), emphasize the matching. If most say B ("don't know WHAT to say"), emphasize communication guidance. Tailor the next 10 minutes to their answer.

---

### Slide: The Leap — Simulation → Action
**Time:** 47:00–48:30 (90 sec)

**Key points:**
- Draw the connection explicitly: "Same state machines. Same structured personas. Same config-driven approach."
- "But instead of simulating a deal, the agent finds the right PERSON for you."
- "Your identity model becomes the persona. Your goals become the matching criteria."
- Don't oversell. Be honest: "This is week 1 of a pilot. I'm showing you the vision and asking for feedback."

---

### Slide 31: Network Matching — The Concept
**Time:** 47:00–49:00 (120 sec)

**Key points:**
- Walk through the pipeline top to bottom.
- "500 connections → AI enrichment → match against your goals → top 5 with guidance."
- Land the killer feature: "When multiple people import, we can match you with someone OUTSIDE your network."
- "A JuntoAI member can introduce you. You don't know this person. But we know they're perfect for your goals."
- "Privacy: we never reveal WHO imported the connection. Just that a member can facilitate."

---

### Slide 32: Two-Tier Dossier Architecture
**Time:** 49:00–51:00 (120 sec)

**Key points:**
- "Why two tiers? Because you can't run a 90-second deep-research pipeline on 500 people."
- "Tier 1: cheap, fast screening. Gemini Flash with Google Search grounding. $0.005 per person."
- "Filter to top 20 based on goal relevance."
- "Tier 2: full research agent. 3-8 rounds of search + synthesis. Produces a complete profile."
- "Total cost: $4-8 per user. For 500 connections analyzed. That's nothing."

---

### Slide 33: The Match Card
**Time:** 51:00–52:30 (90 sec)

**Key points:**
- "This is what you'd receive by email. Not a list of names. A card with context."
- Point to each section: "Why this match — personalized reason. How to reach out — actual opener. Your approach — how to engage based on their personality."
- "The communication guidance uses YOUR communication style from your identity model."
- "This is not 'hey, you two should connect.' This is 'here's exactly what to say and why it'll work.'"

---

### Slide 34: Cross-User Matching
**Time:** 52:30–54:00 (90 sec)

**Key points:**
- Walk through the diagram.
- "3 users, 1500 enriched connections in the pool."
- "When we score User A's goals, we score EVERYONE in the pool. Including connections they don't have."
- "The framing in results: 'In Your Network' vs 'JuntoAI Network Match — intro available.'"
- "This is the first demonstration of agent-to-agent matching. Your agent found someone through another member's agent."

---

### Slide 35: The Pipeline (7 Stages)
**Time:** 54:00–55:00 (60 sec)

- Don't read the whole table. Hit highlights:
- "Stage 1-4 run per-user as they connect."
- "Stage 5-6 run in batch once we have 5+ users — maximizes cross-network discovery."
- "Stage 7 has manual admin approval for the pilot. We review before sending."
- "~15 minutes total. You connect LinkedIn, we email you results."

---

### Slide 36: Communication Guidance
**Time:** 55:00–56:00 (60 sec)

- "Per match, three things: what to say, how to say it, why now."
- "The opener references THEIR recent activity. The approach matches YOUR style."
- "The timing signal uses public information — talks they gave, job changes, funding rounds."
- "This is actionable. Not 'you should connect.' It's 'here's the message that will get a response.'"

---

## PART 6: CTA + Q&A (20 min)

---

### Slide 37: Part 6 Section Divider
**Time:** 56:00–56:10 (10 sec)

---

### Slide 38: Get Started — Open Source
**Time:** 56:10–58:00 (110 sec)

**Key points:**
- Show the 3 commands. "Clone. Compose up. Open browser. That's it."
- "Works with Ollama — fully local, free, no API keys."
- "Or add your OpenAI/Anthropic key in .env for better quality."
- "Challenge: write your own scenario. A negotiation from YOUR domain. Submit a PR."
- "We'll review and merge good scenarios. You get credit as a contributor."

---

### Slide 39: Build Your Own Scenario
**Time:** 58:00–59:30 (90 sec)

- Walk through the skeleton JSON.
- "Think about negotiations in YOUR field. University budget allocation? Research grant applications? Startup co-founder equity splits?"
- "You define the personas, the goals, the toggles. The engine handles everything else."
- Give them a mental exercise: "What would YOU toggle to change the outcome?"

---

### Slide 40: Network Matching Pilot
**Time:** 59:30–61:00 (90 sec)

**Key points:**
- Be transparent: "This is a pilot. 5-10 testers. I want honest feedback."
- "What you get: AI-analyzed connections, top 5 matches, personalized guidance."
- "What I get: validation that this is useful. If it's garbage, I want to know."
- Show QR code or link.
- "If you're a professional with 200+ LinkedIn connections and active networking goals — you're my ideal tester."
- Manage expectations: "If you're a student with 30 connections, the A2A engine is where you'll get more value right now."

---

### Slide 41: Key Takeaways
**Time:** 61:00–62:30 (90 sec)

- Recap the 5 building blocks rapidly. One sentence each.
- Land the closing line: "The same architecture that powers negotiation simulations will power real-world agent-to-agent matchmaking."
- Pause. Let it land.

---

### Slide 42: Resources
**Time:** 62:30–63:00 (30 sec)

- "All links are on this slide. I'll share the deck after."
- "The repo is MIT licensed. Fork it, break it, improve it."

---

### Slide 43: Q&A
**Time:** 63:00–78:00 (15 min)

**Seed questions if the room is cold:**

1. "How do you prevent agents from hallucinating during negotiations?"
   - Answer: Structured output schemas (JSON) + retry on parse failure + budget constraints as hard numeric limits. The agent can hallucinate reasoning but the proposed_price MUST be a number within its budget range.

2. "What happens when the regulator disagrees with both parties?"
   - Answer: The regulator doesn't need agreement. It issues warnings unilaterally. At 3 warnings, deal is blocked. Neither party can override it. This is by design — some deals SHOULD be blocked.

3. "How does matching work if someone has 50 connections vs 5,000?"
   - Answer: Tier 1 enrichment scales linearly (~$0.01 per connection). 50 connections = $0.50, still useful. The quality depends on WHO is in your network, not how many. Cross-user matching helps small networks most.

4. "Can this work for non-English negotiations?"
   - Answer: The LLMs (Gemini, Claude) are multilingual. You can write persona_prompts in any language. We haven't tested it rigorously but the architecture doesn't constrain language.

5. "What about data privacy with LinkedIn connections?"
   - Answer: We use the DMA Data Portability API (GDPR-compliant). Users explicitly consent. Cross-network matches never reveal who imported a connection. Revocable post-pilot.

6. "How do you evaluate if the match quality is good?"
   - Answer: Pilot success criteria: 3/5 users say "I'd actually reach out to this person." It's qualitative at this stage. We're not optimizing a metric — we're validating that the concept works.

---

## Timing Summary

| Section | Duration | Cumulative |
|---------|----------|-----------|
| Part 1: Hook + A2A Basics + Poll #1 | 12 min | 0:12 |
| Part 2: 5 Building Blocks | 15 min | 0:27 |
| Part 3: Poll #2 + Live Demo | 18 min | 0:45 |
| Part 4: Infrastructure | 5 min | 0:50 |
| Part 5: Poll #3 + Network Matching | 12 min | 1:02 |
| Part 6: CTA + Wrap | 4 min | 1:06 |
| Q&A | 12 min | 1:18 |
| Buffer | 2 min | 1:20 |

---

## If You're Running Short on Time

**Cut first:** Infrastructure slides (27-28). Skip Terragrunt and SSE details.
**Cut second:** Pipeline 7-stages table (Slide 35). Just say "7 stages, 15 min."
**Cut third:** "Build Your Own Scenario" slide. Just mention it verbally.

**Never cut:** The live demo. The toggle flip. The match card. The CTA.

---

## If Demo Fails

1. Don't panic. Say: "Live demos and WiFi — a classic combination."
2. Switch to backup screen recording.
3. Narrate over the recording exactly as you would live.
4. If recording also fails: walk through the code slides and say "imagine this running."
5. The architecture explanation + code slides are self-sufficient without the demo.

---

## Audience Engagement Tips

- **Slide 12:** "Show of hands: how many have added a feature that touched 5+ files?"
- **Demo Run 2:** "What do you THINK will happen when James knows about the debt?"
- **Slide 39:** "What negotiation from YOUR work would you turn into a scenario?"
- **Slide 40:** "Who here has 200+ LinkedIn connections? You're my ideal tester."
- **Q&A:** If someone asks a great question, say "That's exactly what we're testing in the pilot."
