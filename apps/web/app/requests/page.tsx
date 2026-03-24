// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * Request Queue page -- displays work requests with governance verdicts,
 * status tracking, priority indicators, and assignment details.
 *
 * Supports filtering by status and objective, and drill-down into
 * individual request detail showing sessions and artifacts.
 */

"use client";

import { useState, useCallback, useMemo } from "react";
import DashboardShell from "../../components/layout/DashboardShell";
import ErrorAlert from "../../components/ui/ErrorAlert";
import { TableSkeleton } from "../../components/ui/Skeleton";
import { useAuth } from "../../lib/auth-context";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface WorkRequest {
  id: string;
  title: string;
  objective_id: string;
  objective_title: string;
  status: string;
  priority: "low" | "medium" | "high" | "critical";
  assigned_to: string | null;
  governance_verdict: string | null;
  cost: number;
  created_at: string;
  updated_at: string;
}

interface RequestDetail extends WorkRequest {
  description: string;
  sessions: Array<{
    id: string;
    status: string;
    agent_id: string;
    started_at: string;
    ended_at: string | null;
    cost: number;
  }>;
  artifacts: Array<{
    id: string;
    type: string;
    name: string;
    created_at: string;
  }>;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const STATUS_OPTIONS = [
  { value: "all", label: "All Statuses" },
  { value: "pending", label: "Pending" },
  { value: "queued", label: "Queued" },
  { value: "assigned", label: "Assigned" },
  { value: "in_progress", label: "In Progress" },
  { value: "review", label: "Review" },
  { value: "completed", label: "Completed" },
  { value: "failed", label: "Failed" },
  { value: "cancelled", label: "Cancelled" },
] as const;

const STATUS_COLORS: Record<string, string> = {
  pending: "bg-yellow-100 text-yellow-800 border-yellow-300",
  queued: "bg-blue-100 text-blue-800 border-blue-300",
  assigned: "bg-indigo-100 text-indigo-800 border-indigo-300",
  in_progress: "bg-purple-100 text-purple-800 border-purple-300",
  review: "bg-amber-100 text-amber-800 border-amber-300",
  completed: "bg-green-100 text-green-800 border-green-300",
  failed: "bg-red-100 text-red-800 border-red-300",
  cancelled: "bg-gray-100 text-gray-600 border-gray-300",
};

const VERDICT_COLORS: Record<string, string> = {
  AUTO_APPROVED: "bg-green-100 text-green-800 border-green-300",
  FLAGGED: "bg-yellow-100 text-yellow-800 border-yellow-300",
  HELD: "bg-orange-100 text-orange-800 border-orange-300",
  BLOCKED: "bg-red-100 text-red-800 border-red-300",
};

const PRIORITY_INDICATORS: Record<string, string> = {
  low: "text-gray-400",
  medium: "text-blue-500",
  high: "text-orange-500",
  critical: "text-red-500",
};

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function StatusBadgeLocal({ value }: { value: string }) {
  const colorClass =
    STATUS_COLORS[value] ?? "bg-gray-100 text-gray-700 border-gray-300";
  const label = value
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${colorClass}`}
    >
      {label}
    </span>
  );
}

function VerdictBadge({ verdict }: { verdict: string | null }) {
  if (!verdict) {
    return <span className="text-xs text-gray-400 italic">No verdict</span>;
  }
  const colorClass =
    VERDICT_COLORS[verdict] ?? "bg-gray-100 text-gray-700 border-gray-300";
  const label = verdict
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${colorClass}`}
    >
      {label}
    </span>
  );
}

