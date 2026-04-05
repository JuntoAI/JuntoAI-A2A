# Requirements Document

## Introduction

This feature adds two capabilities to the JuntoAI A2A negotiation engine: (1) an explicit deal closure protocol where negotiating agents formally confirm or reject a proposed agreement before the negotiation is considered complete, and (2) a post-negotiation evaluator agent ("JuntoAI Evaluator") that interviews each participant after the deal closes, assesses whether the outcome is a genuine win-win, and produces an honest, ruthless quality score. The evaluator reinforces JuntoAI's core thesis: the goal of negotiation is not that someone wins — it is mutual respect, being seen, and win-win outcomes for everyone.

Currently, deal completion is determined mechanically by price convergence within `agreement_threshold`. This means negotiations can be marked "Agreed" even when agents haven't explicitly confirmed they accept the terms. The closure protocol adds a formal confirmation round where each negotiator must explicitly accept or reject the proposed deal. The evaluator agent then runs as a separate post-negotiation phase, querying each party independently and producing a structured, multi-dimensional score that is displayed on the Outcome Receipt screen.

## Glossary

- **Closure_Protocol**: The backend orchestration phase that triggers when price convergence is detected. Instead of immediately marking the deal as "Agreed", the Closure_Protocol asks each negotiator to explicitly confirm or reject the proposed terms in a final confirmation round.
- **Confirmation_Round**: A single pass through all negotiator agents (excluding regulators and observers) where each agent is prompted to accept or reject the converged deal terms. Each agent produces a Confirmation_Output.
- **Confirmation_Output**: The structured JSON response from a negotiator during the Confirmation_Round, containing `accept` (boolean), `final_statement` (string — the agent's closing message visible to all parties), and `conditions` (optional list of strings — any last conditions attached to acceptance).
- **Deal_Closure_Status**: The result of the Confirmation_Round. One of: `"Confirmed"` (all negotiators accepted), `"Rejected"` (at least one negotiator rejected), or `"Conditional"` (all accepted but with unresolved conditions).
- **Evaluator_Agent**: A special post-negotiation agent ("JuntoAI Evaluator") that runs after the negotiation reaches a terminal state. The Evaluator_Agent interviews each participant independently and produces an Evaluation_Report.
- **Evaluation_Interview**: A single LLM call where the Evaluator_Agent asks one participant a structured set of questions about their satisfaction, sense of being heard, and perception of fairness. Each participant is interviewed independently — they cannot see other participants' responses.
- **Evaluation_Report**: The structured output of the Evaluator_Agent containing per-participant interview results and an overall Evaluation_Score with sub-dimension breakdowns.
- **Evaluation_Score**: A composite score from 1 to 10 (integer) representing the overall quality of the negotiation outcome. Derived from sub-dimension scores, not a simple average.
- **Score_Dimensions**: The four sub-dimensions scored individually from 1 to 10: `fairness` (was the outcome equitable given each party's constraints?), `mutual_respect` (did parties engage constructively without manipulation or bad faith?), `value_creation` (did the negotiation create value beyond zero-sum splitting?), and `satisfaction` (does each party genuinely feel the outcome serves their interests?).
- **Evaluator_SSE_Events**: New SSE event types emitted during the evaluation phase: `evaluation_interview` (streams each participant's interview response) and `evaluation_complete` (delivers the final Evaluation_Report).
- **Orchestrator**: The existing LangGraph-based backend service (`backend/app/orchestrator/`) that manages negotiation state, agent turns, and terminal condition detection.
- **Outcome_Receipt**: The existing frontend component (`frontend/components/glassbox/OutcomeReceipt.tsx`) that displays the final negotiation result. Extended to show the Evaluation_Report.

## Requirements

### Requirement 1: Deal Convergence Triggers Confirmation Round

**User Story:** As an investor watching a negotiation, I want to see agents explicitly confirm they agree on a deal, so that I can trust the outcome is genuine and not just a mechanical price match.

#### Acceptance Criteria

1. WHEN the Orchestrator's `_check_agreement` function detects price convergence within `agreement_threshold`, THE Orchestrator SHALL transition to a Confirmation_Round instead of immediately setting `deal_status` to `"Agreed"`.
2. WHILE the Confirmation_Round is active, THE Orchestrator SHALL set `deal_status` to `"Confirming"` in the NegotiationState.
3. WHEN the Confirmation_Round begins, THE Orchestrator SHALL prompt each negotiator agent (agents with `type == "negotiator"`) in turn_order sequence, skipping regulators and observers.
4. THE Orchestrator SHALL provide each negotiator with the current converged terms (current_offer, turn_count, and the last public messages from all parties) when prompting for confirmation.
5. WHEN a negotiator is prompted for confirmation, THE Orchestrator SHALL require a Confirmation_Output containing `accept` (boolean), `final_statement` (string, minimum 1 character), and `conditions` (list of strings, may be empty).

### Requirement 2: Confirmation Round Resolution

**User Story:** As an investor, I want to see a clear final message from each party confirming or rejecting the deal, so that the negotiation has an unambiguous conclusion.

#### Acceptance Criteria

1. WHEN all negotiators in the Confirmation_Round set `accept` to true with empty `conditions` lists, THE Orchestrator SHALL set `deal_status` to `"Agreed"` and set Deal_Closure_Status to `"Confirmed"`.
2. WHEN at least one negotiator in the Confirmation_Round sets `accept` to false, THE Orchestrator SHALL resume normal negotiation by setting `deal_status` back to `"Negotiating"` and continuing from the current turn_order position.
3. WHEN all negotiators accept but at least one includes non-empty `conditions`, THE Orchestrator SHALL resume normal negotiation by setting `deal_status` back to `"Negotiating"` so agents can address the outstanding conditions.
4. WHEN a rejection or conditional acceptance causes negotiation to resume, THE Orchestrator SHALL append the rejection or conditional statements to the negotiation history so all agents can see the reasons.
5. IF the Confirmation_Round resumes negotiation and the remaining turns reach `max_turns`, THEN THE Orchestrator SHALL set `deal_status` to `"Failed"` with a reason indicating agents could not finalize agreement.
6. THE Orchestrator SHALL stream each negotiator's `final_statement` as an `agent_message` SSE event during the Confirmation_Round so the Glass Box UI displays the closing messages in real time.

### Requirement 3: Confirmation Output Schema

**User Story:** As a developer, I want a well-defined output schema for the confirmation phase, so that agent responses are parseable and testable.

#### Acceptance Criteria

1. THE Orchestrator SHALL define a `ConfirmationOutput` Pydantic V2 model with fields: `accept` (bool), `final_statement` (str, min_length=1), and `conditions` (list[str], default empty list).
2. WHEN the LLM response during the Confirmation_Round fails to parse as valid `ConfirmationOutput` JSON, THE Orchestrator SHALL retry once with an explicit JSON instruction, and if the retry also fails, treat the response as a rejection with `final_statement` set to a fallback message.
3. THE Orchestrator SHALL append each Confirmation_Output to the negotiation `history` with `agent_type` set to `"confirmation"` and the correct `turn_number`.

### Requirement 4: NegotiationState Extensions for Closure

**User Story:** As a developer, I want the negotiation state to track closure protocol status, so that the dispatcher can route correctly during and after confirmation.

#### Acceptance Criteria

1. THE NegotiationState TypedDict SHALL include a `closure_status` field of type `str` with default value `""`, representing the Deal_Closure_Status.
2. THE NegotiationState TypedDict SHALL include a `confirmation_pending` field of type `list[str]` with default empty list, tracking which negotiator roles have not yet confirmed.
3. THE NegotiationStateModel Pydantic model SHALL include corresponding `closure_status` and `confirmation_pending` fields for serialization.
4. WHEN the `deal_status` literal type is extended, THE NegotiationStateModel SHALL accept `"Confirming"` as a valid value in addition to `"Negotiating"`, `"Agreed"`, `"Blocked"`, and `"Failed"`.

### Requirement 5: Post-Negotiation Evaluator Agent

**User Story:** As an investor, I want an independent evaluator to assess whether the negotiation outcome is a genuine win-win, so that I can see beyond the deal terms to the quality of the process.

#### Acceptance Criteria

1. WHEN the Orchestrator sets `deal_status` to a terminal state (`"Agreed"`, `"Blocked"`, or `"Failed"`), THE Orchestrator SHALL invoke the Evaluator_Agent as a post-negotiation phase before emitting the `negotiation_complete` SSE event.
2. THE Evaluator_Agent SHALL conduct an independent Evaluation_Interview with each negotiator agent (agents with `type == "negotiator"`), one at a time.
3. THE Evaluator_Agent SHALL NOT show any participant the responses from other participants' interviews.
4. THE Evaluator_Agent SHALL use a system prompt that instructs the LLM to be adversarial, skeptical, and ruthless in its assessment — explicitly instructing the LLM to not rubber-stamp deals and to probe for hidden dissatisfaction.
5. WHEN the Evaluator_Agent interviews a participant, THE Evaluator_Agent SHALL provide the full negotiation history, the participant's persona and goals, and the final deal terms as context.

### Requirement 6: Evaluation Interview Structure

**User Story:** As an investor, I want each participant to be asked specific, probing questions about their experience, so that the evaluation captures genuine sentiment rather than surface-level agreement.

#### Acceptance Criteria

1. THE Evaluator_Agent SHALL ask each participant the following questions in a single prompt: (a) "Do you genuinely feel this outcome serves your interests, or are you settling?", (b) "Did you feel heard and respected throughout the negotiation?", (c) "Is this a true win-win, or did one side gain at the other's expense?", (d) "What would you change about how the other party negotiated?", (e) "Rate your overall satisfaction from 1-10 and explain why."
2. THE Evaluator_Agent SHALL require each participant to respond with a structured JSON containing: `feels_served` (bool), `felt_respected` (bool), `is_win_win` (bool), `criticism` (str), and `satisfaction_rating` (int, 1-10).
3. IF a participant's LLM response fails to parse as valid interview JSON, THEN THE Evaluator_Agent SHALL retry once, and if the retry fails, use a neutral fallback response with `satisfaction_rating` set to 5.

### Requirement 7: Evaluation Scoring

**User Story:** As an investor, I want a multi-dimensional score that breaks down the negotiation quality, so that I can understand which aspects worked well and which did not.

#### Acceptance Criteria

1. WHEN all participant interviews are complete, THE Evaluator_Agent SHALL produce an Evaluation_Report containing: per-participant interview summaries, Score_Dimensions (fairness, mutual_respect, value_creation, satisfaction — each 1-10), an overall Evaluation_Score (1-10), and a `verdict` string (2-3 sentence summary).
2. THE Evaluator_Agent SHALL compute the overall Evaluation_Score by making a separate LLM call that receives all interview responses and the negotiation history, and is instructed to produce a holistic score that weighs all four dimensions — not a simple arithmetic average.
3. THE Evaluator_Agent SHALL use a scoring prompt that explicitly penalizes: outcomes where one party clearly lost, negotiations where agents were dismissive or manipulative, deals that merely split the difference without creative value creation, and situations where agents expressed dissatisfaction but accepted anyway.
4. THE Evaluation_Report SHALL be serialized as a Pydantic V2 model with fields: `participant_interviews` (list of per-participant results), `dimensions` (dict with fairness, mutual_respect, value_creation, satisfaction as int 1-10), `overall_score` (int, 1-10), `verdict` (str), and `deal_status` (str — the terminal status that triggered evaluation).

### Requirement 8: Evaluation SSE Events

**User Story:** As a user watching the Glass Box UI, I want to see the evaluation happening in real time, so that the post-negotiation assessment feels transparent and live.

#### Acceptance Criteria

1. WHEN the Evaluator_Agent begins an Evaluation_Interview with a participant, THE Orchestrator SHALL emit an `evaluation_interview` SSE event containing `agent_name` (the participant being interviewed), `turn_number` (the current evaluation step), and `status` (`"interviewing"`).
2. WHEN the Evaluator_Agent completes an Evaluation_Interview with a participant, THE Orchestrator SHALL emit an `evaluation_interview` SSE event containing `agent_name`, `satisfaction_rating`, `felt_respected`, `is_win_win`, and `status` (`"complete"`).
3. WHEN the Evaluator_Agent completes the full Evaluation_Report, THE Orchestrator SHALL emit an `evaluation_complete` SSE event containing the complete Evaluation_Report (dimensions, overall_score, verdict, participant_interviews).
4. THE Orchestrator SHALL emit the `evaluation_complete` SSE event before the `negotiation_complete` SSE event, so the frontend receives the evaluation data before the negotiation is marked as finished.

### Requirement 9: Evaluator Model Configuration

**User Story:** As a developer, I want the evaluator to use a configurable LLM model, so that the evaluation quality can be tuned independently of the negotiation agents.

#### Acceptance Criteria

1. THE ArenaScenario Pydantic model SHALL include an optional `evaluator_config` field containing `model_id` (str), `fallback_model_id` (str, optional), and `enabled` (bool, default true).
2. WHEN `evaluator_config` is not present in the scenario JSON, THE Orchestrator SHALL use the first negotiator agent's `model_id` as the default evaluator model.
3. WHEN `evaluator_config.enabled` is set to false, THE Orchestrator SHALL skip the evaluation phase entirely and proceed directly to the `negotiation_complete` SSE event.
4. THE Evaluator_Agent SHALL respect `LLM_MODEL_OVERRIDE` and `MODEL_MAP` environment variables for model routing, consistent with how negotiation agents resolve their models.

### Requirement 10: Outcome Receipt Evaluation Display

**User Story:** As a user, I want to see the evaluation score and breakdown on the outcome screen, so that I can assess the quality of the negotiation at a glance.

#### Acceptance Criteria

1. WHEN the Outcome_Receipt receives an Evaluation_Report, THE Outcome_Receipt SHALL display the overall Evaluation_Score as a prominent "X / 10" indicator with color coding: 1-3 red, 4-6 amber, 7-8 green, 9-10 bright green.
2. THE Outcome_Receipt SHALL display the four Score_Dimensions (fairness, mutual_respect, value_creation, satisfaction) as individual progress bars or numeric indicators below the overall score.
3. THE Outcome_Receipt SHALL display the `verdict` string as a 2-3 sentence summary below the dimension scores.
4. THE Outcome_Receipt SHALL display each participant's `satisfaction_rating` and a one-line summary of their interview response in the participant summaries section.
5. WHEN no Evaluation_Report is available (evaluator disabled or evaluation failed), THE Outcome_Receipt SHALL display the existing outcome layout without an evaluation section.

### Requirement 11: Evaluator Prompt Anti-Rubber-Stamp Design

**User Story:** As a product owner, I want the evaluator to produce honest, differentiated scores, so that a 9/10 actually means something and mediocre deals get mediocre scores.

#### Acceptance Criteria

1. THE Evaluator_Agent's scoring system prompt SHALL include explicit instructions to: (a) default to a score of 5 and require evidence to move higher, (b) treat any participant expressing dissatisfaction as a cap at 6 regardless of other factors, (c) penalize negotiations that ended with a simple price split without creative terms by at least 2 points, and (d) reserve scores of 9-10 for negotiations where all parties expressed genuine enthusiasm and the deal created novel value.
2. THE Evaluator_Agent's interview prompt SHALL instruct the participant LLM to answer honestly based on its persona's goals and constraints, and to not default to politeness — explicitly stating "If you are unhappy, say so. If you feel you lost, say so."
3. THE Evaluator_Agent SHALL cross-reference participant self-reported satisfaction against objective deal metrics (final price vs each agent's target/budget) and flag inconsistencies in the verdict.

### Requirement 12: N-Agent Compatibility

**User Story:** As a developer, I want the closure protocol and evaluator to work with any number of negotiator agents, so that the system remains config-driven and extensible.

#### Acceptance Criteria

1. THE Confirmation_Round SHALL iterate over all agents with `type == "negotiator"` from the scenario config, regardless of how many negotiators exist.
2. THE Evaluator_Agent SHALL interview all agents with `type == "negotiator"` from the scenario config, regardless of how many negotiators exist.
3. WHEN a scenario has more than two negotiators, THE Evaluator_Agent SHALL adjust its scoring to account for multi-party dynamics — the `fairness` dimension SHALL consider whether all parties (not just two) received equitable outcomes.
4. THE Confirmation_Round and Evaluator_Agent SHALL NOT reference specific agent roles by name in their logic — all role references SHALL be derived from the scenario config's `agents` array.
