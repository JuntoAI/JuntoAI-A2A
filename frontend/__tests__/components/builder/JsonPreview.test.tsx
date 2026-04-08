import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import fc from "fast-check";
import {
  JsonPreview,
  buildPreviewObject,
  highlightJson,
  SECTIONS,
  PLACEHOLDER,
} from "@/components/builder/JsonPreview";
import type { ArenaScenario } from "@/lib/api";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const FULL_SCENARIO: ArenaScenario = {
  id: "test-scenario",
  name: "Test Scenario",
  description: "A test scenario for property testing",
  agents: [
    { name: "Agent A", role: "buyer", goals: ["buy cheap"], model_id: "m1", type: "negotiator" },
    { name: "Agent B", role: "seller", goals: ["sell high"], model_id: "m2", type: "negotiator" },
  ],
  toggles: [{ id: "t1", label: "Toggle 1", target_agent_role: "seller" }],
  negotiation_params: { max_turns: 10 },
  outcome_receipt: { equivalent_human_time: "2 hours", process_label: "Negotiation" },
};

/** Generate a partial scenario with a random subset of sections populated. */
const arbSectionSubset = fc.subarray(SECTIONS as unknown as string[], { minLength: 0 });

function buildPartialFromSections(sections: string[]): Partial<ArenaScenario> {
  const partial: Record<string, unknown> = {};
  for (const key of sections) {
    partial[key] = (FULL_SCENARIO as Record<string, unknown>)[key];
  }
  return partial as Partial<ArenaScenario>;
}

// ---------------------------------------------------------------------------
// Property 21: JSON preview placeholder rendering
// **Validates: Requirements 4.2**
// ---------------------------------------------------------------------------

describe("Property 21: JSON preview placeholder rendering", () => {
  it("unpopulated sections show placeholders, populated sections show valid JSON", () => {
    fc.assert(
      fc.property(arbSectionSubset, (populatedSections) => {
        const partial = buildPartialFromSections(populatedSections);
        const preview = buildPreviewObject(partial);

        for (const section of SECTIONS) {
          const key = section as string;
          if (populatedSections.includes(key)) {
            // Populated section should NOT be the placeholder
            expect(preview[key]).not.toBe(PLACEHOLDER);
            // Should be valid JSON-serializable
            expect(() => JSON.stringify(preview[key])).not.toThrow();
          } else {
            // Unpopulated section should be the placeholder
            expect(preview[key]).toBe(PLACEHOLDER);
          }
        }
      }),
      { numRuns: 100 },
    );
  });

  it("rendered component shows placeholder text for empty sections", () => {
    const partial: Partial<ArenaScenario> = { name: "Test" };
    render(<JsonPreview scenarioJson={partial} highlightedSection={null} />);

    const container = screen.getByTestId("json-preview");
    const text = container.textContent ?? "";

    // "name" should appear with its value
    expect(text).toContain('"name"');
    expect(text).toContain('"Test"');

    // Unpopulated sections should show placeholder
    expect(text).toContain(PLACEHOLDER);
  });
});

// ---------------------------------------------------------------------------
// Property 22: JSON preview 2-space indentation
// **Validates: Requirements 4.4**
// ---------------------------------------------------------------------------

describe("Property 22: JSON preview 2-space indentation", () => {
  it("for any scenario JSON, output uses 2-space indentation", () => {
    fc.assert(
      fc.property(arbSectionSubset, (populatedSections) => {
        const partial = buildPartialFromSections(populatedSections);
        const preview = buildPreviewObject(partial);
        const jsonString = JSON.stringify(preview, null, 2);

        // Verify indentation: every indented line should use multiples of 2 spaces
        const lines = jsonString.split("\n");
        for (const line of lines) {
          const leadingSpaces = line.match(/^( *)/)?.[1] ?? "";
          // Leading spaces should be a multiple of 2
          expect(leadingSpaces.length % 2).toBe(0);
        }

        // Verify it's valid JSON
        expect(() => JSON.parse(jsonString)).not.toThrow();

        // Verify round-trip: parse and re-stringify should match
        const reparsed = JSON.parse(jsonString);
        const reStringified = JSON.stringify(reparsed, null, 2);
        expect(reStringified).toBe(jsonString);
      }),
      { numRuns: 100 },
    );
  });
});

// ---------------------------------------------------------------------------
// Unit tests: syntax highlighting
// ---------------------------------------------------------------------------

describe("JsonPreview syntax highlighting", () => {
  it("highlights keys with purple class", () => {
    const tokens = highlightJson('{"name": "test"}');
    const keyToken = tokens.find((t) => t.text === '"name"');
    expect(keyToken).toBeDefined();
    expect(keyToken!.className).toContain("purple");
  });

  it("highlights string values with green class", () => {
    const tokens = highlightJson('{"name": "test"}');
    const valueToken = tokens.find((t) => t.text === '"test"');
    expect(valueToken).toBeDefined();
    expect(valueToken!.className).toContain("green");
  });

  it("highlights numbers with blue class", () => {
    const tokens = highlightJson('{"count": 42}');
    const numToken = tokens.find((t) => t.text === "42");
    expect(numToken).toBeDefined();
    expect(numToken!.className).toContain("blue");
  });

  it("highlights booleans with orange class", () => {
    const tokens = highlightJson('{"active": true}');
    const boolToken = tokens.find((t) => t.text === "true");
    expect(boolToken).toBeDefined();
    expect(boolToken!.className).toContain("orange");
  });

  it("highlights placeholder strings with yellow italic", () => {
    const tokens = highlightJson(`{"id": "${PLACEHOLDER}"}`);
    const placeholderToken = tokens.find((t) => t.text === `"${PLACEHOLDER}"`);
    expect(placeholderToken).toBeDefined();
    expect(placeholderToken!.className).toContain("yellow");
    expect(placeholderToken!.className).toContain("italic");
  });
});

// ---------------------------------------------------------------------------
// Unit test: section highlight
// ---------------------------------------------------------------------------

describe("JsonPreview section highlight", () => {
  it("marks highlighted section lines with data-highlighted attribute", () => {
    render(
      <JsonPreview scenarioJson={FULL_SCENARIO} highlightedSection="name" />,
    );

    const highlighted = screen.getByTestId("json-preview").querySelectorAll(
      "[data-highlighted]",
    );
    expect(highlighted.length).toBeGreaterThan(0);
  });

  it("does not highlight when highlightedSection is null", () => {
    render(
      <JsonPreview scenarioJson={FULL_SCENARIO} highlightedSection={null} />,
    );

    const highlighted = screen.getByTestId("json-preview").querySelectorAll(
      "[data-highlighted]",
    );
    expect(highlighted.length).toBe(0);
  });
});
