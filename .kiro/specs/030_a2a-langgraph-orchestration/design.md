# Design Document: LangGraph N-Agent Orchestration Layer

## Overview

This design covers the LangGraph-based AI orchestration engine that drives the turn-based negotiation loop for the JuntoAI A2A MVP. The orchestrator coordinates N agents (negotiators + regulators + observers) through a config-driven state machine, routing each agent to a distinct LLM via Google Vertex AI Model Garden.

### Key Design Decisions

1. **TypedDict for LangGraph, Pydantic for the boundary** — LangGraph's `StateGraph` requires a `TypedDict` (or `dataclass`) as its state schema. The Pydantic `NegotiationStateModel` (owned by spec 020) is the serialization format for Firestore and API responses. This spec owns the `NegotiationState` TypedDict and the explicit `negotiation_state_to_pydantic()` / `pydantic_to_negotiation_state()` converters. The two representations exist because LangGraph's channel-based state merging doesn't work with Pydantic models, and Pydantic's validation overhead is unnecessary inside the hot loop of node executions.

2. **Single generic `create_agent_node()` factory** — Instead of separate `BuyerNode`, `SellerNode`, `RegulatorNode` classes, a single factory function creates all agent nodes. The factory takes the agent's role, index in the scenario config's `agents` array, and agent type (`negotiator` | `regulator` | `observer`). The agent type determines which output parser to use (`NegotiatorOutput` vs `RegulatorOutput` vs `ObserverOutput`). This eliminates code duplication across Requirements 3, 4, and 5 — the only difference between a Buyer and Seller node is the persona prompt and output fields, both of which come from the scenario config.

3. **Dispatcher node as central routing point** — Rather than N² conditional edges between agent nodes, a single `dispatcher` node inspects `current_speaker` and `deal_status` to determine the next node. The dispatcher is the only node with conditional outgoing edges. Agent nodes always route back to the dispatcher. This keeps the graph topology simple: `agent_i → dispatcher → agent_j` for all i, j.

