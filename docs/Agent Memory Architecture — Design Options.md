# Agent Memory Architecture — Design Options

## Status: RFC (Request for Comments)
## Date: 2026-04-02
## Author: JuntoAI Engineering

---

## Problem Statement

The current A2A negotiation engine uses **stateless LLM calls** per agent turn. Each turn, the full negotiation history is serialized into the prompt as plain text. The agent has no persistent memory — it reconstructs context from scratch every call.

This creates three concrete problems:

1. **Token cost scales quadratically** — each turn adds to history, and every subsequent call re-sends the entire transcript. A 12-turn negotiation with 3 agents produces ~36 LLM calls, each carrying an ever-growing history payload.
2. **Strategic recall degrades** — as history grows, earlier turns get diluted in the context window. Agents "forget" what was conceded in turn 2 by the time they reach turn 10, leading to circular arguments and repeated positions.
3. **No structured recall** — agents can't efficiently answer "what did I offer last time?" or "what compliance items are still open?" without re-parsing the entire transcript. This makes strategic reasoning brittle and model-dependent.

### Current Architecture

```
┌─────────────┐     ┌──────────────────────────┐     ┌─────────────┐
│  Dispatcher  │────▶│  Agent Node (per turn)   │────▶│  Dispatcher  │
│  (routing)   │     │                          │     │  (routing)   │
└─────────────┘     │  1. Build prompt:         │     └─────────────┘
                    │     - System: persona     │
                    │     - User: FULL history  │
                    │       + current_offer     │
                    │       + last_price        │
                    │  2. Single LLM call       │
                    │  3. Parse JSON output     │
                    │  4. Update state          │
                    └──────────────────────────┘
```

Each agent call is independent. The LangGraph state machine holds `current_offer`, `warning_count`, `last_proposed_price`, and `deal_status` — but the agent itself has no memory beyond what's stuffed into the prompt.

---

## Design Options

### Option 1: Per-Agent Rolling Summary

After each agent's turn, make a lightweight LLM call to compress the agent's strategic state into a short summary memo. Store this as a `strategy_memo` field in `agent_states`. On the next turn, the agent receives their memo + only the last 2–3 history entries instead of the full transcript.

**How it works:**

```
Turn N:
  1. Agent receives: strategy_memo (from turn N-1) + last 3 messages
  2. Agent produces: response JSON
  3. Summarizer LLM call: "Given this response and the previous memo,
     update the strategic summary"
  4. Updated strategy_memo stored in agent_states
```

**Example strategy_memo:**

```
I have offered €90, €87, €82.50. The client started at €40k fixed-price,
moved to €39k, then €39.5k. They are firm on a 2-week trial period and
fixed-price contract. I have successfully pushed them toward hourly billing.
Key unresolved: payment structure (they want bi-weekly, I want milestone).
My next move: accept their budget ceiling but demand 30% upfront.
```

---

### Option 2: Structured Agent Memory

Instead of free-text history, maintain a typed, structured memory object per agent that is updated programmatically after each turn. The agent receives this structured data + the last 2–3 raw messages for conversational context.

**Memory schema:**

```json
{
  "my_offers": [90.0, 87.0, 82.5, 80.0, 82.0, 83.0],
  "their_offers": [40000, 38000, 39000, 39500, 39250],
  "concessions_made": [
    "Dropped from €90 to €87 in exchange for 3-month commitment discussion",
    "Accepted €80/hour for guaranteed 40h/week engagement"
  ],
  "concessions_received": [
    "Client moved from fixed-price-only to considering hourly",
    "Client increased from €38k to €39.5k"
  ],
  "open_items": ["payment structure", "trial period terms", "scope document"],
  "tactics_used": ["scope creep risk framing", "milestone payment justification"],
  "red_lines_stated": ["No work without written scope", "Minimum 25% upfront"],
  "compliance_status": {},
  "turn_count": 8
}
```

**How it works:**

