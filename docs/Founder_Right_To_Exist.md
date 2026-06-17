# JuntoAI A2A — The "Right to Exist" Test

**Date:** May 2026  
**Purpose:** Can we answer the six questions every founder must answer clearly? Brutally honest self-assessment.

---

## 1. Whose Pain, and How Badly?

### The Honest Answer: This Is Where We're Weakest.

Let me try to name three specific humans who would pay cash today:

**Person A: Head of Sales Enablement at a mid-market SaaS company (200-500 employees)**
- They spend $50K–$150K/year on negotiation training (Sandler, SPIN, Challenger Sale workshops)
- Their reps still lose deals because they can't practice against realistic counterparties
- Role-play with managers is awkward, infrequent, and doesn't scale

**Would they pay for JuntoAI today?** Honestly — probably not. They'd need:
- Custom scenarios matching THEIR sales motion (not generic M&A/HR)
- Integration with their CRM to pull real deal context
- Analytics proving rep performance improved
- We have NONE of this. We have 3 pre-built scenarios and a token limit.

**Person B: Procurement Director at a Fortune 500 managing 5,000+ suppliers**
- They negotiate thousands of contracts/year
- Only top 20% of suppliers get human attention; the "long tail" gets ignored
- Leaving 3-7% savings on the table across unmanaged spend

**Would they pay for JuntoAI today?** No. Pactum already does this, has $54M in funding, and has Walmart as a client. We're not even in the same conversation. We'd need to pivot from "demo sandbox" to "production negotiation tool" — which is a completely different product.

**Person C: AI Safety Researcher at a lab or university**
- They need controlled environments to test agent behavior under adversarial conditions
- They want to observe how information asymmetry affects AI decision-making
- Current tools are ad-hoc scripts and custom harnesses

**Would they pay for JuntoAI today?** Maybe $50/month for a research tool. Not enterprise money. And they'd want API access, not a pretty UI. The Glass Box visualization is actually compelling for this use case, but the market is tiny and doesn't scale to venture returns.

### The Brutal Truth

**We cannot clearly name three humans who would pay cash today.** We have a product that impresses people in demos but doesn't solve a daily, urgent, expensive problem for a specific buyer. The pain we address is diffuse:
- "Negotiation is hard" → True, but people have been negotiating for millennia without AI sandboxes
- "AI agents need testing" → True, but researchers build their own tools
- "Sales teams need practice" → True, but they buy from established training vendors

**Severity of pain: 3/10.** Nobody is losing sleep over the absence of an AI negotiation sandbox. This is a "nice to have," not a "hair on fire" problem.

---

## 2. How Are They Solving This Today?

### Sales Training / Negotiation Practice
- **Workshops:** $2K–$10K per session. Sandler Training, Scotwork, The Gap Partnership. Fly in a trainer, do 2-day intensive, forget 80% within a month.
- **Role-play with managers:** Scheduled 1:1s where a sales manager pretends to be a difficult buyer. Awkward. Inconsistent. Manager has 15 other reps to coach.
- **Recorded call review:** Gong, Chorus.ai analyze past calls. Retrospective only — you can't practice BEFORE the call.
- **Nothing:** Most reps just wing it. They learn by losing deals.

### Procurement Negotiation
- **Spreadsheets + email:** Procurement teams literally email suppliers with counter-offers, track responses in Excel, and manually follow up. For the long tail of suppliers, they just accept the first quote.
- **eSourcing platforms:** Coupa, SAP Ariba, Jaggaer run structured RFx events. These are auction-style, not conversational negotiation.
- **Pactum:** The only real AI negotiation tool in production. Chatbot-style supplier engagement at scale.

### AI Agent Testing / Research
- **Custom Python scripts:** Researchers write bespoke harnesses using raw API calls.
- **AutoGen/CrewAI notebooks:** Jupyter notebooks with ad-hoc multi-agent setups. No persistence, no visualization, no reproducibility.
- **Nothing standardized:** There is no "Postman for AI agent interactions." This is genuinely underserved — but it's a developer tool market, not an enterprise SaaS market.

### The Unflattering Detail

The status quo for negotiation training is: **a $5K workshop once a year + hoping reps figure it out.** It's bad. But it's also "good enough" for most companies. The switching cost to adopt an AI simulation platform is HIGH (new vendor evaluation, budget approval, change management, proving ROI) and the perceived urgency is LOW (reps are already closing some deals).

For procurement: Pactum exists and works. We're not offering anything better for that use case.

For AI research: The status quo is messy but functional. Researchers are comfortable with code. A pretty UI doesn't solve their core problem (which is evaluation methodology, not visualization).

---

## 3. Why Is Your Version 10x Better, Not 10% Better?

### What We Claim Is 10x