function PriorityIndicator({ priority }: { priority: string }) {
  const colorClass = PRIORITY_INDICATORS[priority] ?? "text-gray-400";
  const bars =
    priority === "critical"
      ? 4
      : priority === "high"
        ? 3
        : priority === "medium"
          ? 2
          : 1;

  return (
    <div className="flex items-center gap-1" title={priority}>
      {Array.from({ length: 4 }).map((_, i) => (
        <div
          key={i}
          className={`h-3 w-1 rounded-sm ${i < bars ? colorClass.replace("text-", "bg-") : "bg-gray-200"}`}
        />
      ))}
      <span className={`ml-1 text-xs font-medium ${colorClass}`}>
        {priority.charAt(0).toUpperCase() + priority.slice(1)}
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Detail panel
// ---------------------------------------------------------------------------

function RequestDetailPanel({
  request,
  onClose,
}: {
  request: RequestDetail;
  onClose: () => void;
}) {
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-6 space-y-5">
      <div className="flex items-start justify-between">
        <div>
          <h3 className="text-lg font-semibold text-gray-900">
            {request.title}
          </h3>
          <p className="mt-1 text-sm text-gray-500">
            Objective: {request.objective_title}
          </p>
        </div>
        <button
          onClick={onClose}
          className="rounded-md border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
        >
          Close
        </button>
      </div>

      {request.description && (
        <p className="text-sm text-gray-600">{request.description}</p>
      )}

      <div className="flex flex-wrap gap-3">
        <StatusBadgeLocal value={request.status} />
        <VerdictBadge verdict={request.governance_verdict} />
        <PriorityIndicator priority={request.priority} />
        {request.assigned_to && (
          <span className="text-sm text-gray-600">
            Assigned to:{" "}
            <span className="font-medium">{request.assigned_to}</span>
          </span>
        )}
      </div>

      {/* Sessions */}
      <div>
        <h4 className="mb-2 text-sm font-semibold text-gray-700">
          Sessions ({request.sessions.length})
        </h4>
        {request.sessions.length === 0 ? (
          <p className="text-sm text-gray-500">No sessions recorded yet.</p>
        ) : (
          <div className="overflow-hidden rounded-lg border border-gray-200">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-2 text-left text-xs font-medium uppercase text-gray-500">
                    Session
                  </th>
                  <th className="px-4 py-2 text-left text-xs font-medium uppercase text-gray-500">
                    Agent
                  </th>
                  <th className="px-4 py-2 text-left text-xs font-medium uppercase text-gray-500">
                    Status
                  </th>
                  <th className="px-4 py-2 text-left text-xs font-medium uppercase text-gray-500">
                    Started
                  </th>
                  <th className="px-4 py-2 text-right text-xs font-medium uppercase text-gray-500">
                    Cost
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 bg-white">
                {request.sessions.map((session) => (
                  <tr key={session.id} className="hover:bg-gray-50">
                    <td className="px-4 py-2 text-sm font-mono text-gray-700">
                      {session.id.slice(0, 8)}
                    </td>
                    <td className="px-4 py-2 text-sm text-gray-600">
                      {session.agent_id}
                    </td>
                    <td className="px-4 py-2 text-sm">
                      <StatusBadgeLocal value={session.status} />
                    </td>
                    <td className="px-4 py-2 text-sm text-gray-500">
                      {new Date(session.started_at).toLocaleString()}
                    </td>
                    <td className="px-4 py-2 text-right text-sm text-gray-900">
                      ${session.cost.toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Artifacts */}
      <div>
        <h4 className="mb-2 text-sm font-semibold text-gray-700">
          Artifacts ({request.artifacts.length})
        </h4>
        {request.artifacts.length === 0 ? (
          <p className="text-sm text-gray-500">No artifacts produced yet.</p>
        ) : (
          <div className="space-y-2">
            {request.artifacts.map((artifact) => (
              <div
                key={artifact.id}
                className="flex items-center justify-between rounded-md border border-gray-200 bg-gray-50 px-4 py-2"
              >
                <div className="flex items-center gap-3">
                  <span className="inline-flex items-center rounded bg-gray-200 px-2 py-0.5 text-xs font-medium text-gray-600">
                    {artifact.type}
                  </span>
                  <span className="text-sm text-gray-900">{artifact.name}</span>
                </div>
                <span className="text-xs text-gray-400">
                  {new Date(artifact.created_at).toLocaleDateString()}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function RequestsPage() {
  const { user } = useAuth();
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [objectiveFilter, setObjectiveFilter] = useState<string>("");
  const [requests, setRequests] = useState<WorkRequest[]>([]);
  const [detail, setDetail] = useState<RequestDetail | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  // Fetch requests
  const fetchRequests = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (statusFilter !== "all") params.set("status", statusFilter);
      if (objectiveFilter) params.set("objective_id", objectiveFilter);
      const qs = params.toString();
      const response = await fetch(`/api/v1/requests${qs ? `?${qs}` : ""}`);
      if (!response.ok) {
        throw new Error(`Failed to load requests: ${response.status}`);
      }
      const result = await response.json();
      setRequests(result.data?.requests ?? result.requests ?? []);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load requests");
    } finally {
      setLoading(false);
    }
  }, [statusFilter, objectiveFilter]);

  // Initial load and refetch on filter change
  useState(() => {
    fetchRequests();
  });

  // Fetch detail
  const fetchDetail = useCallback(async (id: string) => {
    setDetailLoading(true);
    setSelectedId(id);
    setDetail(null);
    try {
      const response = await fetch(
        `/api/v1/requests/${encodeURIComponent(id)}`,
      );
      if (!response.ok) {
        throw new Error(`Failed to load request detail: ${response.status}`);
      }
      const result = await response.json();
      setDetail(result.data ?? result);
    } catch {
      setDetail(null);
    } finally {
      setDetailLoading(false);
    }
  }, []);

  // Unique objective IDs for filter dropdown
  const objectiveIds = useMemo(() => {
    const ids = new Set<string>();
    for (const req of requests) {
      if (req.objective_id) ids.add(req.objective_id);
    }
    return Array.from(ids);
  }, [requests]);

  // Filtered list
  const filtered = useMemo(() => {
    let list = requests;
    if (statusFilter !== "all") {
      list = list.filter((r) => r.status === statusFilter);
    }
    if (objectiveFilter) {
      list = list.filter((r) => r.objective_id === objectiveFilter);
    }
    return list;
  }, [requests, statusFilter, objectiveFilter]);

  return (
    <DashboardShell
      activePath="/requests"
      title="Request Queue"
      breadcrumbs={[{ label: "Dashboard", href: "/" }, { label: "Requests" }]}
      actions={
        <button
          onClick={fetchRequests}
          disabled={loading}
          className="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 transition-colors"
        >
          Refresh
        </button>
      }
    >
      <div className="space-y-6">
        <p className="text-sm text-gray-600">
          Governance-evaluated work requests in the execution queue. Each
          request carries a governance verdict determining its approval status
          and constraint boundaries.
        </p>

        {/* Filters */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2">
            <label htmlFor="req-status" className="text-sm text-gray-600">
              Status:
            </label>
            <select
              id="req-status"
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value);
                // Re-fetch is triggered by filter change via the initializer
                setTimeout(fetchRequests, 0);
              }}
              className="rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              {STATUS_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          {objectiveIds.length > 0 && (
            <div className="flex items-center gap-2">
              <label htmlFor="req-obj" className="text-sm text-gray-600">
                Objective:
              </label>
              <select
                id="req-obj"
                value={objectiveFilter}
                onChange={(e) => {
                  setObjectiveFilter(e.target.value);
                  setTimeout(fetchRequests, 0);
                }}
                className="rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              >
                <option value="">All Objectives</option>
                {objectiveIds.map((id) => (
                  <option key={id} value={id}>
                    {id.slice(0, 8)}...
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>

        {/* Loading */}
        {loading && <TableSkeleton rows={6} />}

        {/* Error */}
        {error && <ErrorAlert message={error} onRetry={fetchRequests} />}

        {/* Detail panel */}
        {selectedId && detail && !detailLoading && (
          <RequestDetailPanel
            request={detail}
            onClose={() => {
              setSelectedId(null);
              setDetail(null);
            }}
          />
        )}

        {detailLoading && (
          <div className="rounded-lg border border-gray-200 bg-white p-6">
            <div className="animate-pulse space-y-3">
              <div className="h-5 w-1/3 rounded bg-gray-200" />
              <div className="h-4 w-2/3 rounded bg-gray-200" />
              <div className="h-4 w-1/2 rounded bg-gray-200" />
            </div>
          </div>
        )}

        {/* Table */}
        {!loading && !error && (
          <>
            {filtered.length > 0 ? (
              <div className="overflow-hidden rounded-lg border border-gray-200 bg-white">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                        Title
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                        Status
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                        Priority
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                        Verdict
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                        Assigned To
                      </th>
                      <th className="px-4 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">
                        Cost
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200">
                    {filtered.map((req) => (
                      <tr
                        key={req.id}
                        onClick={() => fetchDetail(req.id)}
                        className="cursor-pointer hover:bg-gray-50 transition-colors"
                      >
                        <td className="px-4 py-3">
                          <div className="text-sm font-medium text-gray-900">
                            {req.title}
                          </div>
                          <div className="text-xs text-gray-400">
                            {req.objective_title}
                          </div>
                        </td>
                        <td className="px-4 py-3 text-sm">
                          <StatusBadgeLocal value={req.status} />
                        </td>
                        <td className="px-4 py-3 text-sm">
                          <PriorityIndicator priority={req.priority} />
                        </td>
                        <td className="px-4 py-3 text-sm">
                          <VerdictBadge verdict={req.governance_verdict} />
                        </td>
                        <td className="px-4 py-3 text-sm text-gray-600">
                          {req.assigned_to ?? (
                            <span className="italic text-gray-400">
                              Unassigned
                            </span>
                          )}
                        </td>
                        <td className="px-4 py-3 text-right text-sm text-gray-900">
                          ${req.cost.toLocaleString()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="rounded-lg border border-gray-200 bg-white p-8 text-center">
                <p className="text-sm text-gray-500">
                  {requests.length === 0
                    ? "No requests in the queue."
                    : "No requests match the selected filters."}
                </p>
              </div>
            )}
          </>
        )}
      </div>
    </DashboardShell>
  );
}