```
Turn N:
  1. Agent receives: structured_memory + last 3 messages + current_offer
  2. Agent produces: response JSON (with inner_thought, public_message, proposed_price)
  3. Extraction logic parses the response and updates structured_memory:
     - Append proposed_price to my_offers
     - Parse concessions from inner_thought
     - Update open_items based on what was addressed
  4. Updated structured_memory stored in agent_states
```

The extraction can be done either deterministically (parse known fields) or with a lightweight LLM call for nuanced items like concessions and tactics.

---

### Option 3: RAG Over Negotiation History

Store each turn as a vector embedding in an in-memory vector store (FAISS, ChromaDB) or Firestore with vector search. Before each agent's turn, retrieve the top-K most relevant past turns based on the current negotiation context.

**How it works:**

```
Turn N:
  1. Build query from current state: "payment terms, trial period, hourly rate"
  2. Retrieve top-5 most relevant past turns from vector store
  3. Agent receives: persona + retrieved turns + last 2 messages
  4. Agent produces response
  5. New turn embedded and stored in vector store
```

**Infrastructure required:**
- Embedding model (Vertex AI text-embedding or sentence-transformers)
- Vector store (in-memory FAISS for MVP, Firestore vector search for production)
- Retrieval pipeline with relevance scoring

---

### Option 4: Hybrid — Structured Memory + Sliding Window + Milestone Summaries

Combines Options 1 and 2 into a comprehensive memory system:

- **Structured memory** (Option 2) for hard facts: prices, concessions, open items
- **Sliding window** of last 3–4 raw messages for conversational tone and context
- **Milestone summaries** generated at turn 4, 8, 12 that compress earlier history into strategic context paragraphs
- **Full raw history dropped** after turn 4 — never sent to the LLM again

**How it works:**

```
Turn N (where N > 4):
  1. Agent receives:
     - Structured memory (prices, concessions, open items)
     - Milestone summary from turn 4 (and 8, 12 if applicable)
     - Last 3 raw messages (sliding window)
     - Current offer + turn info
  2. Agent produces response
  3. Structured memory updated
  4. If N is a milestone turn (4, 8, 12): generate milestone summary
```

**Token budget per turn (estimated):**

| Component | Tokens (approx) |
|---|---|
| System prompt (persona + goals + rules) | ~500 |
| Structured memory | ~300 |
| Milestone summaries (1–3) | ~200–600 |
| Sliding window (3 messages) | ~600 |
| Current state + instructions | ~200 |
| **Total** | **~1,800–2,200** |

Compare to current approach at turn 12: ~4,000–6,000 tokens of raw history alone.

---

### Option 5: LangGraph Memory Checkpointing

Use LangGraph's built-in persistence layer (`MemorySaver`, `SqliteSaver`, or a custom Firestore-backed checkpointer) to give each agent a persistent conversation thread. Instead of reconstructing context each turn, the agent's sub-graph maintains its own message history natively.

**How it works:**

```
Each agent becomes a sub-graph with its own checkpointed state:

┌─────────────────────────────────────────────┐
│  Main Negotiation Graph                     │
│                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │ Buyer    │  │ Seller   │  │ Regulator│  │
│  │ SubGraph │  │ SubGraph │  │ SubGraph │  │
│  │ (own     │  │ (own     │  │ (own     │  │
│  │  memory) │  │  memory) │  │  memory) │  │
│  └──────────┘  └──────────┘  └──────────┘  │
│                                             │
│  Dispatcher routes between sub-graphs       │
└─────────────────────────────────────────────┘
```

Each sub-graph maintains its own `messages` list via LangGraph checkpointing. The agent sees its full conversation history natively through the LangChain message interface, and LangGraph handles persistence/replay.

---

## Comparison Table