"Our Glass Box shows AI reasoning in real-time. You can see WHY the agent made a decision, toggle hidden information, and watch behavior change instantly. No other tool does this."

### The Honest Assessment: Is This Actually 10x?

**Compared to sales role-play with a manager:** 
- Available 24/7 vs. scheduled sessions ✓ (that's maybe 3x)
- Infinite patience, never gets tired ✓ (2x)
- Can simulate scenarios you'd never encounter in practice ✓ (2x)
- Shows you the counterparty's INNER THINKING ✓ (this is genuinely novel — you can't read your manager's mind during role-play)

**The "inner monologue visibility" is the only truly 10x element.** Everything else is incremental improvement over existing solutions. But here's the problem: seeing an AI's inner monologue is fascinating for a DEMO but unclear if it's useful for TRAINING. Does watching an AI think make a human negotiate better? We don't know. We haven't tested this hypothesis with actual sales reps.

**Compared to Pactum (for procurement):**
We're not 10x better. We're not even 1x. They have production-grade autonomous negotiation with real suppliers. We have a sandbox with fake scenarios.

**Compared to custom research scripts (for AI safety):**
- Visual Glass Box vs. terminal output ✓ (5x better UX)
- Config-driven scenarios vs. writing code ✓ (3x faster setup)
- Reproducible with toggles vs. ad-hoc ✓ (genuinely useful)

This might actually be 10x for the AI research use case — but that's our smallest, lowest-revenue market.

### The Uncomfortable Conclusion

**We don't have a clear 10x for our primary target market because we don't have a clear primary target market.** The 10x story changes depending on who we're talking to, which means we haven't found product-market fit.

A real 10x would be: "Sales reps who practice with JuntoAI close 40% more deals." We can't say that. We haven't measured it. We don't even have the product features (custom scenarios, CRM integration, performance analytics) that would make that measurement possible.

---

## 4. Why Now — And Why Hasn't Somebody Already Won This?

### Our "Why Now" Claim

1. **LLMs can finally negotiate convincingly** (GPT-4/Claude/Gemini-class models, 2023+)
2. **Multi-agent frameworks matured** (LangGraph, CrewAI hit production-ready in 2024-2025)
3. **Anthropic's Project Deal proved agent-to-agent commerce works** (April 2026)
4. **AI agent market exploding** ($7.8B → $52.6B by 2030, 46% CAGR)

### Is This Actually a Good "Why Now"?

**Partially.** The technology enabler is real — you couldn't build this product in 2022. LLMs weren't good enough at maintaining persona, following complex instructions, or generating strategic reasoning. Now they are.

**But "AI exists now" is not a defensible "why now."** Every AI startup says this. It's table stakes, not differentiation.

**A BETTER "why now" would be:**
- A regulatory change forcing companies to document negotiation processes (doesn't exist yet)
- A behavioral shift where enterprises are ALREADY buying AI agent tools (happening, but for customer service, not negotiation)
- A specific cost crisis making manual negotiation unsustainable (procurement teams are stretched thin — this is real but Pactum already addresses it)

### Why Hasn't Somebody Already Won This?

**Honest answer: Because the market might not exist.**

- Pactum won the "AI negotiates with humans" market
- Nobody has won the "AI negotiates with AI as a product" market because it's unclear who the customer is
- The "negotiation training via AI simulation" market is emerging but unproven — companies like Second Nature AI and Hyperbound are attacking sales role-play specifically, and they're further along

**The reason nobody has won "AI-vs-AI negotiation sandbox" is possibly because it's not a business — it's a research demo.** That's the scariest answer, and we need to disprove it with customer evidence.

---

## 5. Why You? (Asymmetric Insight or Edge)

### What We'd Like to Say

"We understand that the future of business is AI agents negotiating with AI agents, and we're building the protocol layer for that future."

### The Honest Assessment

**What's our actual edge if we gave this idea to ten other competent founders?**

Let me be real about what we have and don't have:

**We DON'T have:**
- Domain expertise in procurement, sales, or negotiation theory (or do we? If we do, lead with it)
- A proprietary dataset of negotiation outcomes
- Relationships with enterprise buyers
- A patent or trade secret
- Distribution (no existing user base)
- A unique technical breakthrough (LangGraph + LLMs is public knowledge)

**We MIGHT have:**
- First-mover advantage in "Glass Box" visualization for multi-agent systems (but this is a UX choice, not a moat)
- The N-agent architecture designed from day one (good engineering, but replicable)
- A working product while others are still theorizing (execution speed matters at pre-seed)

**The real question:** What do the founders know that others don't?

Possible asymmetric insights (pick the one that's TRUE for your team):
1. "We've personally experienced the pain of failed negotiations in [specific context] and know exactly what information would have changed the outcome" → This is a founder-market fit story
2. "We have a background in game theory / mechanism design that lets us build scenarios that reliably produce interesting outcomes" → This is a technical edge
3. "We have relationships with [specific enterprise buyers] who've told us they'd pay for this" → This is a distribution edge
4. "We've discovered that [specific LLM prompting technique] makes agent negotiation 10x more reliable than naive approaches" → This is a know-how edge

**If none of these are true, we don't have a "why you" answer.** And that's a problem. Investors fund teams with unfair advantages, not teams that executed a good idea first.

---

## 6. Will They Pay — And Will They Keep Paying?

### Current Revenue Model

- **Cloud mode:** 100 free tokens/day per email. No paid tier exists yet.
- **Local mode:** Completely free. Bring your own API keys.
- **Revenue today:** $0.

### The Revenue Quality Problem

**Even if we add a paid tier, what does retention look like?**

**Scenario A: "Pay per simulation" (transaction model)**
- User pays $X to run a negotiation scenario
- Problem: One-time curiosity. They run it 5 times, see the patterns, never come back.
- Retention: Terrible. This is a novelty, not a workflow tool.
- Revenue quality: LOW (one-time transactions, no recurring need)

**Scenario B: "Monthly subscription for sales teams" (SaaS model)**
- $99/seat/month for unlimited practice scenarios
- Problem: Need custom scenarios, analytics, CRM integration, admin dashboard — none of which exist
- Retention: Could be good IF we prove training efficacy. But we're 12+ months of product development away from this.
- Revenue quality: POTENTIALLY HIGH (if we build the product)

**Scenario C: "Enterprise platform for procurement" (Pactum competitor)**
- $100K+/year for autonomous supplier negotiation
- Problem: We'd need to completely pivot from "demo sandbox" to "production tool." Different product, different team, different sales motion.
- Retention: High (procurement is ongoing), but we're years behind Pactum.
- Revenue quality: HIGH (but unrealistic for us today)

**Scenario D: "Developer platform" (usage-based)**
- Pay per API call for orchestrated multi-agent negotiations
- Problem: Developers can use LangGraph directly for free. Why pay us?
- Retention: Only if we provide value above raw framework (hosted infra, analytics, scenario marketplace)
- Revenue quality: MEDIUM (usage-based can be volatile)

### The Honest Answer

**We don't know if they'll pay because we haven't asked them to.**

We've built a gated demo with a token limit, but the token limit is for COST CONTROL, not monetization. There's no pricing page. No "upgrade to Pro" button. No enterprise sales conversation.

**Will they keep paying?** We can't answer this because:
1. We don't have paying customers
2. We don't have usage data showing repeat engagement
3. We don't have a product that solves a recurring problem (running the same 3 scenarios gets old fast)

**The retention killer:** Our product has a natural "completion" moment. You run the scenarios, you see how toggles work, you're impressed, you're done. There's no ongoing workflow that brings you back daily. Compare this to:
- Slack (daily communication need)
- Gong (every sales call generates new data)
- Pactum (thousands of suppliers to negotiate with continuously)

**We need to find the "infinite game" — the reason someone opens JuntoAI every week.** Right now, we don't have one.

---

## Summary: The Verdict

| Question | Can We Answer It? | Grade |
|----------|------------------|-------|
| Whose pain, how badly? | Vaguely. No specific buyer with urgent pain. | D |
| How do they solve it today? | Yes, we understand the status quo. | B |
| Why 10x better? | Only for the "inner monologue visibility" angle, and only for training use case. | C- |
| Why now? | Technology enabler is real, but "AI exists" isn't differentiated. | C |
| Why you? | Unclear. No obvious asymmetric advantage articulated. | D |
| Will they pay & keep paying? | Unknown. No revenue model tested. No retention data. | F |

### What This Means

**We are not ready for a fundraise.** We have a technically impressive demo that proves a concept, but we cannot clearly articulate:
- Who the customer is
- Why they'd pay
- Why they'd keep paying
- Why we're the team to win this

### What Would Change the Grade to an A

1. **Find 5 enterprise buyers who say "I'd pay $X/month for this if it had Y feature"** — then build Y.
2. **Run a paid pilot** — even at $500/month with one company. Revenue > $0 changes everything.
3. **Prove training efficacy** — "Reps who used JuntoAI improved close rate by X%" is a fundable thesis.
4. **Articulate the founder edge** — What do you know that Pactum's team doesn't? What have you lived that makes you the inevitable winner?
5. **Show retention** — Even with free users, show that people come back weekly. If they don't, the product isn't sticky enough to monetize.

---

*This document is intentionally harsh. The goal is to find the gaps BEFORE an investor finds them for you. Every weakness identified here is a weakness you can fix — or at minimum, have a prepared answer for.*
