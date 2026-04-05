# Tasks: LLM Usage Summary

## Task 1: Create Pydantic V2 schema models
- [ ] 1.1 Create `backend/app/models/usage_summary.py` with `PersonaUsageStats`, `ModelUsageStats`, and `UsageSummary` Pydantic V2 models with all fields and `ge=0` constraints as specified in the design
- [ ] 1.2 Add property-based test `backend/tests/property/test_usage_summary_properties.py` — Property 2: UsageSummary JSON round-trip (Hypothesis, 100 iterations)

## Task 2: Implement Usage Summary Aggregator
- [ ] 2.1 Create `backend/app/orchestrator/usage_summary.py` with `compute_usage_summary(agent_calls: list[dict]) -> dict` pure function that groups by `agent_role` and `model_id`, computes per-persona stats, per-model stats, session-wide totals, and `negotiation_duration_ms` from timestamp range
- [ ] 2.2 Handle edge cases: empty list → zero-valued summary, all-error persona → `tokens_per_message = 0`, single record → `negotiation_duration_ms = 0`, missing/malformed timestamps → duration 0
- [ ] 2.3 Add property-based test `backend/tests/property/test_usage_summary_properties.py` — Property 1: Aggregation correctness (Hypothesis, 100 iterations) verifying per-persona sums, per-model sums, session totals, and duration match manual computation
- [ ] 2.4 Add unit tests `backend/tests/unit/test_usage_summary.py` for empty input, all-error persona, single record, and missing `agent_calls` field edge cases

## Task 3: Integrate into NegotiationCompleteEvent
- [ ] 3.1 In `backend/app/routers/negotiation.py` `_snapshot_to_events`, call `compute_usage_summary(state.get("agent_calls", []))` and add result as `usage_summary` key in `final_summary` dict at all terminal-state code paths (dispatcher empty-history path and history-present path)
- [ ] 3.2 Ensure existing `ai_tokens_used` field continues to be populated from `total_tokens_used` (additive, not replacement)
- [ ] 3.3 Add integration test verifying `usage_summary` key is present in `NegotiationCompleteEvent.final_summary` and `ai_tokens_used` is still populated

## Task 4: Create frontend UsageSummaryCard component
- [ ] 4.1 Add TypeScript types for `PersonaUsageStats`, `ModelUsageStats`, and `UsageSummary` in `frontend/types/sse.ts`
- [ ] 4.2 Create `frontend/components/glassbox/UsageSummaryCard.tsx` — collapsible section (`data-testid="usage-summary-section"`) with toggle button (`data-testid="usage-summary-toggle"`), collapsed by default
- [ ] 4.3 Implement per-persona breakdown table sorted by `total_tokens` descending, showing agent_role, model_id, total_tokens, call_count, avg_latency_ms (with "ms" suffix), tokens_per_message, and input:output ratio formatted as "X.Y:1"
- [ ] 4.4 Implement per-model breakdown table showing model_id, total_tokens, call_count, avg_latency_ms, tokens_per_message
- [ ] 4.5 Implement session-wide totals display: total_tokens, total_calls, total_errors (only if > 0), avg_latency_ms, negotiation_duration_ms formatted as seconds with 1 decimal
- [ ] 4.6 Add most-verbose-badge (`data-testid="most-verbose-badge"`) on persona with highest `tokens_per_message` when 2+ personas exist
- [ ] 4.7 Add responsive layout: stacked tables on mobile, side-by-side at ≥1024px (`lg:` breakpoint)

## Task 5: Integrate UsageSummaryCard into OutcomeReceipt
- [ ] 5.1 In `frontend/components/glassbox/OutcomeReceipt.tsx`, conditionally render `UsageSummaryCard` when `finalSummary.usage_summary` exists and `total_calls > 0`; do not render when absent or `total_calls === 0`

## Task 6: Frontend tests
- [ ] 6.1 Add property-based tests `frontend/__tests__/properties/usageSummaryCard.property.test.tsx` — Property 3: renders all persona roles, model IDs, and total_tokens (fast-check, 100 iterations)
- [ ] 6.2 Add property-based test — Property 4: personas sorted by total_tokens descending (fast-check, 100 iterations)
- [ ] 6.3 Add property-based test — Property 5: input:output ratio string correctness (fast-check, 100 iterations)
- [ ] 6.4 Add property-based test — Property 6: most-verbose-badge on correct persona (fast-check, 100 iterations)
- [ ] 6.5 Add unit tests `frontend/__tests__/components/UsageSummaryCard.test.tsx` — section not rendered when absent, not rendered when total_calls=0, collapsed by default, toggle expands, errors hidden when 0, duration formatted correctly