| Criteria | Option 1: Rolling Summary | Option 2: Structured Memory | Option 3: RAG | Option 4: Hybrid | Option 5: LangGraph Checkpointing |
|---|---|---|---|---|---|
| **Strategic recall accuracy** | Good — depends on summarizer quality | Excellent — precise structured data | Good — depends on retrieval relevance | Excellent — structured + contextual | Good — full history but unstructured |
| **Token cost per turn** | Low (~1,500) | Low (~1,200) | Medium (~1,800) | Low (~2,000) | High (grows with turns, same as current) |
| **Token cost scaling** | O(n) — bounded by memo size | O(n) — bounded by memory schema | O(1) — fixed retrieval window | O(1) — fixed budget | O(n²) — same as current unless windowed |
| **Extra LLM calls per turn** | +1 (summarizer) | 0 or +1 (extraction) | 0 (embedding is cheap) | +1 at milestones only | 0 |
| **Infrastructure added** | None | None | Embedding model + vector store | None | LangGraph checkpointer backend |
| **Implementation effort** | Small (1–2 days) | Medium (2–3 days) | High (4–5 days) | Medium-high (3–4 days) | High (4–5 days, architectural change) |
| **Handles 50+ turns** | Yes | Yes | Yes (designed for this) | Yes | Poorly (context window limits) |
| **Stall detection synergy** | Moderate — memo is free text | Excellent — structured data is directly analyzable | Low — requires re-retrieval | Excellent — same as Option 2 | Low — same as current |
| **Debugging / observability** | Moderate — can inspect memos | Excellent — structured data is inspectable | Low — embeddings are opaque | Excellent — structured + readable | Moderate — message history is inspectable |
| **Risk of information loss** | Medium — summarizer may drop nuance | Low — deterministic extraction for key fields | Medium — retrieval may miss relevant turns | Low — structured core + raw sliding window | None — full history preserved |
| **Scenario author impact** | None — transparent | None — transparent | None — transparent | None — transparent | Medium — sub-graph architecture changes scenario wiring |
| **Works with user-created scenarios** | Yes | Yes | Yes | Yes | Yes, but more complex |
| **Latency per turn added** | +1–2s (summarizer call) | +0–1s (extraction) | +0.5s (embedding + retrieval) | +0–2s (varies by turn) | 0 |

---

## Recommendation

### Phase 1 (MVP): Option 2 — Structured Agent Memory

**Why:** Highest impact-to-effort ratio. Gives agents precise recall of prices, concessions, and open items without any additional infrastructure. Token costs drop significantly. Stall detection becomes trivial — you can analyze structured data directly instead of parsing free text. Zero new infrastructure dependencies.

**Scope:**
- New `AgentMemory` Pydantic model with typed fields
- Update `_build_prompt` to serialize structured memory instead of full history
- Add extraction logic in `_update_state` to populate memory fields from parsed output
- Keep sliding window of last 3 raw messages for conversational context
- Update stall detector to use structured memory data

### Phase 2 (Post-MVP): Option 4 — Full Hybrid

**Why:** Adds milestone summaries for long-running scenarios (16+ turns) and formalizes the sliding window. This is the production-grade architecture that scales to any turn count while maintaining bounded token costs.

**Scope:**
- Add milestone summary generation at configurable turn intervals
- Formalize sliding window size as a scenario parameter
- Drop full history from prompts entirely after the first milestone

### Not Recommended for Now

- **Option 3 (RAG):** Overkill for 8–16 turn negotiations. Retrieval relevance is questionable for negotiations where chronological context matters more than semantic similarity. Adds infrastructure complexity (embedding model, vector store) without proportional benefit at current scale.
- **Option 5 (LangGraph Checkpointing):** Requires significant architectural restructuring (agents become sub-graphs). Doesn't solve the token scaling problem — it just moves the full history into the framework's memory layer. Would only make sense if we needed cross-session agent memory (agents that remember previous negotiations).

---

## Open Questions

1. **Extraction accuracy:** Should concession extraction be deterministic (regex/rule-based on known fields) or LLM-assisted? Deterministic is faster and cheaper but may miss nuanced concessions expressed in natural language.
2. **Memory visibility:** Should the structured memory be visible in the Glass Box UI? Showing investors what each agent "remembers" could be a powerful demo feature.
3. **Cross-agent memory:** Should agents be able to see each other's structured memory, or only their own? Keeping memories private preserves the information asymmetry that makes negotiations interesting.
4. **Memory in user-created scenarios:** Should scenario authors be able to configure which memory fields are tracked, or should the schema be fixed?
