// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * ErrorAlert -- displays an error message with a retry button.
 *
 * Used across dashboard views when API requests fail.
 */

"use client";

interface ErrorAlertProps {
  /** Error message to display. */
  message: string;
  /** Optional callback to retry the failed operation. */
  onRetry?: () => void;
}

/** Error alert banner with optional retry action. */
export default function ErrorAlert({ message, onRetry }: ErrorAlertProps) {
  return (
    <div
      className="rounded-lg border border-red-200 bg-red-50 p-4"
      role="alert"
    >
      <div className="flex items-start gap-3">
        <svg
          className="h-5 w-5 flex-shrink-0 text-red-600"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
          aria-hidden="true"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z"
          />
        </svg>
        <div className="flex-1">
          <h3 className="text-sm font-semibold text-red-800">
            Something went wrong
          </h3>
          <p className="mt-1 text-sm text-red-700">{message}</p>
        </div>
        {onRetry && (
          <button
            onClick={onRetry}
            className="rounded-md bg-red-100 px-3 py-1.5 text-sm font-medium text-red-800 hover:bg-red-200 transition-colors"
          >
            Retry
          </button>
        )}
      </div>
    </div>
  );
}
