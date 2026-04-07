import { describe, it, expect, vi } from "vitest";
import { render, within, fireEvent } from "@testing-library/react";
import * as fc from "fast-check";
import UsageSummaryCard from "@/components/glassbox/UsageSummaryCard";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

// ---------------------------------------------------------------------------
// Arbitraries
// ---------------------------------------------------------------------------

const AGENT_ROLES = [
  "Buyer",
  "Seller",
  "EU Regulator",
  "HR Compliance",
  "Recruiter",
  "Candidate",
  "Founder",
  "Account Exec",
  "CTO",
  "Procurement Bot",
] as const;

const AGENT_TYPES = ["negotiator", "regulator", "observer"] as const;

const MODEL_IDS = [
  "gemini-2.5-flash",
  "claude-3.5-sonnet",
  "claude-sonnet-4",
  "gemini-2.5-pro",
  "gpt-4o",
] as const;

const personaUsageStatsArb = fc
  .record({
    agent_role: fc.constantFrom(...AGENT_ROLES),
    agent_type: fc.constantFrom(...AGENT_TYPES),
    model_id: fc.constantFrom(...MODEL_IDS),
    total_input_tokens: fc.integer({ min: 0, max: 100_000 }),
    total_output_tokens: fc.integer({ min: 0, max: 100_000 }),
    call_count: fc.integer({ min: 1, max: 200 }),
    error_count: fc.integer({ min: 0, max: 50 }),
    avg_latency_ms: fc.integer({ min: 0, max: 5000 }),
    tokens_per_message: fc.integer({ min: 0, max: 10_000 }),
  })
  .map((r) => ({
    ...r,
    total_tokens: r.total_input_tokens + r.total_output_tokens,
  }));

const modelUsageStatsArb = fc
  .record({
    model_id: fc.constantFrom(...MODEL_IDS),
    total_input_tokens: fc.integer({ min: 0, max: 100_000 }),
    total_output_tokens: fc.integer({ min: 0, max: 100_000 }),
    call_count: fc.integer({ min: 1, max: 200 }),
    error_count: fc.integer({ min: 0, max: 50 }),
    avg_latency_ms: fc.integer({ min: 0, max: 5000 }),
    tokens_per_message: fc.integer({ min: 0, max: 10_000 }),
  })
  .map((r) => ({
    ...r,
    total_tokens: r.total_input_tokens + r.total_output_tokens,
  }));

/** Build a unique-persona list of exactly `size` entries. */
const uniquePersonaListArb = (minSize: number, maxSize: number) =>
  fc
    .shuffledSubarray([...AGENT_ROLES], { minLength: minSize, maxLength: maxSize })
    .chain((roles) =>
      fc.tuple(...roles.map((role) =>
        personaUsageStatsArb.map((p) => ({ ...p, agent_role: role })),
      )),
    );

/** Build a unique-model list of exactly `size` entries. */
const uniqueModelListArb = (minSize: number, maxSize: number) =>
  fc
    .shuffledSubarray([...MODEL_IDS], { minLength: minSize, maxLength: maxSize })
    .chain((ids) =>
      fc.tuple(...ids.map((id) =>
        modelUsageStatsArb.map((m) => ({ ...m, model_id: id })),
      )),
    );

/** Full UsageSummary with total_calls > 0 and at least 1 persona + 1 model. */
const usageSummaryArb = fc
  .tuple(
    uniquePersonaListArb(1, 6),
    uniqueModelListArb(1, 4),
    fc.integer({ min: 0, max: 500_000 }),
    fc.integer({ min: 0, max: 500_000 }),
    fc.integer({ min: 1, max: 1000 }),
    fc.integer({ min: 0, max: 100 }),
    fc.integer({ min: 0, max: 5000 }),
    fc.integer({ min: 0, max: 300_000 }),
  )
  .map(([personas, models, totalIn, totalOut, totalCalls, totalErrors, avgLat, durMs]) => ({
    per_persona: personas,
    per_model: models,
    total_input_tokens: totalIn,
    total_output_tokens: totalOut,
    total_tokens: totalIn + totalOut,
    total_calls: totalCalls,
    total_errors: totalErrors,
    avg_latency_ms: avgLat,
    negotiation_duration_ms: durMs,
  }));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Click the toggle to expand the card, return the container for queries. */
