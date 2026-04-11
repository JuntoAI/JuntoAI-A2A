"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Loader2 } from "lucide-react";

export interface HealthCheckFindingDisplay {
  check_name: string;
  severity: "critical" | "warning" | "info";
  message: string;
}

export interface SaveCallbacks {
  onHealthStart: () => void;
  onHealthFinding: (finding: HealthCheckFindingDisplay) => void;
  onHealthComplete: (report: { readiness_score: number; tier: string }) => void;
  onError: (message: string) => void;
}

export interface ScenarioEditorModalProps {
  isOpen: boolean;
  onClose: () => void;
  scenarioId: string;
  scenarioJson: Record<string, unknown>;
  onSave: (updated: Record<string, unknown>, callbacks: SaveCallbacks) => Promise<void>;
}

const MAX_NAME_LENGTH = 100;

/**
 * Tokenise a JSON string into spans with syntax-highlight classes.
 * Handles strings, numbers, booleans, null, and structural characters.
 * Unmatched text (whitespace, newlines) is escaped and passed through.
 */
function highlightJson(json: string): string {
  // Match JSON tokens: strings, numbers, booleans, null, punctuation
  const tokenRegex = /("(?:[^"\\]|\\.)*")|(true|false)|(null)|(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)|([{}[\]:,])/g;
  let result = "";
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = tokenRegex.exec(json)) !== null) {
    // Append any text between the last match and this one (whitespace/newlines)
    if (match.index > lastIndex) {
      result += escapeHtml(json.slice(lastIndex, match.index));
    }
    const [, str, bool, nil, num, punct] = match;

    if (str) {
      // Check if this string is a key (followed by optional whitespace then colon)
      const after = json.slice(match.index + match[0].length);
      if (/^\s*:/.test(after)) {
        result += `<span class="json-key">${escapeHtml(str)}</span>`;
      } else {
        result += `<span class="json-string">${escapeHtml(str)}</span>`;
      }
    } else if (bool) {
      result += `<span class="json-bool">${match[0]}</span>`;
    } else if (nil) {
      result += `<span class="json-null">${match[0]}</span>`;
    } else if (num) {
      result += `<span class="json-number">${match[0]}</span>`;
    } else if (punct) {
      result += `<span class="json-punct">${escapeHtml(match[0])}</span>`;
    }

    lastIndex = match.index + match[0].length;
  }

  // Append any remaining text
  if (lastIndex < json.length) {
    result += escapeHtml(json.slice(lastIndex));
  }

  return result;
}

