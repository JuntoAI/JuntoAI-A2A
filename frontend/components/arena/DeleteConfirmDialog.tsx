"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { AlertTriangle, Loader2 } from "lucide-react";
import { getScenarioSessionCount } from "@/lib/builder/api";

export interface DeleteConfirmDialogProps {
  isOpen: boolean;
  onClose: () => void;
  scenarioId: string;
  scenarioName: string;
  email: string;
  onConfirm: () => Promise<void>;
}

export function DeleteConfirmDialog({
  isOpen,
  onClose,
  scenarioId,
  scenarioName,
  email,
  onConfirm,
}: DeleteConfirmDialogProps) {
  const [sessionCount, setSessionCount] = useState<number | null>(null);
  const [isFetchingCount, setIsFetchingCount] = useState(false);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  const modalRef = useRef<HTMLDivElement>(null);

  // Fetch session count when dialog opens
  useEffect(() => {
    if (!isOpen) return;

    setSessionCount(null);
    setFetchError(null);
    setIsDeleting(false);
    setIsFetchingCount(true);

    let cancelled = false;

    getScenarioSessionCount(email, scenarioId)
      .then((res) => {
        if (!cancelled) {
          setSessionCount(res.count);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setFetchError(
            err instanceof Error ? err.message : "Failed to fetch session count",
          );
        }
      })
      .finally(() => {
        if (!cancelled) {
          setIsFetchingCount(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [isOpen, email, scenarioId]);

  // Escape key closes dialog (only when not deleting)
  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !isDeleting) {
        onClose();
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, isDeleting, onClose]);

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

  const handleConfirm = useCallback(async () => {
    setIsDeleting(true);
    try {
      await onConfirm();
    } catch {
      setIsDeleting(false);
    }
  }, [onConfirm]);

  const handleCancel = useCallback(() => {
    if (!isDeleting) {
      onClose();
    }
  }, [isDeleting, onClose]);

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
        aria-label="Delete scenario confirmation"
        className="relative mx-4 w-full max-w-md rounded-xl bg-white p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Warning icon + title */}
        <div className="mb-4 flex items-start gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-red-100">
            <AlertTriangle className="h-5 w-5 text-red-600" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-gray-900">
              Delete Scenario
            </h2>
            <p className="mt-0.5 text-sm text-gray-500">
              {scenarioName}
            </p>
          </div>
        </div>

        {/* Session count info */}
        <div className="mb-6">
          {isFetchingCount && (
            <div className="flex items-center gap-2 text-sm text-gray-500">
              <Loader2 className="h-4 w-4 animate-spin" />
              <span>Checking connected simulations…</span>
            </div>
          )}

          {fetchError && (
            <p className="text-sm text-red-600" role="alert">
              {fetchError}
            </p>
          )}

          {!isFetchingCount && fetchError === null && sessionCount !== null && (
            <p className="text-sm text-gray-700">
              {sessionCount > 0
                ? `This will delete ${sessionCount} connected simulation${sessionCount === 1 ? "" : "s"}.`
                : "No connected simulations."}
              {" "}This action cannot be undone.
            </p>
          )}
        </div>

        {/* Actions */}
        <div className="flex items-center justify-end gap-3">
          <button
            type="button"
            onClick={handleCancel}
            disabled={isDeleting}
            className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleConfirm}
            disabled={isDeleting || isFetchingCount}
            className="flex items-center gap-2 rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-red-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isDeleting && <Loader2 className="h-4 w-4 animate-spin" />}
            {isDeleting ? "Deleting…" : "Delete"}
          </button>
        </div>
      </div>
    </div>
  );
}
