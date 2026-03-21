// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * ApprovalActions -- Approve/Reject buttons for held actions.
 *
 * Provides action buttons with confirmation state and loading feedback.
 * Includes "Approve with Note" option for adding decision context.
 * Calls the PACT API to approve or reject the held action.
 */

"use client";

import { useState } from "react";

interface ApprovalActionsProps {
  /** Agent ID owning the action. */
  agentId: string;
  /** Action ID to approve or reject. */
  actionId: string;
  /** Callback when an action is resolved (approved or rejected). */
  onResolved: (actionId: string, decision: "approved" | "rejected") => void;
  /** Callback to perform the API approve call. Accepts optional reason. */
  onApprove: (
    agentId: string,
    actionId: string,
    reason?: string,
  ) => Promise<void>;
  /** Callback to perform the API reject call. Accepts optional reason. */
  onReject: (
    agentId: string,
    actionId: string,
    reason?: string,
  ) => Promise<void>;
}

/** Approve/Reject button pair for a held action with optional note. */
export default function ApprovalActions({
  agentId,
  actionId,
  onResolved,
  onApprove,
  onReject,
}: ApprovalActionsProps) {
  const [processing, setProcessing] = useState(false);
  const [resolved, setResolved] = useState<"approved" | "rejected" | null>(
    null,
  );
  const [error, setError] = useState<string | null>(null);
  const [showNoteInput, setShowNoteInput] = useState(false);
  const [note, setNote] = useState("");

  const handleAction = async (
    decision: "approved" | "rejected",
    reason?: string,
  ) => {
    setProcessing(true);
    setError(null);

    try {
      if (decision === "approved") {
        await onApprove(agentId, actionId, reason);
      } else {
        await onReject(agentId, actionId, reason);
      }
      setResolved(decision);
      onResolved(actionId, decision);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to process action");
    } finally {
      setProcessing(false);
    }
  };

  if (resolved) {
    return (
      <span
        className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium ${
          resolved === "approved"
            ? "bg-green-100 text-green-800"
            : "bg-red-100 text-red-800"
        }`}
      >
        {resolved === "approved" ? "Approved" : "Rejected"}
      </span>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      {showNoteInput ? (
        <div className="space-y-2">
          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Add a note for this decision..."
            disabled={processing}
            rows={2}
            aria-label="Decision note"
            className="w-full rounded-md border border-gray-300 px-3 py-1.5 text-xs text-gray-900 placeholder:text-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:opacity-50"
          />
          <div className="flex gap-2">
            <button
              onClick={() => handleAction("approved", note || undefined)}
              disabled={processing}
              className="rounded-md bg-green-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-green-700 disabled:opacity-50 transition-colors"
            >
              {processing ? "..." : "Approve"}
            </button>
            <button
              onClick={() => handleAction("rejected", note || undefined)}
              disabled={processing}
              className="rounded-md bg-red-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-red-700 disabled:opacity-50 transition-colors"
            >
              {processing ? "..." : "Reject"}
            </button>
            <button
              onClick={() => {
                setShowNoteInput(false);
                setNote("");
              }}
              disabled={processing}
              className="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-xs font-medium text-gray-600 hover:bg-gray-50 disabled:opacity-50 transition-colors"
            >
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <div className="flex gap-2">
          <button
            onClick={() => handleAction("approved")}
            disabled={processing}
            className="rounded-md bg-green-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-green-700 disabled:opacity-50 transition-colors"
          >
            {processing ? "..." : "Approve"}
          </button>
          <button
            onClick={() => handleAction("rejected")}
            disabled={processing}
            className="rounded-md bg-red-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-red-700 disabled:opacity-50 transition-colors"
          >
            {processing ? "..." : "Reject"}
          </button>
          <button
            onClick={() => setShowNoteInput(true)}
            disabled={processing}
            className="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-xs font-medium text-gray-600 hover:bg-gray-50 disabled:opacity-50 transition-colors"
            title="Add a note with your decision"
          >
            With Note
          </button>
        </div>
      )}
      {error && <p className="text-xs text-red-600">{error}</p>}
    </div>
  );
}