function escapeHtml(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

export function ScenarioEditorModal({
  isOpen,
  onClose,
  scenarioId,
  scenarioJson,
  onSave,
}: ScenarioEditorModalProps) {
  const [jsonText, setJsonText] = useState("");
  const [name, setName] = useState("");
  const [parseError, setParseError] = useState<string | null>(null);
  const [backendErrors, setBackendErrors] = useState<string[]>([]);
  const [isSaving, setIsSaving] = useState(false);
  const [healthChecking, setHealthChecking] = useState(false);
  const [healthFindings, setHealthFindings] = useState<HealthCheckFindingDisplay[]>([]);
  const [healthResult, setHealthResult] = useState<{ readiness_score: number; tier: string } | null>(null);

  const modalRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const highlightRef = useRef<HTMLPreElement>(null);

  // Sync scroll between textarea and highlight layer
  const syncScroll = useCallback(() => {
    if (textareaRef.current && highlightRef.current) {
      highlightRef.current.scrollTop = textareaRef.current.scrollTop;
      highlightRef.current.scrollLeft = textareaRef.current.scrollLeft;
    }
  }, []);

  // Initialize state when modal opens or scenarioJson changes
  useEffect(() => {
    if (isOpen) {
      const formatted = JSON.stringify(scenarioJson, null, 2);
      setJsonText(formatted);
      setName(typeof scenarioJson.name === "string" ? scenarioJson.name : "");
      setParseError(null);
      setBackendErrors([]);
      setIsSaving(false);
      setHealthChecking(false);
      setHealthFindings([]);
      setHealthResult(null);
    }
  }, [isOpen, scenarioJson]);

  // Focus textarea when modal opens
  useEffect(() => {
    if (isOpen && textareaRef.current) {
      textareaRef.current.focus();
    }
  }, [isOpen]);

  // Escape key closes modal (only when not saving)
  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !isSaving) {
        onClose();
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, isSaving, onClose]);

  // Focus trap
  useEffect(() => {
    if (!isOpen || !modalRef.current) return;
    const handleFocusTrap = (e: KeyboardEvent) => {
      if (e.key !== "Tab") return;
      const focusableElements = modalRef.current!.querySelectorAll<HTMLElement>(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
      );
      if (focusableElements.length === 0) return;
      const first = focusableElements[0];
      const last = focusableElements[focusableElements.length - 1];
      if (e.shiftKey) {
        if (document.activeElement === first) { e.preventDefault(); last.focus(); }
      } else {
        if (document.activeElement === last) { e.preventDefault(); first.focus(); }
      }
    };
    document.addEventListener("keydown", handleFocusTrap);
    return () => document.removeEventListener("keydown", handleFocusTrap);
  }, [isOpen]);

  // When the name field changes, update the name inside the JSON text
  const handleNameChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const newName = e.target.value.slice(0, MAX_NAME_LENGTH);
      setName(newName);
      try {
        const parsed = JSON.parse(jsonText);
        parsed.name = newName;
        setJsonText(JSON.stringify(parsed, null, 2));
        setParseError(null);
      } catch {
        // JSON is currently invalid — just update the name state
      }
    },
    [jsonText],
  );

  // When the JSON textarea changes, validate and sync name
  const handleJsonChange = useCallback(
    (e: React.ChangeEvent<HTMLTextAreaElement>) => {
      const text = e.target.value;
      setJsonText(text);
      setBackendErrors([]);
      try {
        const parsed = JSON.parse(text);
        setParseError(null);
        if (typeof parsed.name === "string") {
          setName(parsed.name);
        }
      } catch (err) {
        setParseError(
          err instanceof Error ? err.message : "Invalid JSON syntax",
        );
      }
    },
    [],
  );

  // Handle Tab key for indentation instead of focus change
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Tab") {
        e.preventDefault();
        const ta = e.currentTarget;
        const start = ta.selectionStart;
        const end = ta.selectionEnd;
        const newText = jsonText.substring(0, start) + "  " + jsonText.substring(end);
        setJsonText(newText);
        // Restore cursor position after React re-render
        requestAnimationFrame(() => {
          ta.selectionStart = ta.selectionEnd = start + 2;
        });
      }
    },
    [jsonText],
  );

  const handleSave = useCallback(async () => {
    let parsed: Record<string, unknown>;
    try {
      parsed = JSON.parse(jsonText);
    } catch {
      setParseError("Invalid JSON — cannot save");
      return;
    }
    setIsSaving(true);
    setBackendErrors([]);
    setHealthChecking(false);
    setHealthFindings([]);
    setHealthResult(null);

    const callbacks: SaveCallbacks = {
      onHealthStart: () => setHealthChecking(true),
      onHealthFinding: (f) => setHealthFindings((prev) => [...prev, f]),
      onHealthComplete: (report) => {
        setHealthChecking(false);
        setHealthResult({ readiness_score: report.readiness_score, tier: report.tier });
      },
      onError: (msg) => setBackendErrors((prev) => [...prev, msg]),
    };

    try {
      await onSave(parsed, callbacks);
    } catch (err) {
      // Display backend validation errors inline — split newlines into separate items
      const message = err instanceof Error ? err.message : String(err);
      setBackendErrors(message.split("\n").filter(Boolean));
    } finally {
      setIsSaving(false);
      setHealthChecking(false);
    }
  }, [jsonText, onSave]);

  const handleCancel = useCallback(() => {
    if (!isSaving) {
      onClose();
    }
  }, [isSaving, onClose]);

  const hasParseError = parseError !== null;
  const isSaveDisabled = hasParseError || isSaving;

  if (!isOpen) return null;

  // Build highlighted HTML — append a newline so the pre always matches textarea height
  const highlighted = highlightJson(jsonText) + "\n";

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      onClick={handleCancel}
      role="presentation"
    >
      <div
        ref={modalRef}
        role="dialog"
        aria-modal="true"
        aria-label="Edit scenario JSON"
        className="relative mx-4 flex w-full max-w-2xl flex-col rounded-xl bg-white p-6 shadow-xl"
        style={{ maxHeight: "90vh" }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="mb-4">
          <h2 className="text-lg font-semibold text-gray-900">Edit Scenario</h2>
          <p className="mt-0.5 text-xs text-gray-400">{scenarioId}</p>
        </div>

        {/* Inline name field */}
        <div className="mb-4">
          <label
            htmlFor="scenario-name"
            className="mb-1.5 block text-sm font-medium text-gray-700"
          >
            Scenario Name
          </label>
          <input
            id="scenario-name"
            type="text"
            value={name}
            onChange={handleNameChange}
            maxLength={MAX_NAME_LENGTH}
            disabled={isSaving}
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:border-brand-blue focus:outline-none focus:ring-1 focus:ring-brand-blue disabled:cursor-not-allowed disabled:opacity-50"
            placeholder="Scenario name"
          />
          <p className="mt-1 text-right text-xs text-gray-400">
            {name.length} / {MAX_NAME_LENGTH}
          </p>
        </div>

        {/* Syntax-highlighted JSON editor */}
        <div className="mb-4 flex-1">
          <label
            htmlFor="scenario-json"
            className="mb-1.5 block text-sm font-medium text-gray-700"
          >
            Scenario JSON
          </label>
          <div
            className={`relative rounded-lg border overflow-hidden ${
              hasParseError
                ? "border-red-500 focus-within:border-red-500 focus-within:ring-1 focus-within:ring-red-500"
                : "border-gray-300 focus-within:border-brand-blue focus-within:ring-1 focus-within:ring-brand-blue"
            }`}
            style={{ backgroundColor: "#1e1e2e" }}
          >
            {/* Highlight layer (behind) */}
            <pre
              ref={highlightRef}
              aria-hidden="true"
              className="pointer-events-none absolute inset-0 m-0 overflow-hidden whitespace-pre-wrap break-words p-3 font-mono text-sm leading-[1.625]"
              dangerouslySetInnerHTML={{ __html: highlighted }}
            />
            {/* Editable textarea (on top, transparent text) */}
            <textarea
              ref={textareaRef}
              id="scenario-json"
              value={jsonText}
              onChange={handleJsonChange}
              onScroll={syncScroll}
              onKeyDown={handleKeyDown}
              disabled={isSaving}
              spellCheck={false}
              className="relative z-10 m-0 min-h-[340px] w-full resize-y whitespace-pre-wrap break-words bg-transparent p-3 font-mono text-sm leading-[1.625] text-transparent caret-white outline-none disabled:cursor-not-allowed"
            />
          </div>

          {/* Parse error */}
          {hasParseError && (
            <p className="mt-1.5 text-sm text-red-600" role="alert">
              {parseError}
            </p>
          )}

          {/* Backend validation errors */}
          {backendErrors.length > 0 && (
            <div className="mt-2 rounded-md border border-red-200 bg-red-50 p-3" role="alert">
              <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-red-700">
                Validation errors ({backendErrors.length})
              </p>
              <ul className="list-none space-y-1">
                {backendErrors.map((err, i) => (
                  <li key={i} className="font-mono text-xs text-red-600">
                    • {err}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        {/* Health check progress */}
        {(healthChecking || healthFindings.length > 0 || healthResult) && (
          <div className="mb-4 rounded-lg border border-gray-200 bg-gray-50 p-3">
            <div className="mb-2 flex items-center gap-2">
              {healthChecking && <Loader2 className="h-3.5 w-3.5 animate-spin text-brand-blue" />}
              <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">
                {healthChecking ? "Running quality audit…" : "Quality Audit"}
              </p>
              {healthResult && (
                <span
                  className={`ml-auto rounded-full px-2 py-0.5 text-xs font-medium ${
                    healthResult.tier === "Ready"
                      ? "bg-green-100 text-green-700"
                      : healthResult.tier === "Needs Work"
                        ? "bg-yellow-100 text-yellow-700"
                        : "bg-red-100 text-red-700"
                  }`}
                >
                  {healthResult.readiness_score}/100 — {healthResult.tier}
                </span>
              )}
            </div>
            {healthFindings.length > 0 && (
              <ul className="max-h-32 space-y-1 overflow-y-auto">
                {healthFindings.map((f, i) => (
                  <li key={i} className="flex items-start gap-1.5 text-xs">
                    <span
                      className={`mt-0.5 inline-block h-1.5 w-1.5 shrink-0 rounded-full ${
                        f.severity === "critical"
                          ? "bg-red-500"
                          : f.severity === "warning"
                            ? "bg-yellow-500"
                            : "bg-blue-400"
                      }`}
                    />
                    <span className="text-gray-600">{f.message}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        {/* Actions */}
        <div className="flex items-center justify-end gap-3">
          <button
            type="button"
            onClick={handleCancel}
            disabled={isSaving}
            className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSave}
            disabled={isSaveDisabled}
            className="flex items-center gap-2 rounded-lg bg-brand-blue px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-600 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isSaving && <Loader2 className="h-4 w-4 animate-spin" />}
            {isSaving ? "Saving…" : "Save"}
          </button>
        </div>
      </div>
    </div>
  );
}
