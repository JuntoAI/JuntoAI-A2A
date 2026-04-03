"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { ModelInfo } from "@/lib/api";

export interface AdvancedConfigModalProps {
  isOpen: boolean;
  agentName: string;
  agentRole: string;
  defaultModelId: string;
  availableModels: ModelInfo[];
  initialCustomPrompt: string;
  initialModelOverride: string | null;
  initialStructuredMemory: boolean;
  onSave: (customPrompt: string, modelOverride: string | null, structuredMemory: boolean) => void;
  onCancel: () => void;
}

const MAX_PROMPT_LENGTH = 500;

export function AdvancedConfigModal({
  isOpen,
  agentName,
  agentRole,
  defaultModelId,
  availableModels,
  initialCustomPrompt,
  initialModelOverride,
  initialStructuredMemory,
  onSave,
  onCancel,
}: AdvancedConfigModalProps) {
  const [customPrompt, setCustomPrompt] = useState(initialCustomPrompt);
  const [selectedModelId, setSelectedModelId] = useState<string>(
    initialModelOverride ?? defaultModelId,
  );
  const [structuredMemory, setStructuredMemory] = useState(initialStructuredMemory);

  const modalRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Sync local state when modal opens with new initial values
  useEffect(() => {
    if (isOpen) {
      setCustomPrompt(initialCustomPrompt);
      setSelectedModelId(initialModelOverride ?? defaultModelId);
      setStructuredMemory(initialStructuredMemory);
    }
  }, [isOpen, initialCustomPrompt, initialModelOverride, defaultModelId, initialStructuredMemory]);

  // Focus textarea when modal opens
  useEffect(() => {
    if (isOpen && textareaRef.current) {
      textareaRef.current.focus();
    }
  }, [isOpen]);

  // Escape key closes modal
  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onCancel();
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onCancel]);

  // Focus trap: cycle focus within modal on Tab/Shift+Tab
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
        if (document.activeElement === first) {
          e.preventDefault();
          last.focus();
        }
      } else {
        if (document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };

    document.addEventListener("keydown", handleFocusTrap);
    return () => document.removeEventListener("keydown", handleFocusTrap);
  }, [isOpen]);

  const handlePromptChange = useCallback(
    (e: React.ChangeEvent<HTMLTextAreaElement>) => {
      const value = e.target.value;
      setCustomPrompt(value.slice(0, MAX_PROMPT_LENGTH));
    },
    [],
  );

  const handlePaste = useCallback(
    (e: React.ClipboardEvent<HTMLTextAreaElement>) => {
      e.preventDefault();
      const pastedText = e.clipboardData.getData("text");
      const textarea = e.currentTarget;
      const start = textarea.selectionStart;
      const end = textarea.selectionEnd;
      const currentValue = customPrompt;
      const newValue =
        currentValue.slice(0, start) + pastedText + currentValue.slice(end);
      setCustomPrompt(newValue.slice(0, MAX_PROMPT_LENGTH));
    },
    [customPrompt],
  );

  const handleSave = useCallback(() => {
    const modelOverride =
      selectedModelId === defaultModelId ? null : selectedModelId;
    onSave(customPrompt, modelOverride, structuredMemory);
  }, [customPrompt, selectedModelId, defaultModelId, onSave, structuredMemory]);

  // Build sorted model options: default first, then rest
  const sortedModels = buildSortedModels(availableModels, defaultModelId);

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      onClick={onCancel}
      role="presentation"
    >
      <div
        ref={modalRef}
        role="dialog"
        aria-modal="true"
        aria-label={`Advanced configuration for ${agentName}`}
        className="relative mx-4 w-full max-h-[90vh] overflow-y-auto rounded-xl bg-white p-6 shadow-xl lg:max-w-[480px]"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="mb-5">
          <h2 className="text-lg font-semibold text-gray-900">
            Advanced Config
          </h2>
          <p className="mt-1 text-sm text-gray-500">
            {agentName} &middot; {agentRole}
          </p>
        </div>

        {/* Custom Prompt */}
        <div className="mb-5">
          <label
            htmlFor="custom-prompt"
            className="mb-1.5 block text-sm font-medium text-gray-700"
          >
            Custom Prompt
          </label>
          <textarea
            ref={textareaRef}
            id="custom-prompt"
            value={customPrompt}
            onChange={handlePromptChange}
            onPaste={handlePaste}
            maxLength={MAX_PROMPT_LENGTH}
            placeholder="e.g., Be more aggressive in counter-offers and always cite market data to justify your position."
            className="w-full min-h-[120px] rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:border-brand-blue focus:outline-none focus:ring-1 focus:ring-brand-blue resize-y"
          />
          <p className="mt-1 text-right text-xs text-gray-400">
            {customPrompt.length} / {MAX_PROMPT_LENGTH}
          </p>
        </div>

        {/* Model Selector */}
        <div className="mb-5">
          <label
            htmlFor="model-selector"
            className="mb-1.5 block text-sm font-medium text-gray-700"
          >
            Model
          </label>
          <select
            id="model-selector"
            value={selectedModelId}
            onChange={(e) => setSelectedModelId(e.target.value)}
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 focus:border-brand-blue focus:outline-none focus:ring-1 focus:ring-brand-blue"
          >
            {sortedModels.map(({ model_id, family, isDefault }) => (
              <option key={model_id} value={model_id}>
                {model_id} ({family}){isDefault ? " (default)" : ""}
              </option>
            ))}
          </select>
        </div>

        {/* Structured Memory */}
        <div className="mb-6">
          <label
            htmlFor="structured-memory-toggle"
            className="flex cursor-pointer items-center gap-3 text-sm text-gray-700"
          >
            <input
              id="structured-memory-toggle"
              type="checkbox"
              checked={structuredMemory}
              onChange={(e) => setStructuredMemory(e.target.checked)}
              className="h-4 w-4 rounded border-gray-300 text-brand-blue focus:ring-brand-blue"
            />
            <div>
              <span className="font-medium">Structured Agent Memory</span>
              <p className="mt-0.5 text-xs text-gray-500">
                This agent maintains structured recall of offers, concessions, and tactics instead of replaying full history each turn
              </p>
            </div>
          </label>
        </div>

        {/* Actions */}
        <div className="flex items-center justify-end gap-3">
          <button
            type="button"
            onClick={onCancel}
            className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSave}
            className="rounded-lg bg-brand-blue px-4 py-2 text-sm font-medium text-white hover:bg-blue-600 transition-colors"
          >
            Save
          </button>
        </div>
      </div>
    </div>
  );
}

interface SortedModel {
  model_id: string;
  family: string;
  isDefault: boolean;
}

function buildSortedModels(
  availableModels: ModelInfo[],
  defaultModelId: string,
): SortedModel[] {
  const defaultModel = availableModels.find(
    (m) => m.model_id === defaultModelId,
  );
  const rest = availableModels.filter((m) => m.model_id !== defaultModelId);

  const sorted: SortedModel[] = [];

  if (defaultModel) {
    sorted.push({ ...defaultModel, isDefault: true });
  } else {
    // Fallback: if default model not in available list, still show it
    const family = defaultModelId.split("-")[0];
    sorted.push({ model_id: defaultModelId, family, isDefault: true });
  }

  for (const m of rest) {
    sorted.push({ ...m, isDefault: false });
  }

  return sorted;
}
