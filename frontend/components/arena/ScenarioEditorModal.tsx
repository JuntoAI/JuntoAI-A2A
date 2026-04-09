"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Loader2 } from "lucide-react";

export interface ScenarioEditorModalProps {
  isOpen: boolean;
  onClose: () => void;
  scenarioId: string;
  scenarioJson: Record<string, unknown>;
  onSave: (updated: Record<string, unknown>) => Promise<void>;
}

const MAX_NAME_LENGTH = 100;

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

  const modalRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Initialize state when modal opens or scenarioJson changes
  useEffect(() => {
    if (isOpen) {
      const formatted = JSON.stringify(scenarioJson, null, 2);
      setJsonText(formatted);
      setName(typeof scenarioJson.name === "string" ? scenarioJson.name : "");
      setParseError(null);
      setBackendErrors([]);
      setIsSaving(false);
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

      // Try to update the name inside the JSON text
      try {
        const parsed = JSON.parse(jsonText);
        parsed.name = newName;
        setJsonText(JSON.stringify(parsed, null, 2));
        setParseError(null);
      } catch {
        // JSON is currently invalid — just update the name state,
        // user will fix JSON separately
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
        // Sync name field from parsed JSON
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

  const handleSave = useCallback(async () => {
    // Final parse check
    let parsed: Record<string, unknown>;
    try {
      parsed = JSON.parse(jsonText);
    } catch {
      setParseError("Invalid JSON — cannot save");
      return;
    }

    setIsSaving(true);
    setBackendErrors([]);

    try {
      await onSave(parsed);
    } catch (err) {
      // Display backend validation errors inline
      const message = err instanceof Error ? err.message : String(err);
      setBackendErrors([message]);
    } finally {
      setIsSaving(false);
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

        {/* JSON textarea */}
        <div className="mb-4 flex-1">
          <label
            htmlFor="scenario-json"
            className="mb-1.5 block text-sm font-medium text-gray-700"
          >
            Scenario JSON
          </label>
          <textarea
            ref={textareaRef}
            id="scenario-json"
            value={jsonText}
            onChange={handleJsonChange}
            disabled={isSaving}
            spellCheck={false}
            className={`w-full min-h-[300px] rounded-lg border px-3 py-2 font-mono text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-1 resize-y disabled:cursor-not-allowed disabled:opacity-50 ${
              hasParseError
                ? "border-red-500 focus:border-red-500 focus:ring-red-500"
                : "border-gray-300 focus:border-brand-blue focus:ring-brand-blue"
            }`}
          />

          {/* Parse error */}
          {hasParseError && (
            <p className="mt-1.5 text-sm text-red-600" role="alert">
              {parseError}
            </p>
          )}

          {/* Backend validation errors */}
          {backendErrors.length > 0 && (
            <div className="mt-1.5 space-y-1" role="alert">
              {backendErrors.map((err, i) => (
                <p key={i} className="text-sm text-red-600">
                  {err}
                </p>
              ))}
            </div>
          )}
        </div>

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
