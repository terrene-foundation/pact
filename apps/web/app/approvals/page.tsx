// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * Approvals page -- interactive queue of HELD items awaiting human approval.
 *
 * Displays all held actions as cards with approve/reject buttons.
 * Actions are sorted by urgency (critical first) then by submission time.
 * Resolved actions are visually updated in place.
 */

"use client";

import { useState, useCallback, useMemo } from "react";
import DashboardShell from "../../components/layout/DashboardShell";
import ApprovalCard from "../../components/approvals/ApprovalCard";
import ErrorAlert from "../../components/ui/ErrorAlert";
import { CardSkeleton } from "../../components/ui/Skeleton";
import { useApi, getApiClient } from "../../lib/use-api";
import { useAuth } from "../../lib/auth-context";

/** Urgency sort order -- lower number = higher priority (shown first). */
const URGENCY_ORDER: Record<string, number> = {
  critical: 0,
  high: 1,
  medium: 2,
  low: 3,
};

export default function ApprovalsPage() {
  const { user } = useAuth();
  const approverId = user?.name ?? "unknown-operator";

  const { data, loading, error, refetch } = useApi(
    (client) => client.heldActions(),
    [],
  );

  const [resolvedIds, setResolvedIds] = useState<Set<string>>(new Set());

  const handleResolved = useCallback(
    (actionId: string, _decision: "approved" | "rejected") => {
      setResolvedIds((prev) => new Set(prev).add(actionId));
    },
    [],
  );

  const handleApprove = useCallback(
    async (agentId: string, actionId: string, reason?: string) => {
      const client = getApiClient();
      await client.approveAction(agentId, actionId, approverId, reason);
    },
    [approverId],
  );

  const handleReject = useCallback(
    async (agentId: string, actionId: string, reason?: string) => {
      const client = getApiClient();
      await client.rejectAction(agentId, actionId, approverId, reason);
    },
    [approverId],
  );

  /** Sort pending actions by urgency (critical first), then by time (oldest first). */
  const pendingActions = useMemo(() => {
    const actions =
      data?.actions.filter((a) => !resolvedIds.has(a.action_id)) ?? [];
    return actions.sort((a, b) => {
      const urgencyA = URGENCY_ORDER[a.urgency] ?? 99;
      const urgencyB = URGENCY_ORDER[b.urgency] ?? 99;
      if (urgencyA !== urgencyB) return urgencyA - urgencyB;
      // Within the same urgency level, oldest first
      return (
        new Date(a.submitted_at).getTime() - new Date(b.submitted_at).getTime()
      );
    });
  }, [data, resolvedIds]);

  const resolvedCount = resolvedIds.size;
  const criticalCount = pendingActions.filter(
    (a) => a.urgency === "critical",
  ).length;

  return (
    <DashboardShell
      activePath="/approvals"
      title="Approval Queue"
      breadcrumbs={[{ label: "Dashboard", href: "/" }, { label: "Approvals" }]}
      actions={
        <button
          onClick={refetch}
          disabled={loading}
          className="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 transition-colors"
        >
          Refresh
        </button>
      }
    >
      <div className="space-y-6">
        <p className="text-sm text-gray-600">
          Actions that exceeded a soft constraint limit and require human
          approval. Review each request and approve or reject based on the
          action context and constraint boundaries.
        </p>

        {/* Summary bar */}
        {data && !loading && (
          <div className="flex flex-wrap items-center gap-4 rounded-lg border border-gray-200 bg-white px-4 py-3">
            <div className="flex items-center gap-2">
              <span className="flex h-6 w-6 items-center justify-center rounded-full bg-orange-100 text-xs font-bold text-orange-700">
                {pendingActions.length}
              </span>
              <span className="text-sm text-gray-700">Pending</span>
            </div>
            {criticalCount > 0 && (
              <div className="flex items-center gap-2">
                <span className="flex h-6 w-6 items-center justify-center rounded-full bg-red-100 text-xs font-bold text-red-700">
                  {criticalCount}
                </span>
                <span className="text-sm text-red-700 font-medium">
                  Critical
                </span>
              </div>
            )}
            {resolvedCount > 0 && (
              <div className="flex items-center gap-2">
                <span className="flex h-6 w-6 items-center justify-center rounded-full bg-green-100 text-xs font-bold text-green-700">
                  {resolvedCount}
                </span>
                <span className="text-sm text-gray-700">
                  Resolved this session
                </span>
              </div>
            )}
          </div>
        )}

        {/* Loading */}
        {loading && (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <CardSkeleton key={i} />
            ))}
          </div>
        )}

        {/* Error */}
        {error && <ErrorAlert message={error} onRetry={refetch} />}

        {/* Approval cards */}
        {data && (
          <>
            {pendingActions.length > 0 ? (
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {pendingActions.map((action) => (
                  <ApprovalCard
                    key={action.action_id}
                    item={action}
                    onResolved={handleResolved}
                    onApprove={handleApprove}
                    onReject={handleReject}
                  />
                ))}
              </div>
            ) : (
              <div className="rounded-lg border border-green-200 bg-green-50 p-8 text-center">
                <svg
                  className="mx-auto mb-3 h-10 w-10 text-green-500"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                  aria-hidden="true"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
                  />
                </svg>
                <p className="text-sm font-medium text-green-800">
                  All caught up
                </p>
                <p className="text-xs text-green-600">
                  No actions are awaiting approval right now.
                </p>
              </div>
            )}
          </>
        )}
      </div>
    </DashboardShell>
  );
}