4. **Agreement detection after every negotiator turn** — The dispatcher checks for price convergence (both negotiators' latest `proposed_price` within `agreement_threshold`) after every negotiator completes, not just at the end of a full cycle. This means a deal can close mid-cycle without forcing unnecessary regulator/seller turns. The `turn_count` still increments only after a full cycle completes.

5. **LangChain Vertex AI integration** — Uses `ChatVertexAI` (from `langchain-google-vertexai`) for Gemini models and `ChatAnthropicVertex` (from `langchain-google-vertexai`) for Claude models on Vertex AI. Both use GCP IAM auth — no separate API keys. The `model_router.py` module maps `model_id` strings to the correct LangChain chat model class.

6. **Retry-once on parse failure** — When an LLM response can't be parsed into the expected output schema, the agent node retries once with an explicit JSON formatting instruction appended to the prompt. If the retry also fails, an `AgentOutputParseError` is raised. This handles the common case of LLMs returning markdown-wrapped JSON or missing fields on the first attempt.

7. **Async generator for SSE integration** — `run_negotiation()` is an async generator that yields `NegotiationState` snapshots after each node execution. The SSE endpoint (spec 020) iterates this generator and converts each snapshot to SSE events. This decouples orchestration from transport completely.

8. **Dynamic graph construction from scenario config** — `build_graph()` reads the `agents` array and `turn_order` from the scenario config to construct the `StateGraph` dynamically. The turn order (e.g., `["Buyer", "Regulator", "Seller", "Regulator"]`) defines the cycle. Agent nodes are registered by role name. This means a 4th scenario with different agent roles (e.g., `Landlord`, `Tenant`, `Mediator`) works without code changes.

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                    LangGraph StateGraph                          │
│                                                                  │
│  ┌──────────┐     ┌────────────┐     ┌──────────┐              │
│  │  Agent    │────▶│ Dispatcher │────▶│  Agent   │              │
│  │  Node 0   │     │            │     │  Node 1  │              │
│  │ (Buyer)   │     │ Routes by: │     │ (Seller) │              │
│  └──────────┘     │ • speaker  │     └────┬─────┘              │
│       ▲           │ • status   │          │                     │
│       │           │ • turn_cnt │          │                     │
│       │           └─────┬──────┘          │                     │
│       │                 │                 │                     │
│       │           ┌─────▼──────┐          │                     │
│       │           │  Agent     │◀─────────┘                     │
│       └───────────│  Node 2    │                                │
│                   │ (Regulator)│                                │
│                   └────────────┘                                │
│                         │                                       │
│                    ┌────▼────┐                                  │
│                    │   END   │  (deal_status != "Negotiating")  │
│                    └─────────┘                                  │
└──────────────────────────────────────────────────────────────────┘
         │
         │  yields NegotiationState snapshots
         ▼
┌─────────────────────────┐
│  run_negotiation()      │  async generator
│  (graph.py)             │──▶ SSE endpoint (spec 020)
└─────────────────────────┘

┌─────────────────────────┐     ┌─────────────────────────┐
│  Model Router           │     │  Converters             │
│  (model_router.py)      │     │  (converters.py)        │
│                         │     │                         │
│  model_id → LangChain   │     │  TypedDict ↔ Pydantic   │
│  ChatModel instance     │     │  NegotiationState ↔     │
│                         │     │  NegotiationStateModel   │
│  • ChatVertexAI         │     └─────────────────────────┘
│    (Gemini models)      │
│  • ChatAnthropicVertex  │
│    (Claude models)      │
└─────────────────────────┘
```

### Directory Layout

```
backend/app/orchestrator/
├── __init__.py           # Re-exports: build_graph, run_negotiation, NegotiationState
├── state.py              # NegotiationState TypedDict + defaults factory
├── outputs.py            # NegotiatorOutput, RegulatorOutput, ObserverOutput Pydantic models
├── agent_node.py         # create_agent_node() factory + prompt construction + parse logic
├── graph.py              # build_graph(), dispatcher node, run_negotiation() async generator
├── model_router.py       # get_model() → ChatVertexAI | ChatAnthropicVertex, fallback support
├── converters.py         # negotiation_state_to_pydantic(), pydantic_to_negotiation_state()
└── exceptions.py         # ModelNotAvailableError, ModelTimeoutError, AgentOutputParseError
```

## Components and Interfaces

### 1. NegotiationState TypedDict (`state.py`)

The LangGraph runtime state. Uses `TypedDict` with `Annotated` types for LangGraph's channel-based state merging where needed.

```python
from typing import TypedDict, Any, Annotated
from operator import add

class AgentState(TypedDict):
    """Per-agent tracking within a negotiation."""
    role: str
    name: str
    agent_type: str          # "negotiator" | "regulator" | "observer"
    model_id: str
    last_proposed_price: float  # 0.0 for non-negotiators

class NegotiationState(TypedDict):
    session_id: str
    scenario_id: str
    turn_count: int                          # increments after full cycle
    max_turns: int
    current_speaker: str                     # role name of next agent to act
    deal_status: str                         # "Negotiating" | "Agreed" | "Blocked" | "Failed"
    current_offer: float
    history: Annotated[list[dict[str, Any]], add]  # append-only via LangGraph reducer
    hidden_context: dict[str, Any]
    warning_count: int
    agreement_threshold: float
    scenario_config: dict[str, Any]          # full loaded scenario JSON
    turn_order: list[str]                    # e.g. ["Buyer", "Regulator", "Seller", "Regulator"]
    turn_order_index: int                    # current position in turn_order
    agent_states: dict[str, AgentState]      # keyed by role name
    active_toggles: list[str]
```

The `history` field uses LangGraph's `Annotated[list, add]` reducer so each node can return `{"history": [new_entry]}` and LangGraph appends it automatically, avoiding read-modify-write race conditions.

A `create_initial_state()` factory function builds the initial `NegotiationState` from a scenario config dict, active toggles list, and session ID:

```python
def create_initial_state(
    session_id: str,
    scenario_config: dict[str, Any],
    active_toggles: list[str] | None = None,
    hidden_context: dict[str, Any] | None = None,
) -> NegotiationState:
    agents = scenario_config["agents"]
    params = scenario_config["negotiation_params"]
    
    # Build turn_order from agents: negotiators alternate with regulators
    negotiators = [a for a in agents if a["role"] != "Regulator" and "status" not in a.get("output_fields", [])]
    regulators = [a for a in agents if "status" in a.get("output_fields", [])]
    
    turn_order = []
    for neg in negotiators:
        turn_order.append(neg["role"])
        for reg in regulators:
            turn_order.append(reg["role"])
    
    agent_states = {}
    for a in agents:
        agent_type = "regulator" if "status" in a.get("output_fields", []) else "negotiator"
        agent_states[a["role"]] = AgentState(
            role=a["role"],
            name=a["name"],
            agent_type=agent_type,
            model_id=a["model_id"],
            last_proposed_price=0.0,
        )
    
    return NegotiationState(
        session_id=session_id,
        scenario_id=scenario_config["id"],
        turn_count=0,
        max_turns=params.get("max_turns", 15),
        current_speaker=turn_order[0],
        deal_status="Negotiating",
        current_offer=0.0,
        history=[],
        hidden_context=hidden_context or {},
        warning_count=0,
        agreement_threshold=params.get("agreement_threshold", 1000000.0),
        scenario_config=scenario_config,
        turn_order=turn_order,
        turn_order_index=0,
        agent_states=agent_states,
        active_toggles=active_toggles or [],
    )
```

### 2. Agent Output Models (`outputs.py`)

Pydantic V2 models for parsing LLM responses. These are internal to the orchestrator — not the same as the SSE event models in spec 020.

```python
from pydantic import BaseModel, field_validator
from typing import Any, Literal

class NegotiatorOutput(BaseModel):
    """Output schema for negotiating agents (Buyer, Seller, etc.)."""
    inner_thought: str
    public_message: str
    proposed_price: float
    extra_fields: dict[str, Any] = {}

class RegulatorOutput(BaseModel):
    """Output schema for regulator agents."""
    status: Literal["CLEAR", "WARNING", "BLOCKED"]
    reasoning: str

class ObserverOutput(BaseModel):
    """Output schema for observer agents (future extensibility)."""
    observation: str
    recommendation: str = ""
```

### 3. Agent Node Factory (`agent_node.py`)

A single factory that creates callable node functions for any agent type.

```python
def create_agent_node(
    role: str,
    agent_type: str,  # "negotiator" | "regulator" | "observer"
    get_model: Callable[[str, str | None], BaseChatModel],
) -> Callable[[NegotiationState], dict[str, Any]]:
```

The returned callable:
1. Looks up the agent config from `state["scenario_config"]["agents"]` by matching `role`
2. Constructs the system prompt from `persona_prompt`, `goals`, `budget`, and any `hidden_context` for this role
3. Builds the message history from `state["history"]`
4. Calls `get_model(agent_config["model_id"], fallback_model_id)` to get the LangChain chat model
5. Invokes the model with the constructed messages
6. Parses the response using the appropriate output model (`NegotiatorOutput`, `RegulatorOutput`, or `ObserverOutput`)
7. On parse failure, retries once with an explicit JSON formatting instruction
8. Returns a state update dict (LangGraph merges this into the state)

The prompt construction follows this structure:

```
SYSTEM: {persona_prompt}

Your goals: {goals as bullet list}
Your budget constraints: min={budget.min}, max={budget.max}, target={budget.target}

{hidden_context if present}

You MUST respond with valid JSON matching this schema:
{output_schema}