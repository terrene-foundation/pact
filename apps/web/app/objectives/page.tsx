// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * Objectives page -- manage work objectives with status tracking,
 * budget monitoring, and decomposed request summaries.
 *
 * Supports creation of new objectives and drill-down into individual
 * objective detail showing child requests and cost breakdown.
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

interface Objective {
  id: string;
  title: string;
  description: string;
  org_address: string;
  status: "draft" | "active" | "completed" | "cancelled";
  priority: "low" | "medium" | "high" | "critical";
  budget: number;
  spent: number;
  request_count: number;
  created_at: string;
  updated_at: string;
}

interface ObjectiveDetail extends Objective {
  requests: Array<{
    id: string;
    title: string;
    status: string;
    assigned_to: string | null;
    cost: number;
  }>;
}

interface CreateObjectiveForm {
  title: string;
  org_address: string;
  budget: string;
  priority: "low" | "medium" | "high" | "critical";
  description: string;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const STATUS_OPTIONS = [
  { value: "all", label: "All Statuses" },
  { value: "draft", label: "Draft" },
  { value: "active", label: "Active" },
  { value: "completed", label: "Completed" },
  { value: "cancelled", label: "Cancelled" },
] as const;

const STATUS_COLORS: Record<string, string> = {
  draft: "bg-gray-100 text-gray-700 border-gray-300",
  active: "bg-blue-100 text-blue-800 border-blue-300",
  completed: "bg-green-100 text-green-800 border-green-300",
  cancelled: "bg-red-100 text-red-800 border-red-300",
};

const PRIORITY_COLORS: Record<string, string> = {
  low: "text-gray-500",
  medium: "text-blue-600",
  high: "text-orange-600",
  critical: "text-red-600",
};

const EMPTY_FORM: CreateObjectiveForm = {
  title: "",
  org_address: "",
  budget: "",
  priority: "medium",
  description: "",
};

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function StatusBadgeLocal({ status }: { status: string }) {
  const colorClass =
    STATUS_COLORS[status] ?? "bg-gray-100 text-gray-700 border-gray-300";
  const label = status.charAt(0).toUpperCase() + status.slice(1);
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${colorClass}`}
    >
      {label}
    </span>
  );
}

function BudgetBar({ spent, budget }: { spent: number; budget: number }) {
  const pct = budget > 0 ? Math.min((spent / budget) * 100, 100) : 0;
  const overBudget = spent > budget;
  const barColor = overBudget
    ? "bg-red-500"
    : pct > 80
      ? "bg-orange-500"
      : "bg-blue-500";

  return (
    <div className="flex items-center gap-2">
      <div className="h-2 w-24 rounded-full bg-gray-200">
        <div
          className={`h-2 rounded-full ${barColor} transition-all`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-xs text-gray-500">
        ${spent.toLocaleString()} / ${budget.toLocaleString()}
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Detail panel
// ---------------------------------------------------------------------------

function ObjectiveDetailPanel({
  objective,
  onClose,
}: {
  objective: ObjectiveDetail;
  onClose: () => void;
}) {
  const totalRequestCost = objective.requests.reduce(
    (sum, r) => sum + r.cost,
    0,
  );

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-6 space-y-5">
      <div className="flex items-start justify-between">
        <div>
          <h3 className="text-lg font-semibold text-gray-900">
            {objective.title}
          </h3>
          <p className="mt-1 text-sm text-gray-500">{objective.org_address}</p>
        </div>
        <button
          onClick={onClose}
          className="rounded-md border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
        >
          Close
        </button>
      </div>

      {objective.description && (
        <p className="text-sm text-gray-600">{objective.description}</p>
      )}

      {/* Cost summary */}
      <div className="grid grid-cols-3 gap-4">
        <div className="rounded-lg border border-gray-200 bg-gray-50 p-3">
          <p className="text-xs text-gray-500">Budget</p>
          <p className="text-lg font-semibold text-gray-900">
            ${objective.budget.toLocaleString()}
          </p>
        </div>
        <div className="rounded-lg border border-gray-200 bg-gray-50 p-3">
          <p className="text-xs text-gray-500">Spent</p>
          <p className="text-lg font-semibold text-gray-900">
            ${objective.spent.toLocaleString()}
          </p>
        </div>
        <div className="rounded-lg border border-gray-200 bg-gray-50 p-3">
          <p className="text-xs text-gray-500">Request Cost Total</p>
          <p className="text-lg font-semibold text-gray-900">
            ${totalRequestCost.toLocaleString()}
          </p>
        </div>
      </div>

      {/* Decomposed requests */}
      <div>
        <h4 className="mb-2 text-sm font-semibold text-gray-700">
          Decomposed Requests ({objective.requests.length})
        </h4>
        {objective.requests.length === 0 ? (
          <p className="text-sm text-gray-500">
            No requests have been created for this objective yet.
          </p>
        ) : (
          <div className="overflow-hidden rounded-lg border border-gray-200">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-2 text-left text-xs font-medium uppercase text-gray-500">
                    Title
                  </th>
                  <th className="px-4 py-2 text-left text-xs font-medium uppercase text-gray-500">
                    Status
                  </th>
                  <th className="px-4 py-2 text-left text-xs font-medium uppercase text-gray-500">
                    Assigned
                  </th>
                  <th className="px-4 py-2 text-right text-xs font-medium uppercase text-gray-500">
                    Cost
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 bg-white">
                {objective.requests.map((req) => (
                  <tr key={req.id} className="hover:bg-gray-50">
                    <td className="px-4 py-2 text-sm text-gray-900">
                      {req.title}
                    </td>
                    <td className="px-4 py-2 text-sm">
                      <StatusBadgeLocal status={req.status} />
                    </td>
                    <td className="px-4 py-2 text-sm text-gray-600">
                      {req.assigned_to ?? "--"}
                    </td>
                    <td className="px-4 py-2 text-right text-sm text-gray-900">
                      ${req.cost.toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Create form
// ---------------------------------------------------------------------------

function CreateObjectivePanel({
  onCreated,
  onCancel,
}: {
  onCreated: () => void;
  onCancel: () => void;
}) {
  const [form, setForm] = useState<CreateObjectiveForm>({ ...EMPTY_FORM });
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      setSubmitting(true);
      setSubmitError(null);

      try {
        const response = await fetch("/api/v1/objectives", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            title: form.title,
            org_address: form.org_address,
            budget: parseFloat(form.budget) || 0,
            priority: form.priority,
            description: form.description,
          }),
        });

        if (!response.ok) {
          const body = await response.text();
          throw new Error(
            `Failed to create objective: ${response.status} ${body}`,
          );
        }

        onCreated();
      } catch (err: unknown) {
        setSubmitError(
          err instanceof Error ? err.message : "Failed to create objective",
        );
      } finally {
        setSubmitting(false);
      }
    },
    [form, onCreated],
  );

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-6">
      <h3 className="mb-4 text-lg font-semibold text-gray-900">
        Create Objective
      </h3>
      {submitError && (
        <div className="mb-4">
          <ErrorAlert message={submitError} />
        </div>
      )}
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label
            htmlFor="obj-title"
            className="block text-sm font-medium text-gray-700"
          >
            Title
          </label>
          <input
            id="obj-title"
            type="text"
            required
            value={form.title}
            onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
            className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            placeholder="e.g. Q2 Platform Migration"
          />
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <label
              htmlFor="obj-address"
              className="block text-sm font-medium text-gray-700"
            >
              Org Address (D/T/R)
            </label>
            <input
              id="obj-address"
              type="text"
              required
              value={form.org_address}
              onChange={(e) =>
                setForm((f) => ({ ...f, org_address: e.target.value }))
              }
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              placeholder="e.g. D1-R1-T1-R1"
            />
          </div>
          <div>
            <label
              htmlFor="obj-budget"
              className="block text-sm font-medium text-gray-700"
            >
              Budget ($)
            </label>
            <input
              id="obj-budget"
              type="number"
              min="0"
              step="0.01"
              required
              value={form.budget}
              onChange={(e) =>
                setForm((f) => ({ ...f, budget: e.target.value }))
              }
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              placeholder="10000"
            />
          </div>
        </div>

        <div>
          <label
            htmlFor="obj-priority"
            className="block text-sm font-medium text-gray-700"
          >
            Priority
          </label>
          <select
            id="obj-priority"
            value={form.priority}
            onChange={(e) =>
              setForm((f) => ({
                ...f,
                priority: e.target.value as CreateObjectiveForm["priority"],
              }))
            }
            className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            <option value="low">Low</option>
            <option value="medium">Medium</option>
            <option value="high">High</option>
            <option value="critical">Critical</option>
          </select>
        </div>

        <div>
          <label
            htmlFor="obj-desc"
            className="block text-sm font-medium text-gray-700"
          >
            Description
          </label>
          <textarea
            id="obj-desc"
            rows={3}
            value={form.description}
            onChange={(e) =>
              setForm((f) => ({ ...f, description: e.target.value }))
            }
            className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            placeholder="Describe the objective and expected outcomes..."
          />
        </div>

        <div className="flex justify-end gap-3">
          <button
            type="button"
            onClick={onCancel}
            className="rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={submitting}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            {submitting ? "Creating..." : "Create Objective"}
          </button>
        </div>
      </form>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function ObjectivesPage() {
  const { user } = useAuth();
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [showCreate, setShowCreate] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [objectives, setObjectives] = useState<Objective[]>([]);
  const [detail, setDetail] = useState<ObjectiveDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  // Fetch objectives list
  const fetchObjectives = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch("/api/v1/objectives");
      if (!response.ok) {
        throw new Error(`Failed to load objectives: ${response.status}`);
      }
      const result = await response.json();
      setObjectives(result.data?.objectives ?? result.objectives ?? []);
    } catch (err: unknown) {
      setError(
        err instanceof Error ? err.message : "Failed to load objectives",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  // Initial load
  useState(() => {
    fetchObjectives();
  });

  // Fetch detail for a selected objective
  const fetchDetail = useCallback(async (id: string) => {
    setDetailLoading(true);
    setSelectedId(id);
    setDetail(null);
    try {
      const response = await fetch(
        `/api/v1/objectives/${encodeURIComponent(id)}`,
      );
      if (!response.ok) {
        throw new Error(`Failed to load objective detail: ${response.status}`);
      }
      const result = await response.json();
      setDetail(result.data ?? result);
    } catch {
      setDetail(null);
    } finally {
      setDetailLoading(false);
    }
  }, []);

  // Filtered list
  const filtered = useMemo(() => {
    if (statusFilter === "all") return objectives;
    return objectives.filter((o) => o.status === statusFilter);
  }, [objectives, statusFilter]);

  // Status summary counts
  const statusCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const obj of objectives) {
      counts[obj.status] = (counts[obj.status] ?? 0) + 1;
    }
    return counts;
  }, [objectives]);

  const handleCreated = useCallback(() => {
    setShowCreate(false);
    fetchObjectives();
  }, [fetchObjectives]);

  return (
    <DashboardShell
      activePath="/objectives"
      title="Objectives"
      breadcrumbs={[{ label: "Dashboard", href: "/" }, { label: "Objectives" }]}
      actions={
        <div className="flex gap-2">
          <button
            onClick={() => setShowCreate(true)}
            className="rounded-md bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
          >
            New Objective
          </button>
          <button
            onClick={fetchObjectives}
            disabled={loading}
            className="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 transition-colors"
          >
            Refresh
          </button>
        </div>
      }
    >
      <div className="space-y-6">
        <p className="text-sm text-gray-600">
          Work objectives define the scope, budget, and priority of governed
          work items. Each objective decomposes into requests assigned to pools
          and agents.
        </p>

        {/* Summary bar */}
        {!loading && objectives.length > 0 && (
          <div className="flex flex-wrap items-center gap-4 rounded-lg border border-gray-200 bg-white px-4 py-3">
            <span className="text-sm font-medium text-gray-700">
              {objectives.length} objective{objectives.length !== 1 ? "s" : ""}
            </span>
            {statusCounts.active !== undefined && statusCounts.active > 0 && (
              <div className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-blue-500" />
                <span className="text-sm text-gray-600">
                  {statusCounts.active} active
                </span>
              </div>
            )}
            {statusCounts.draft !== undefined && statusCounts.draft > 0 && (
              <div className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-gray-400" />
                <span className="text-sm text-gray-600">
                  {statusCounts.draft} draft
                </span>
              </div>
            )}
            {statusCounts.completed !== undefined &&
              statusCounts.completed > 0 && (
                <div className="flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-full bg-green-500" />
                  <span className="text-sm text-gray-600">
                    {statusCounts.completed} completed
                  </span>
                </div>
              )}
          </div>
        )}

        {/* Filter */}
        <div className="flex items-center gap-3">
          <label htmlFor="status-filter" className="text-sm text-gray-600">
            Filter:
          </label>
          <select
            id="status-filter"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            {STATUS_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        {/* Create form */}
        {showCreate && (
          <CreateObjectivePanel
            onCreated={handleCreated}
            onCancel={() => setShowCreate(false)}
          />
        )}

        {/* Loading */}
        {loading && <TableSkeleton rows={5} />}

        {/* Error */}
        {error && <ErrorAlert message={error} onRetry={fetchObjectives} />}

        {/* Detail panel */}
        {selectedId && detail && !detailLoading && (
          <ObjectiveDetailPanel
            objective={detail}
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
                        Budget
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                        Requests
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                        Address
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200">
                    {filtered.map((obj) => (
                      <tr
                        key={obj.id}
                        onClick={() => fetchDetail(obj.id)}
                        className="cursor-pointer hover:bg-gray-50 transition-colors"
                      >
                        <td className="px-4 py-3 text-sm font-medium text-gray-900">
                          {obj.title}
                        </td>
                        <td className="px-4 py-3 text-sm">
                          <StatusBadgeLocal status={obj.status} />
                        </td>
                        <td className="px-4 py-3 text-sm">
                          <span
                            className={`font-medium ${PRIORITY_COLORS[obj.priority] ?? "text-gray-500"}`}
                          >
                            {obj.priority.charAt(0).toUpperCase() +
                              obj.priority.slice(1)}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-sm">
                          <BudgetBar spent={obj.spent} budget={obj.budget} />
                        </td>
                        <td className="px-4 py-3 text-sm text-gray-600">
                          {obj.request_count}
                        </td>
                        <td className="px-4 py-3 text-sm font-mono text-gray-500">
                          {obj.org_address}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="rounded-lg border border-gray-200 bg-white p-8 text-center">
                <p className="text-sm text-gray-500">
                  {objectives.length === 0
                    ? "No objectives yet. Create one to get started."
                    : "No objectives match the selected filter."}
                </p>
              </div>
            )}
          </>
        )}
      </div>
    </DashboardShell>
  );
}