function renderExpanded(summary: Parameters<typeof UsageSummaryCard>[0]["usageSummary"]) {
  const result = render(<UsageSummaryCard usageSummary={summary} />);
  const toggle = result.getByTestId("usage-summary-toggle");
  fireEvent.click(toggle);
  return result;
}

// ---------------------------------------------------------------------------
// Property 3: renders all persona roles, model IDs, and total_tokens
// ---------------------------------------------------------------------------

/**
 * Feature: 190_llm-usage-summary
 * Property 3: Usage section renders all data when total_calls > 0
 *
 * For any valid UsageSummary with total_calls > 0, the rendered UsageSummaryCard
 * contains every persona's agent_role, every model's model_id, and the
 * session-wide total_tokens value.
 *
 * **Validates: Requirements 4.1, 4.2, 4.3, 4.4**
 */
describe("Property 3: Usage section renders all data when total_calls > 0", () => {
  it("renders every persona role, every model ID, and session total_tokens", () => {
    fc.assert(
      fc.property(usageSummaryArb, (summary) => {
        const { unmount, container } = renderExpanded(summary);
        const view = within(container);

        // Every persona agent_role must appear
        for (const p of summary.per_persona) {
          expect(view.getByText(p.agent_role)).toBeTruthy();
        }

        // Every model_id must appear (may appear in both persona and model tables)
        for (const m of summary.per_model) {
          expect(view.getAllByText(m.model_id).length).toBeGreaterThanOrEqual(1);
        }

        // Session-wide total_tokens (formatted with locale)
        const formattedTotal = summary.total_tokens.toLocaleString("en-US");
        expect(container.textContent).toContain(formattedTotal);

        unmount();
      }),
      { numRuns: 100 },
    );
  });
});

// ---------------------------------------------------------------------------
// Property 4: personas sorted by total_tokens descending
// ---------------------------------------------------------------------------

/**
 * Feature: 190_llm-usage-summary
 * Property 4: Personas sorted by total_tokens descending
 *
 * For any per_persona list with 2+ entries, the rendered per-persona table
 * displays personas in descending order of total_tokens.
 *
 * **Validates: Requirements 5.1**
 */
describe("Property 4: Personas sorted by total_tokens descending", () => {
  it("renders personas in descending total_tokens order", () => {
    fc.assert(
      fc.property(
        uniquePersonaListArb(2, 6).chain((personas) =>
          fc
            .tuple(
              uniqueModelListArb(1, 3),
              fc.integer({ min: 0, max: 500_000 }),
              fc.integer({ min: 0, max: 500_000 }),
              fc.integer({ min: 1, max: 1000 }),
              fc.integer({ min: 0, max: 100 }),
              fc.integer({ min: 0, max: 5000 }),
              fc.integer({ min: 0, max: 300_000 }),
            )
            .map(([models, totalIn, totalOut, totalCalls, totalErrors, avgLat, durMs]) => ({
              per_persona: personas,
              per_model: models,
              total_input_tokens: totalIn,
              total_output_tokens: totalOut,
              total_tokens: totalIn + totalOut,
              total_calls: totalCalls,
              total_errors: totalErrors,
              avg_latency_ms: avgLat,
              negotiation_duration_ms: durMs,
            })),
        ),
        (summary) => {
          const { unmount, container } = renderExpanded(summary);

          // Grab all rows from the per-persona table body
          const personaTable = container.querySelectorAll("table")[0];
          const rows = personaTable.querySelectorAll("tbody tr");

          const expectedOrder = [...summary.per_persona].sort(
            (a, b) => b.total_tokens - a.total_tokens,
          );

          // Each row's first cell should match the expected sorted role
          for (let i = 0; i < expectedOrder.length; i++) {
            const firstCell = rows[i].querySelectorAll("td")[0];
            expect(firstCell.textContent).toContain(expectedOrder[i].agent_role);
          }

          unmount();
        },
      ),
      { numRuns: 100 },
    );
  });
});

// ---------------------------------------------------------------------------
// Property 5: input:output ratio string correctness
// ---------------------------------------------------------------------------

/**
 * Feature: 190_llm-usage-summary
 * Property 5: Input-to-output ratio correctness
 *
 * For any PersonaUsageStats with total_output_tokens > 0, the displayed ratio
 * string equals `"${(total_input_tokens / total_output_tokens).toFixed(1)}:1"`.
 *
 * **Validates: Requirements 5.2**
 */
