"use client";

import { useMemo } from "react";
import type { ArenaScenario } from "@/lib/api";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export interface JsonPreviewProps {
  scenarioJson: Partial<ArenaScenario>;
  highlightedSection: string | null;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const SECTIONS: (keyof ArenaScenario)[] = [
  "id",
  "name",
  "description",
  "agents",
  "toggles",
  "negotiation_params",
  "outcome_receipt",
];

const PLACEHOLDER = "<not yet defined>";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Build a full object with placeholders for missing sections. */
function buildPreviewObject(
  partial: Partial<ArenaScenario>,
): Record<string, unknown> {
  const result: Record<string, unknown> = {};
  for (const key of SECTIONS) {
    const value = partial[key];
    const populated =
      value !== undefined &&
      value !== null &&
      value !== "" &&
      !(Array.isArray(value) && value.length === 0) &&
      !(typeof value === "object" && !Array.isArray(value) && Object.keys(value as object).length === 0);
    result[key] = populated ? value : PLACEHOLDER;
  }
  return result;
}

// ---------------------------------------------------------------------------
// Syntax highlighting
// ---------------------------------------------------------------------------

interface TokenSpan {
  text: string;
  className: string;
}


/** Tokenize a JSON string into spans with Tailwind color classes. */
function highlightJson(json: string): TokenSpan[] {
  const spans: TokenSpan[] = [];
  // Regex matches: strings, numbers, booleans, null, and structural chars
  const tokenRegex =
    /("(?:[^"\\]|\\.)*")\s*:|("(?:[^"\\]|\\.)*")|(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)\b|(true|false|null)\b|([{}[\]:,])|(\s+)/g;

  let match: RegExpExecArray | null;
  let lastIndex = 0;

  while ((match = tokenRegex.exec(json)) !== null) {
    // Capture any gap (shouldn't happen with well-formed JSON, but safety)
    if (match.index > lastIndex) {
      spans.push({ text: json.slice(lastIndex, match.index), className: "text-gray-400" });
    }
    lastIndex = tokenRegex.lastIndex;

    if (match[1] !== undefined) {
      // Key (string followed by colon)
      spans.push({ text: match[1], className: "text-purple-400" });
      // The colon and optional space after the key
      const afterKey = json.slice(match.index + match[1].length, lastIndex);
      if (afterKey) {
        spans.push({ text: afterKey, className: "text-gray-400" });
      }
    } else if (match[2] !== undefined) {
      // String value
      const isPlaceholder = match[2] === `"${PLACEHOLDER}"`;
      spans.push({
        text: match[2],
        className: isPlaceholder ? "text-yellow-500 italic" : "text-green-400",
      });
    } else if (match[3] !== undefined) {
      // Number
      spans.push({ text: match[3], className: "text-blue-400" });
    } else if (match[4] !== undefined) {
      // Boolean / null
      spans.push({ text: match[4], className: "text-orange-400" });
    } else if (match[5] !== undefined) {
      // Structural characters
      spans.push({ text: match[5], className: "text-gray-400" });
    } else if (match[6] !== undefined) {
      // Whitespace
      spans.push({ text: match[6], className: "" });
    }
  }

  // Trailing content
  if (lastIndex < json.length) {
    spans.push({ text: json.slice(lastIndex), className: "text-gray-400" });
  }

  return spans;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function JsonPreview({ scenarioJson, highlightedSection }: JsonPreviewProps) {
  const previewObj = useMemo(() => buildPreviewObject(scenarioJson), [scenarioJson]);
  const jsonString = useMemo(() => JSON.stringify(previewObj, null, 2), [previewObj]);
  const tokens = useMemo(() => highlightJson(jsonString), [jsonString]);

  // Split JSON into lines and determine which lines belong to the highlighted section
  const lines = useMemo(() => {
    const rawLines = jsonString.split("\n");
    const lineHighlights: boolean[] = new Array(rawLines.length).fill(false);

    if (highlightedSection) {
      const sectionKey = `"${highlightedSection}"`;
      let inSection = false;
      let braceDepth = 0;
      let bracketDepth = 0;

      for (let i = 0; i < rawLines.length; i++) {
        const trimmed = rawLines[i].trimStart();
        if (!inSection && trimmed.startsWith(sectionKey)) {
          inSection = true;
          lineHighlights[i] = true;
          // Count opening/closing braces on this line
          for (const ch of rawLines[i]) {
            if (ch === "{") braceDepth++;
            else if (ch === "}") braceDepth--;
            else if (ch === "[") bracketDepth++;
            else if (ch === "]") bracketDepth--;
          }
          // If it's a simple value (no nested structure), just highlight this line
          if (braceDepth === 0 && bracketDepth === 0) {
            inSection = false;
          }
          continue;
        }
        if (inSection) {
          lineHighlights[i] = true;
          for (const ch of rawLines[i]) {
            if (ch === "{") braceDepth++;
            else if (ch === "}") braceDepth--;
            else if (ch === "[") bracketDepth++;
            else if (ch === "]") bracketDepth--;
          }
          if (braceDepth <= 0 && bracketDepth <= 0) {
            inSection = false;
          }
        }
      }
    }

    return { rawLines, lineHighlights };
  }, [jsonString, highlightedSection]);

  // Build highlighted output per line
  const renderedLines = useMemo(() => {
    let charOffset = 0;
    return lines.rawLines.map((line, lineIdx) => {
      const lineStart = charOffset;
      // +1 for the newline character (except last line)
      charOffset += line.length + (lineIdx < lines.rawLines.length - 1 ? 1 : 0);
      const lineEnd = lineStart + line.length;

      // Collect tokens that overlap this line
      const lineTokens: TokenSpan[] = [];
      let pos = 0;
      for (const token of tokens) {
        const tokenStart = pos;
        const tokenEnd = pos + token.text.length;
        pos = tokenEnd;

        // Check overlap with this line
        if (tokenEnd <= lineStart || tokenStart >= lineEnd) continue;

        const overlapStart = Math.max(tokenStart, lineStart);
        const overlapEnd = Math.min(tokenEnd, lineEnd);
        const text = token.text.slice(
          overlapStart - tokenStart,
          overlapEnd - tokenStart,
        );
        if (text) {
          lineTokens.push({ text, className: token.className });
        }
      }

      return {
        tokens: lineTokens,
        highlighted: lines.lineHighlights[lineIdx],
      };
    });
  }, [lines, tokens]);

  return (
    <div
      className="h-full overflow-y-auto overflow-x-auto rounded-lg bg-[#1C1C1E] p-4 font-mono text-sm"
      data-testid="json-preview"
    >
      <pre className="whitespace-pre">
        {renderedLines.map((line, i) => (
          <div
            key={i}
            className={
              line.highlighted
                ? "transition-colors duration-[2000ms] bg-blue-900/30"
                : "transition-colors duration-[2000ms] bg-transparent"
            }
            data-highlighted={line.highlighted || undefined}
          >
            {line.tokens.length > 0
              ? line.tokens.map((t, j) => (
                  <span key={j} className={t.className}>
                    {t.text}
                  </span>
                ))
              : "\n"}
          </div>
        ))}
      </pre>
    </div>
  );
}

// Export helpers for testing
export { buildPreviewObject, highlightJson, SECTIONS, PLACEHOLDER };
