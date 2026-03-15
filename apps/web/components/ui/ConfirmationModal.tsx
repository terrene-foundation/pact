// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * ConfirmationModal -- reusable modal dialog for governance actions.
 *
 * Replaces window.prompt/window.confirm with a proper accessible modal.
 * Supports: title, description, optional text input for reason, loading state,
 * and Cancel/Confirm buttons with customizable labels and colors.
 */

"use client";

import { useState, useEffect, useRef, useCallback } from "react";

export interface ConfirmationModalProps {
  /** Whether the modal is open. */
  open: boolean;
  /** Callback to close the modal. */
  onClose: () => void;
  /** Callback when confirmed. Receives the input value if inputRequired is true. */
  onConfirm: (value: string) => void | Promise<void>;
  /** Modal title. */
  title: string;
  /** Modal description/body text. */
  description: string;
  /** Label for the confirm button. Defaults to "Confirm". */
  confirmLabel?: string;
  /** Label for the cancel button. Defaults to "Cancel". */
  cancelLabel?: string;
  /** Whether the confirm action is destructive (shows red button). */
  destructive?: boolean;
  /** Whether a text input is shown and required before confirming. */
  inputRequired?: boolean;
  /** Placeholder text for the input field. */
  inputPlaceholder?: string;
  /** Label for the input field. */
  inputLabel?: string;
  /** External loading state (overrides internal). */
  loading?: boolean;
}

/** Reusable confirmation modal with optional reason input. */
export default function ConfirmationModal({
  open,
  onClose,
  onConfirm,
  title,
  description,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  destructive = false,
  inputRequired = false,
  inputPlaceholder = "Enter reason...",
  inputLabel = "Reason",
  loading: externalLoading,
}: ConfirmationModalProps) {
  const [inputValue, setInputValue] = useState("");
  const [internalLoading, setInternalLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const backdropRef = useRef<HTMLDivElement>(null);

  const loading = externalLoading ?? internalLoading;

  // Reset state when modal opens/closes
  useEffect(() => {
    if (open) {
      setInputValue("");
      setError(null);
      setInternalLoading(false);
      // Focus the input after render
      requestAnimationFrame(() => {
        inputRef.current?.focus();
      });
    }
  }, [open]);

  // Close on Escape and trap focus within the modal
  useEffect(() => {
    if (!open) return;

    // Store the element that triggered the modal to restore focus on close
    const previouslyFocused = document.activeElement as HTMLElement | null;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !loading) {
        onClose();
        return;
      }

      // Focus trap: cycle Tab focus within the modal dialog
      if (e.key === "Tab" && backdropRef.current) {
        const modal = backdropRef.current.querySelector('[class*="max-w-md"]');
        if (!modal) return;
        const focusable = modal.querySelectorAll<HTMLElement>(
          'button:not([disabled]), textarea:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])',
        );
        if (focusable.length === 0) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      // Restore focus to the triggering element
      previouslyFocused?.focus();
    };
  }, [open, loading, onClose]);

  const handleConfirm = useCallback(async () => {
    if (inputRequired && !inputValue.trim()) {
      setError("A reason is required.");
      return;
    }

    setError(null);
    setInternalLoading(true);

    try {
      await onConfirm(inputValue.trim());
    } catch (err: unknown) {
      setError(
        err instanceof Error ? err.message : "Action failed. Please try again.",
      );
    } finally {
      setInternalLoading(false);
    }
  }, [inputRequired, inputValue, onConfirm]);

  const handleBackdropClick = useCallback(
    (e: React.MouseEvent) => {
      if (e.target === backdropRef.current && !loading) {
        onClose();
      }
    },
    [loading, onClose],
  );

  if (!open) return null;

  const confirmButtonClass = destructive
    ? "bg-red-600 hover:bg-red-700 focus:ring-red-500"
    : "bg-blue-600 hover:bg-blue-700 focus:ring-blue-500";

  return (
    <div
      ref={backdropRef}
      onClick={handleBackdropClick}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="modal-title"
      aria-describedby="modal-description"
    >
      <div className="w-full max-w-md rounded-lg border border-gray-200 bg-white shadow-xl">
        {/* Header */}
        <div className="border-b border-gray-100 px-6 py-4">
          <h2 id="modal-title" className="text-lg font-semibold text-gray-900">
            {title}
          </h2>
        </div>

        {/* Body */}
        <div className="px-6 py-4 space-y-4">
          <p id="modal-description" className="text-sm text-gray-600">
            {description}
          </p>

          {inputRequired && (
            <div>
              <label
                htmlFor="modal-input"
                className="block text-sm font-medium text-gray-700 mb-1"
              >
                {inputLabel}
              </label>
              <textarea
                ref={inputRef}
                id="modal-input"
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                placeholder={inputPlaceholder}
                disabled={loading}
                rows={3}
                className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:opacity-50"
              />
            </div>
          )}

          {error && (
            <p className="text-sm text-red-600" role="alert">
              {error}
            </p>
          )}
        </div>

        {/* Footer */}
        <div className="flex justify-end gap-3 border-t border-gray-100 px-6 py-4">
          <button
            onClick={onClose}
            disabled={loading}
            className="rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 transition-colors"
          >
            {cancelLabel}
          </button>
          <button
            onClick={handleConfirm}
            disabled={loading || (inputRequired && !inputValue.trim())}
            className={`rounded-md px-4 py-2 text-sm font-medium text-white disabled:opacity-50 transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2 ${confirmButtonClass}`}
          >
            {loading ? (
              <span className="flex items-center gap-2">
                <svg
                  className="h-4 w-4 animate-spin"
                  fill="none"
                  viewBox="0 0 24 24"
                >
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                  />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                  />
                </svg>
                Processing...
              </span>
            ) : (
              confirmLabel
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