describe("Property 5: Input-to-output ratio string correctness", () => {
  it("displays correct ratio for personas with total_output_tokens > 0", () => {
    fc.assert(
      fc.property(
        personaUsageStatsArb
          .filter((p) => p.total_output_tokens > 0)
          .chain((persona) =>
            fc
              .tuple(
                uniqueModelListArb(1, 2),
                fc.integer({ min: 0, max: 500_000 }),
                fc.integer({ min: 0, max: 500_000 }),
                fc.integer({ min: 1, max: 1000 }),
                fc.integer({ min: 0, max: 100 }),
                fc.integer({ min: 0, max: 5000 }),
                fc.integer({ min: 0, max: 300_000 }),
              )
              .map(([models, totalIn, totalOut, totalCalls, totalErrors, avgLat, durMs]) => ({
                persona,
                summary: {
                  per_persona: [persona],
                  per_model: models,
                  total_input_tokens: totalIn,
                  total_output_tokens: totalOut,
                  total_tokens: totalIn + totalOut,
                  total_calls: totalCalls,
                  total_errors: totalErrors,
                  avg_latency_ms: avgLat,
                  negotiation_duration_ms: durMs,
                },
              })),
          ),
        ({ persona, summary }) => {
          const { unmount, container } = renderExpanded(summary);

          const expectedRatio = `${(persona.total_input_tokens / persona.total_output_tokens).toFixed(1)}:1`;

          // The ratio appears in the last cell of the persona's row
          const personaTable = container.querySelectorAll("table")[0];
          const row = personaTable.querySelector("tbody tr")!;
          const cells = row.querySelectorAll("td");
          const ratioCell = cells[cells.length - 1];

          expect(ratioCell.textContent).toBe(expectedRatio);

          unmount();
        },
      ),
      { numRuns: 100 },
    );
  });
});

// ---------------------------------------------------------------------------
// Property 6: most-verbose-badge on correct persona
// ---------------------------------------------------------------------------

/**
 * Feature: 190_llm-usage-summary
 * Property 6: Most verbose badge on correct persona
 *
 * For any per_persona list with 2+ entries, exactly one persona has the
 * most-verbose-badge, and it is the persona with the highest tokens_per_message.
 *
 * **Validates: Requirements 5.3**
 */
describe("Property 6: Most verbose badge on correct persona", () => {
  it("places exactly one most-verbose-badge on the persona with highest tokens_per_message", () => {
    fc.assert(
      fc.property(
        uniquePersonaListArb(2, 6)
          .filter((personas) => {
            // Ensure a unique winner for tokens_per_message
            const sorted = [...personas].sort(
              (a, b) => b.tokens_per_message - a.tokens_per_message,
            );
            return sorted[0].tokens_per_message !== sorted[1].tokens_per_message;
          })
          .chain((personas) =>
            fc
              .tuple(
                uniqueModelListArb(1, 3),
                fc.integer({ min: 0, max: 500_000 }),
                fc.integer({ min: 0, max: 500_000 }),
                fc.integer({ min: 1, max: 1000 }),
                fc.integer({ min: 0, max: 100 }),
                fc.integer({ min: 0, max: 5000 }),
                fc.integer({ min: 0, max: 300_000 }),
              )
              .map(([models, totalIn, totalOut, totalCalls, totalErrors, avgLat, durMs]) => ({
                per_persona: personas,
                per_model: models,
                total_input_tokens: totalIn,
                total_output_tokens: totalOut,
                total_tokens: totalIn + totalOut,
                total_calls: totalCalls,
                total_errors: totalErrors,
                avg_latency_ms: avgLat,
                negotiation_duration_ms: durMs,
              })),
          ),
        (summary) => {
          const { unmount, container } = renderExpanded(summary);
          const view = within(container);

          // Exactly one badge
          const badges = view.getAllByTestId("most-verbose-badge");
          expect(badges).toHaveLength(1);

          // The badge should be in the row of the persona with highest tokens_per_message
          // The component sorts by total_tokens desc, so find the winner by tokens_per_message
          const sortedByTokens = [...summary.per_persona].sort(
            (a, b) => b.total_tokens - a.total_tokens,
          );
          const winner = sortedByTokens.reduce((prev, curr) =>
            curr.tokens_per_message > prev.tokens_per_message ? curr : prev,
          );

          // The badge's parent row should contain the winner's agent_role
          const badgeRow = badges[0].closest("tr")!;
          expect(badgeRow.textContent).toContain(winner.agent_role);

          unmount();
        },
      ),
      { numRuns: 100 },
    );
  });
});
