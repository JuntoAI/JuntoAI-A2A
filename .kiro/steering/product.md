# JuntoAI A2A MVP — Product Context

## What We're Building
A **Config-Driven Scenario Engine** that visually proves JuntoAI is a universal, protocol-level execution layer for professional negotiations. Not a chatbot. A "blank stage" where AI agents negotiate autonomously while investors watch the reasoning in real time.

## The Investor "Aha!" Moment
Changing a single hidden toggle (e.g., giving an agent a secret competing offer) must **visibly and reliably** alter the AI's reasoning and final deal outcome.

## Core User Flow (4 Screens)
1. **Landing Page** → Value prop + email waitlist gate (mandatory lead capture)
2. **Arena Selector** → Scenario dropdown, agent cards, information toggles, "Initialize A2A Protocol" CTA
3. **Glass Box** → Live split-screen: terminal (inner thoughts) | chat (public messages) | metrics dashboard
4. **Outcome Receipt** → Final terms, ROI metrics, "Run Another" / "Reset with Different Variables" CTAs

## Key Product Rules
- 100 tokens/day per email, server-side enforced, resets at midnight UTC
- N-agent architecture from day one — nothing hardcoded to 3 agents
- New scenarios added by dropping a JSON file, zero code changes
- Inner thoughts stream BEFORE public messages (proves sequential reasoning)
- Regulator: 3 warnings = deal blocked

## MVP Ships With 3 Scenarios
- **Talent War** — HR salary/remote negotiation (Recruiter vs Candidate + HR Compliance)
- **M&A Buyout** — Corporate acquisition (Buyer CEO vs Founder + EU Regulator)
- **B2B Sales** — SaaS contract negotiation (Account Exec vs CTO + Procurement Bot)

## Definition of Done
1. 4th scenario works by uploading a new JSON file — no code changes
2. Waitlist gates access, captures email, enforces 100-token daily limit
3. Inner monologue streams before public message in the UI
4. Toggles reliably alter negotiation outcome ≥90% of the time
5. Agents reach agreement, failure, or regulator block — never infinite loop

## Open-Source Battle Arena (Local Mode)
- Public repo, developers clone and run `docker compose up` — full stack on localhost
- SQLite replaces Firestore for local mode (zero cloud config)
- LiteLLM for provider-agnostic LLM routing (OpenAI, Anthropic, Ollama, etc.)
- Waitlist/token gate bypassed in local mode — unlimited usage
- Developers bring their own API keys via `.env`
- Same scenario JSON configs work in both cloud and local modes
- Future: custom agent plugins + global leaderboard (post-MVP)

## Full Product Spec
For detailed scenarios, agent personas, toggle definitions, and UI breakdowns:
#[[file:docs/JuntoAI A2A MVP_ Product Master Document.md]]
