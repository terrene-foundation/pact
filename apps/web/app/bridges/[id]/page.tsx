// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * Bridge detail page -- shows full bridge information including permissions,
 * constraint intersection, approval status, and audit log.
 *
 * Provides action buttons for approve, suspend, and close operations.
 * All destructive actions use proper confirmation modals (no window.prompt).
 */

"use client";

import { useParams } from "next/navigation";
import { useState, useCallback } from "react";
import DashboardShell from "../../../components/layout/DashboardShell";
import ErrorAlert from "../../../components/ui/ErrorAlert";
import StatusBadge from "../../../components/ui/StatusBadge";
import ConfirmationModal from "../../../components/ui/ConfirmationModal";
import { CardSkeleton } from "../../../components/ui/Skeleton";
import { useApi, getApiClient } from "../../../lib/use-api";
import { useAuth } from "../../../lib/auth-context";

/** Human-readable labels for bridge types. */
const BRIDGE_TYPE_LABELS: Record<string, string> = {
  standing: "Standing",
  scoped: "Scoped",
  ad_hoc: "Ad-Hoc",
};

export default function BridgeDetailPage() {
  const { user } = useAuth();
  const approverId = user?.name ?? "unknown-operator";

  const params = useParams();
  const bridgeId = params.id as string;

  const [actionError, setActionError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [suspendOpen, setSuspendOpen] = useState(false);
  const [closeOpen, setCloseOpen] = useState(false);

  const {
    data: bridgeData,
    loading: bridgeLoading,
    error: bridgeError,
    refetch: bridgeRefetch,
  } = useApi((client) => client.getBridge(bridgeId), [bridgeId]);

  const {
    data: auditData,
    loading: auditLoading,
    error: auditError,
    refetch: auditRefetch,
  } = useApi((client) => client.bridgeAudit(bridgeId), [bridgeId]);

  const handleRefetch = useCallback(() => {
    bridgeRefetch();
    auditRefetch();
    setActionError(null);
  }, [bridgeRefetch, auditRefetch]);

  const handleApprove = useCallback(
    async (side: "source" | "target") => {
      setActionLoading(true);
      setActionError(null);
      try {
        const client = getApiClient();
        const result = await client.approveBridge(bridgeId, side, approverId);
        if (result.status === "error") {
          setActionError(result.error ?? "Approval failed");
        } else {
          handleRefetch();
        }
      } catch (err) {
        setActionError(err instanceof Error ? err.message : "Approval failed");
      } finally {
        setActionLoading(false);
      }
    },
    [bridgeId, approverId, handleRefetch],
  );

  const handleSuspend = useCallback(
    async (reason: string) => {
      setActionError(null);
      const client = getApiClient();
      const result = await client.suspendBridge(bridgeId, reason);
      if (result.status === "error") {
        throw new Error(result.error ?? "Suspension failed");
      }
      setSuspendOpen(false);
      handleRefetch();
    },
    [bridgeId, handleRefetch],
  );

  const handleClose = useCallback(
    async (reason: string) => {
      setActionError(null);
      const client = getApiClient();
      const result = await client.closeBridge(bridgeId, reason);
      if (result.status === "error") {
        throw new Error(result.error ?? "Closure failed");
      }
      setCloseOpen(false);
      handleRefetch();
    },
    [bridgeId, handleRefetch],
  );

  const loading = bridgeLoading || auditLoading;
  const error = bridgeError ?? auditError;

  return (
    <DashboardShell
      activePath="/bridges"
      title="Bridge Detail"
      breadcrumbs={[
        { label: "Dashboard", href: "/" },
        { label: "Bridges", href: "/bridges" },
        { label: bridgeData?.bridge_id ?? bridgeId },
      ]}
      actions={
        <button
          onClick={handleRefetch}
          disabled={loading}
          className="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 transition-colors"
        >
          Refresh
        </button>
      }
    >
      <div className="space-y-6">
        {error && <ErrorAlert message={error} onRetry={handleRefetch} />}
        {actionError && (
          <ErrorAlert
            message={actionError}
            onRetry={() => setActionError(null)}
          />
        )}

        {loading && (
          <div className="grid gap-4 sm:grid-cols-2">
            {Array.from({ length: 4 }).map((_, i) => (
              <CardSkeleton key={i} />
            ))}
          </div>
        )}

        {bridgeData && (
          <>
            {/* Header card */}
            <div className="rounded-lg border border-gray-200 bg-white p-6">
              <div className="flex items-start justify-between">
                <div>
                  <h2 className="text-lg font-semibold text-gray-900">
                    {bridgeData.purpose}
                  </h2>
                  <p className="mt-1 text-sm text-gray-500 font-mono">
                    {bridgeData.bridge_id}
                  </p>
                </div>
                <StatusBadge value={bridgeData.status} size="md" />
              </div>

              <div className="mt-4 grid gap-4 sm:grid-cols-3">
                <div>
                  <p className="text-xs text-gray-500 uppercase tracking-wider">
                    Type
                  </p>
                  <p className="mt-1 text-sm font-medium text-gray-900">
                    {BRIDGE_TYPE_LABELS[bridgeData.bridge_type] ??
                      bridgeData.bridge_type}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-gray-500 uppercase tracking-wider">
                    Source Team
                  </p>
                  <p className="mt-1 text-sm font-medium text-gray-900">
                    {bridgeData.source_team_id}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-gray-500 uppercase tracking-wider">
                    Target Team
                  </p>
                  <p className="mt-1 text-sm font-medium text-gray-900">
                    {bridgeData.target_team_id}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-gray-500 uppercase tracking-wider">
                    Created By
                  </p>
                  <p className="mt-1 text-sm text-gray-700">
                    {bridgeData.created_by || "Unknown"}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-gray-500 uppercase tracking-wider">
                    Created At
                  </p>
                  <p className="mt-1 text-sm text-gray-700">
                    {new Date(bridgeData.created_at).toLocaleString()}
                  </p>
                </div>
                {bridgeData.valid_until && (
                  <div>
                    <p className="text-xs text-gray-500 uppercase tracking-wider">
                      Valid Until
                    </p>
                    <p className="mt-1 text-sm text-gray-700">
                      {new Date(bridgeData.valid_until).toLocaleString()}
                    </p>
                  </div>
                )}
              </div>

              {/* Replacement chain */}
              {(bridgeData.replaced_by || bridgeData.replacement_for) && (
                <div className="mt-4 rounded-md bg-blue-50 border border-blue-200 p-3">
                  <p className="text-xs font-medium text-blue-800">
                    Replacement Chain
                  </p>
                  {bridgeData.replacement_for && (
                    <p className="text-xs text-blue-700 mt-1">
                      Replaces:{" "}
                      <a
                        href={`/bridges/${bridgeData.replacement_for}`}
                        className="underline"
                      >
                        {bridgeData.replacement_for}
                      </a>
                    </p>
                  )}
                  {bridgeData.replaced_by && (
                    <p className="text-xs text-blue-700 mt-1">
                      Replaced by:{" "}
                      <a
                        href={`/bridges/${bridgeData.replaced_by}`}
                        className="underline"
                      >
                        {bridgeData.replaced_by}
                      </a>
                    </p>
                  )}
                </div>
              )}
            </div>

            {/* Approval status */}
            <div className="rounded-lg border border-gray-200 bg-white p-6">
              <h3 className="text-sm font-semibold text-gray-900 mb-4">
                Bilateral Approval Status
              </h3>
              <div className="grid gap-4 sm:grid-cols-2">
                <div
                  className={`rounded-lg border p-4 ${
                    bridgeData.approved_by_source
                      ? "border-green-200 bg-green-50"
                      : "border-yellow-200 bg-yellow-50"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-medium text-gray-900">
                      Source Approval
                    </p>
                    <StatusBadge
                      value={
                        bridgeData.approved_by_source ? "active" : "pending"
                      }
                      label={
                        bridgeData.approved_by_source ? "Approved" : "Pending"
                      }
                      size="xs"
                    />
                  </div>
                  <p className="mt-1 text-xs text-gray-500">
                    Team: {bridgeData.source_team_id}
                  </p>
                  {!bridgeData.approved_by_source &&
                    bridgeData.status === "pending" && (
                      <button
                        onClick={() => handleApprove("source")}
                        disabled={actionLoading}
                        className="mt-2 rounded-md bg-green-600 px-3 py-1 text-xs font-medium text-white hover:bg-green-700 disabled:opacity-50 transition-colors"
                      >
                        Approve Source
                      </button>
                    )}
                </div>
                <div
                  className={`rounded-lg border p-4 ${
                    bridgeData.approved_by_target
                      ? "border-green-200 bg-green-50"
                      : "border-yellow-200 bg-yellow-50"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-medium text-gray-900">
                      Target Approval
                    </p>
                    <StatusBadge
                      value={
                        bridgeData.approved_by_target ? "active" : "pending"
                      }
                      label={
                        bridgeData.approved_by_target ? "Approved" : "Pending"
                      }
                      size="xs"
                    />
                  </div>
                  <p className="mt-1 text-xs text-gray-500">
                    Team: {bridgeData.target_team_id}
                  </p>
                  {!bridgeData.approved_by_target &&
                    bridgeData.status === "pending" && (
                      <button
                        onClick={() => handleApprove("target")}
                        disabled={actionLoading}
                        className="mt-2 rounded-md bg-green-600 px-3 py-1 text-xs font-medium text-white hover:bg-green-700 disabled:opacity-50 transition-colors"
                      >
                        Approve Target
                      </button>
                    )}
                </div>
              </div>
            </div>

            {/* Permissions / Constraint Intersection */}
            <div className="rounded-lg border border-gray-200 bg-white p-6">
              <h3 className="text-sm font-semibold text-gray-900 mb-4">
                Permissions (Constraint Intersection)
              </h3>
              <div className="grid gap-4 sm:grid-cols-3">
                <div>
                  <p className="text-xs text-gray-500 uppercase tracking-wider mb-2">
                    Read Paths
                  </p>
                  {bridgeData.permissions.read_paths.length > 0 ? (
                    <ul className="space-y-1">
                      {bridgeData.permissions.read_paths.map((path) => (
                        <li
                          key={path}
                          className="text-xs font-mono text-gray-700 bg-gray-50 rounded px-2 py-1"
                        >
                          {path}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-xs text-gray-400 italic">None</p>
                  )}
                </div>
                <div>
                  <p className="text-xs text-gray-500 uppercase tracking-wider mb-2">
                    Write Paths
                  </p>
                  {bridgeData.permissions.write_paths.length > 0 ? (
                    <ul className="space-y-1">
                      {bridgeData.permissions.write_paths.map((path) => (
                        <li
                          key={path}
                          className="text-xs font-mono text-gray-700 bg-gray-50 rounded px-2 py-1"
                        >
                          {path}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-xs text-gray-400 italic">None</p>
                  )}
                </div>
                <div>
                  <p className="text-xs text-gray-500 uppercase tracking-wider mb-2">
                    Message Types
                  </p>
                  {bridgeData.permissions.message_types.length > 0 ? (
                    <ul className="space-y-1">
                      {bridgeData.permissions.message_types.map((mt) => (
                        <li
                          key={mt}
                          className="text-xs font-mono text-gray-700 bg-gray-50 rounded px-2 py-1"
                        >
                          {mt}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-xs text-gray-400 italic">None</p>
                  )}
                </div>
              </div>
              {bridgeData.permissions.requires_attribution && (
                <p className="mt-3 text-xs text-amber-700 bg-amber-50 rounded px-2 py-1 inline-block">
                  Requires attribution
                </p>
              )}
              {bridgeData.one_time_use && (
                <p className="mt-2 text-xs text-blue-700 bg-blue-50 rounded px-2 py-1 inline-block">
                  One-time use {bridgeData.used ? "(consumed)" : "(available)"}
                </p>
              )}
            </div>

            {/* Actions */}
            {(bridgeData.status === "active" ||
              bridgeData.status === "pending") && (
              <div className="rounded-lg border border-gray-200 bg-white p-6">
                <h3 className="text-sm font-semibold text-gray-900 mb-4">
                  Actions
                </h3>
                <div className="flex gap-3">
                  {bridgeData.status === "active" && (
                    <>
                      <button
                        onClick={() => setSuspendOpen(true)}
                        disabled={actionLoading}
                        className="rounded-md bg-orange-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-orange-700 disabled:opacity-50 transition-colors"
                      >
                        Suspend Bridge
                      </button>
                      <button
                        onClick={() => setCloseOpen(true)}
                        disabled={actionLoading}
                        className="rounded-md bg-gray-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-gray-700 disabled:opacity-50 transition-colors"
                      >
                        Close Bridge
                      </button>
                    </>
                  )}
                  {bridgeData.status === "pending" && (
                    <button
                      onClick={() => setCloseOpen(true)}
                      disabled={actionLoading}
                      className="rounded-md bg-gray-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-gray-700 disabled:opacity-50 transition-colors"
                    >
                      Close Bridge
                    </button>
                  )}
                </div>
              </div>
            )}

            {/* Audit log */}
            <div className="rounded-lg border border-gray-200 bg-white p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-semibold text-gray-900">
                  Audit Log ({auditData?.total ?? 0} entries)
                </h3>
              </div>

              {auditData && auditData.entries.length > 0 ? (
                <div className="overflow-x-auto">
                  <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="px-3 py-2 text-left text-xs font-medium uppercase text-gray-500">
                          Timestamp
                        </th>
                        <th className="px-3 py-2 text-left text-xs font-medium uppercase text-gray-500">
                          Agent
                        </th>
                        <th className="px-3 py-2 text-left text-xs font-medium uppercase text-gray-500">
                          Path
                        </th>
                        <th className="px-3 py-2 text-left text-xs font-medium uppercase text-gray-500">
                          Access Type
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200">
                      {auditData.entries.map((entry, idx) => (
                        <tr key={idx}>
                          <td className="px-3 py-2 text-xs text-gray-700">
                            {new Date(entry.timestamp).toLocaleString()}
                          </td>
                          <td className="px-3 py-2 text-xs font-mono text-gray-700">
                            {entry.agent_id}
                          </td>
                          <td className="px-3 py-2 text-xs font-mono text-gray-700">
                            {entry.path}
                          </td>
                          <td className="px-3 py-2 text-xs text-gray-700">
                            {entry.access_type}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="text-xs text-gray-400 italic">
                  No access log entries recorded yet.
                </p>
              )}
            </div>
          </>
        )}
      </div>

      {/* Suspend Bridge Modal */}
      <ConfirmationModal
        open={suspendOpen}
        onClose={() => setSuspendOpen(false)}
        onConfirm={handleSuspend}
        title="Suspend Bridge"
        description="Suspending this bridge will immediately halt all cross-team data access through it. The bridge can be reactivated later. Please provide a reason for the suspension."
        confirmLabel="Suspend Bridge"
        destructive
        inputRequired
        inputLabel="Suspension Reason"
        inputPlaceholder="Why is this bridge being suspended?"
      />

      {/* Close Bridge Modal */}
      <ConfirmationModal
        open={closeOpen}
        onClose={() => setCloseOpen(false)}
        onConfirm={handleClose}
        title="Close Bridge"
        description="Closing this bridge will permanently end the cross-team connection. A new bridge will need to be created if teams need to collaborate again. Please provide a reason for the closure."
        confirmLabel="Close Bridge"
        inputRequired
        inputLabel="Closure Reason"
        inputPlaceholder="Why is this bridge being closed?"
      />
    </DashboardShell>
  );
}
