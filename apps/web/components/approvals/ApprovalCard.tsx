// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * ApprovalCard -- card showing a held action with agent, action, reason,
 * decision context (agent posture, urgency), and approve/reject controls
 * including "Approve with Note" option.
 */

"use client";

import ApprovalActions from "./ApprovalActions";
import StatusBadge from "../ui/StatusBadge";
import PostureBadge from "../agents/PostureBadge";
import type { TrustPosture } from "../../types/pact";

/** Held action data shape (matches API response). */
export interface HeldAction {
  action_id: string;
  agent_id: string;
  team_id: string;
  action: string;
  reason: string;
  urgency: string;
  submitted_at: string;
  /** Optional: agent's current posture (enriched by parent). */
  agent_posture?: TrustPosture;
  /** Optional: agent's constraint utilization percentage (enriched by parent). */
  constraint_utilization?: number;
  /** Optional: agent's recent pass rate as a fraction 0-1 (enriched by parent). */
  pass_rate?: number;
}

interface ApprovalCardProps {
  /** The held action to display. */
  item: HeldAction;
  /** Callback when the action is resolved. */
  onResolved: (actionId: string, decision: "approved" | "rejected") => void;
  /** Callback for approve API call. Takes optional reason note. */
  onApprove: (
    agentId: string,
    actionId: string,
    reason?: string,
  ) => Promise<void>;
  /** Callback for reject API call. Takes optional reason note. */
  onReject: (
    agentId: string,
    actionId: string,
    reason?: string,
  ) => Promise<void>;
}

/** Urgency color mapping. */
const URGENCY_COLORS: Record<string, string> = {
  low: "bg-blue-100 text-blue-700 border-blue-200",
  medium: "bg-yellow-100 text-yellow-700 border-yellow-200",
  high: "bg-orange-100 text-orange-700 border-orange-200",
  critical: "bg-red-100 text-red-700 border-red-200",
};

/** Urgency-based card border styling. */
const URGENCY_CARD_BORDERS: Record<string, string> = {
  low: "border-gray-200",
  medium: "border-gray-200",
  high: "border-orange-300",
  critical: "border-red-400 border-2",
};

/** Format an ISO timestamp to a relative or absolute time string. */
function formatSubmittedAt(iso: string): string {
  try {
    const date = new Date(iso);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);

    if (diffMins < 1) return "Just now";
    if (diffMins < 60) return `${diffMins}m ago`;

    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h ago`;

    return date.toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

/** Approval queue card for a single held action. */
export default function ApprovalCard({
  item,
  onResolved,
  onApprove,
  onReject,
}: ApprovalCardProps) {
  const urgencyClass =
    URGENCY_COLORS[item.urgency] ?? "bg-gray-100 text-gray-700 border-gray-200";
  const cardBorderClass =
    URGENCY_CARD_BORDERS[item.urgency] ?? "border-gray-200";
  const isCritical = item.urgency === "critical";

  return (
    <div
      className={`rounded-lg border bg-white p-5 transition-shadow hover:shadow-sm ${cardBorderClass} ${isCritical ? "ring-1 ring-red-200" : ""}`}
    >
      {/* Critical banner */}
      {isCritical && (
        <div className="mb-3 -mt-1 -mx-1 rounded-t bg-red-50 px-3 py-1.5 text-xs font-semibold text-red-800 flex items-center gap-1.5">
          <svg
            className="h-3.5 w-3.5"
            fill="currentColor"
            viewBox="0 0 20 20"
            aria-hidden="true"
          >
            <path
              fillRule="evenodd"
              d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.625-1.516 2.625H3.72c-1.347 0-2.189-1.458-1.515-2.625L8.485 2.495zM10 5a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 0110 5zm0 9a1 1 0 100-2 1 1 0 000 2z"
              clipRule="evenodd"
            />
          </svg>
          Critical -- Requires Immediate Attention
        </div>
      )}

      {/* Header: action + urgency + time */}
      <div className="mb-3 flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <h3 className="text-sm font-semibold text-gray-900">{item.action}</h3>
          <p className="text-xs text-gray-500">
            {formatSubmittedAt(item.submitted_at)}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span
            className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${urgencyClass}`}
            role="status"
            aria-label={`Urgency: ${item.urgency}`}
          >
            {item.urgency}
          </span>
          <StatusBadge value="HELD" size="xs" />
        </div>
      </div>

      {/* Details */}
      <div className="mb-4 space-y-2">
        <div className="flex items-center gap-2 text-xs">
          <span className="text-gray-500">Agent:</span>
          <a
            href={`/agents/${item.agent_id}`}
            className="font-medium text-blue-600 hover:text-blue-800"
          >
            {item.agent_id}
          </a>
          {item.agent_posture && (
            <PostureBadge posture={item.agent_posture} size="sm" />
          )}
        </div>
        <div className="flex items-center gap-2 text-xs">
          <span className="text-gray-500">Team:</span>
          <span className="text-gray-700">{item.team_id}</span>
        </div>
        <div className="text-xs">
          <span className="text-gray-500">Reason: </span>
          <span className="text-gray-700">{item.reason}</span>
        </div>
      </div>

      {/* Decision context: constraint utilization + track record */}
      {(item.constraint_utilization !== undefined ||
        item.pass_rate !== undefined) && (
        <div className="mb-4 rounded-md border border-gray-100 bg-gray-50 p-3 space-y-2">
          <p className="text-xs font-medium text-gray-600">Decision Context</p>

          {item.constraint_utilization !== undefined && (
            <div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-gray-500">Constraint Utilization</span>
                <span
                  className={`font-medium ${
                    item.constraint_utilization >= 90
                      ? "text-red-600"
                      : item.constraint_utilization >= 70
                        ? "text-orange-600"
                        : "text-green-600"
                  }`}
                >
                  {item.constraint_utilization}%
                </span>
              </div>
              <div className="mt-1 h-1.5 w-full rounded-full bg-gray-200 overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all ${
                    item.constraint_utilization >= 90
                      ? "bg-red-500"
                      : item.constraint_utilization >= 70
                        ? "bg-orange-500"
                        : "bg-green-500"
                  }`}
                  style={{
                    width: `${Math.min(item.constraint_utilization, 100)}%`,
                  }}
                />
              </div>
            </div>
          )}

          {item.pass_rate !== undefined && (
            <div className="flex items-center justify-between text-xs">
              <span className="text-gray-500">Recent Track Record</span>
              <span
                className={`font-medium ${
                  item.pass_rate >= 0.9
                    ? "text-green-600"
                    : item.pass_rate >= 0.7
                      ? "text-yellow-600"
                      : "text-red-600"
                }`}
              >
                {Math.round(item.pass_rate * 100)}% pass rate
              </span>
            </div>
          )}
        </div>
      )}

      {/* Action buttons */}
      <div className="border-t border-gray-100 pt-3">
        <ApprovalActions
          agentId={item.agent_id}
          actionId={item.action_id}
          onResolved={onResolved}
          onApprove={onApprove}
          onReject={onReject}
        />
      </div>
    </div>
  );
}
