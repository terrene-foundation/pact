// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * Pool Management page -- displays agent pools with member counts,
 * capacity utilization, and routing strategy. Supports pool creation
 * and member management via drill-down detail view.
 */

"use client";

import { useState, useCallback, useMemo } from "react";
import DashboardShell from "../../components/layout/DashboardShell";
import ErrorAlert from "../../components/ui/ErrorAlert";
import { CardSkeleton } from "../../components/ui/Skeleton";
import { useAuth } from "../../lib/auth-context";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface Pool {
  id: string;
  name: string;
  org_id: string;
  type: string;
  routing_strategy: string;
  member_count: number;
  capacity: number;
  active_requests: number;
  created_at: string;
}

interface PoolMember {
  agent_id: string;
  name: string;
  role: string;
  status: string;
  current_load: number;
  joined_at: string;
}

interface PoolDetail extends Pool {
  members: PoolMember[];
  description: string;
}

interface CreatePoolForm {
  name: string;
  org_id: string;
  type: string;
  routing_strategy: string;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const POOL_TYPES = [
  { value: "general", label: "General" },
  { value: "specialized", label: "Specialized" },
  { value: "overflow", label: "Overflow" },
] as const;

const ROUTING_STRATEGIES = [
  { value: "round_robin", label: "Round Robin" },
  { value: "least_loaded", label: "Least Loaded" },
  { value: "priority_based", label: "Priority Based" },
  { value: "skill_match", label: "Skill Match" },
] as const;

const MEMBER_STATUS_COLORS: Record<string, string> = {
  active: "bg-green-100 text-green-800 border-green-300",
  idle: "bg-blue-100 text-blue-800 border-blue-300",
  busy: "bg-orange-100 text-orange-800 border-orange-300",
  offline: "bg-gray-100 text-gray-600 border-gray-300",
  suspended: "bg-red-100 text-red-800 border-red-300",
};

const EMPTY_FORM: CreatePoolForm = {
  name: "",
  org_id: "",
  type: "general",
  routing_strategy: "round_robin",
};

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function CapacityBar({ used, capacity }: { used: number; capacity: number }) {
  const pct = capacity > 0 ? Math.min((used / capacity) * 100, 100) : 0;
  const barColor =
    pct >= 90
      ? "bg-red-500"
      : pct >= 70
        ? "bg-orange-500"
        : pct >= 40
          ? "bg-blue-500"
          : "bg-green-500";

  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs text-gray-500">
        <span>
          {used} / {capacity} members
        </span>
        <span>{Math.round(pct)}%</span>
      </div>
      <div className="h-2 w-full rounded-full bg-gray-200">
        <div
          className={`h-2 rounded-full ${barColor} transition-all`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

function RoutingBadge({ strategy }: { strategy: string }) {
  const label = strategy
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
  return (
    <span className="inline-flex items-center rounded-md bg-indigo-50 px-2 py-0.5 text-xs font-medium text-indigo-700 border border-indigo-200">
      {label}
    </span>
  );
}

function TypeBadge({ type }: { type: string }) {
  const colors: Record<string, string> = {
    general: "bg-blue-50 text-blue-700 border-blue-200",
    specialized: "bg-purple-50 text-purple-700 border-purple-200",
    overflow: "bg-amber-50 text-amber-700 border-amber-200",
  };
  const colorClass = colors[type] ?? "bg-gray-50 text-gray-700 border-gray-200";
  const label = type.charAt(0).toUpperCase() + type.slice(1);
  return (
    <span
      className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium border ${colorClass}`}
    >
      {label}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Pool card
// ---------------------------------------------------------------------------

function PoolCard({ pool, onClick }: { pool: Pool; onClick: () => void }) {
  return (
    <div
      onClick={onClick}
      className="cursor-pointer rounded-lg border border-gray-200 bg-white p-5 hover:border-blue-300 hover:shadow-sm transition-all"
    >
      <div className="flex items-start justify-between mb-3">
        <div>
          <h3 className="text-sm font-semibold text-gray-900">{pool.name}</h3>
          <p className="text-xs text-gray-500 font-mono">{pool.org_id}</p>
        </div>
        <TypeBadge type={pool.type} />
      </div>

      <CapacityBar used={pool.member_count} capacity={pool.capacity} />

      <div className="mt-3 flex items-center justify-between">
        <RoutingBadge strategy={pool.routing_strategy} />
        <span className="text-xs text-gray-500">
          {pool.active_requests} active request
          {pool.active_requests !== 1 ? "s" : ""}
        </span>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Detail panel
// ---------------------------------------------------------------------------

function PoolDetailPanel({
  pool,
  onClose,
  onMemberRemoved,
  onMemberAdded,
}: {
  pool: PoolDetail;
  onClose: () => void;
  onMemberRemoved: () => void;
  onMemberAdded: () => void;
}) {
  const [addAgentId, setAddAgentId] = useState("");
  const [addingMember, setAddingMember] = useState(false);
  const [removingId, setRemovingId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const handleAddMember = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      if (!addAgentId.trim()) return;
      setAddingMember(true);
      setActionError(null);
      try {
        const response = await fetch(
          `/api/v1/pools/${encodeURIComponent(pool.id)}/members`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ agent_id: addAgentId.trim() }),
          },
        );
        if (!response.ok) {
          const body = await response.text();
          throw new Error(`Failed to add member: ${response.status} ${body}`);
        }
        setAddAgentId("");
        onMemberAdded();
      } catch (err: unknown) {
        setActionError(
          err instanceof Error ? err.message : "Failed to add member",
        );
      } finally {
        setAddingMember(false);
      }
    },
    [addAgentId, pool.id, onMemberAdded],
  );

  const handleRemoveMember = useCallback(
    async (agentId: string) => {
      setRemovingId(agentId);
      setActionError(null);
      try {
        const response = await fetch(
          `/api/v1/pools/${encodeURIComponent(pool.id)}/members/${encodeURIComponent(agentId)}`,
          { method: "DELETE" },
        );
        if (!response.ok) {
          const body = await response.text();
          throw new Error(
            `Failed to remove member: ${response.status} ${body}`,
          );
        }
        onMemberRemoved();
      } catch (err: unknown) {
        setActionError(
          err instanceof Error ? err.message : "Failed to remove member",
        );
      } finally {
        setRemovingId(null);
      }
    },
    [pool.id, onMemberRemoved],
  );

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-6 space-y-5">
      <div className="flex items-start justify-between">
        <div>
          <h3 className="text-lg font-semibold text-gray-900">{pool.name}</h3>
          <div className="mt-1 flex items-center gap-2">
            <TypeBadge type={pool.type} />
            <RoutingBadge strategy={pool.routing_strategy} />
          </div>
        </div>
        <button
          onClick={onClose}
          className="rounded-md border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
        >
          Close
        </button>
      </div>

      {pool.description && (
        <p className="text-sm text-gray-600">{pool.description}</p>
      )}

      <CapacityBar used={pool.member_count} capacity={pool.capacity} />

      {actionError && <ErrorAlert message={actionError} />}

      {/* Add member form */}
      <form onSubmit={handleAddMember} className="flex items-end gap-3">
        <div className="flex-1">
          <label
            htmlFor="add-agent"
            className="block text-sm font-medium text-gray-700"
          >
            Add Member
          </label>
          <input
            id="add-agent"
            type="text"
            value={addAgentId}
            onChange={(e) => setAddAgentId(e.target.value)}
            placeholder="Agent ID"
            className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>
        <button
          type="submit"
          disabled={addingMember || !addAgentId.trim()}
          className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50 transition-colors"
        >
          {addingMember ? "Adding..." : "Add"}
        </button>
      </form>

      {/* Members table */}
      <div>
        <h4 className="mb-2 text-sm font-semibold text-gray-700">
          Members ({pool.members.length})
        </h4>
        {pool.members.length === 0 ? (
          <p className="text-sm text-gray-500">
            No members in this pool yet. Add agents to start routing work.
          </p>
        ) : (
          <div className="overflow-hidden rounded-lg border border-gray-200">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-2 text-left text-xs font-medium uppercase text-gray-500">
                    Agent
                  </th>
                  <th className="px-4 py-2 text-left text-xs font-medium uppercase text-gray-500">
                    Role
                  </th>
                  <th className="px-4 py-2 text-left text-xs font-medium uppercase text-gray-500">
                    Status
                  </th>
                  <th className="px-4 py-2 text-left text-xs font-medium uppercase text-gray-500">
                    Load
                  </th>
                  <th className="px-4 py-2 text-right text-xs font-medium uppercase text-gray-500">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 bg-white">
                {pool.members.map((member) => (
                  <tr key={member.agent_id} className="hover:bg-gray-50">
                    <td className="px-4 py-2">
                      <div className="text-sm font-medium text-gray-900">
                        {member.name}
                      </div>
                      <div className="text-xs font-mono text-gray-400">
                        {member.agent_id}
                      </div>
                    </td>
                    <td className="px-4 py-2 text-sm text-gray-600">
                      {member.role}
                    </td>
                    <td className="px-4 py-2 text-sm">
                      <span
                        className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${
                          MEMBER_STATUS_COLORS[member.status] ??
                          "bg-gray-100 text-gray-700 border-gray-300"
                        }`}
                      >
                        {member.status.charAt(0).toUpperCase() +
                          member.status.slice(1)}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-sm">
                      <div className="flex items-center gap-2">
                        <div className="h-1.5 w-16 rounded-full bg-gray-200">
                          <div
                            className={`h-1.5 rounded-full transition-all ${
                              member.current_load > 80
                                ? "bg-red-500"
                                : member.current_load > 50
                                  ? "bg-orange-500"
                                  : "bg-green-500"
                            }`}
                            style={{
                              width: `${Math.min(member.current_load, 100)}%`,
                            }}
                          />
                        </div>
                        <span className="text-xs text-gray-500">
                          {member.current_load}%
                        </span>
                      </div>
                    </td>
                    <td className="px-4 py-2 text-right text-sm">
                      <button
                        onClick={() => handleRemoveMember(member.agent_id)}
                        disabled={removingId === member.agent_id}
                        className="rounded-md border border-red-200 bg-red-50 px-2 py-1 text-xs font-medium text-red-700 hover:bg-red-100 disabled:opacity-50 transition-colors"
                      >
                        {removingId === member.agent_id
                          ? "Removing..."
                          : "Remove"}
                      </button>
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

function CreatePoolPanel({
  onCreated,
  onCancel,
}: {
  onCreated: () => void;
  onCancel: () => void;
}) {
  const [form, setForm] = useState<CreatePoolForm>({ ...EMPTY_FORM });
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      setSubmitting(true);
      setSubmitError(null);

      try {
        const response = await fetch("/api/v1/pools", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            name: form.name,
            org_id: form.org_id,
            type: form.type,
            routing_strategy: form.routing_strategy,
          }),
        });

        if (!response.ok) {
          const body = await response.text();
          throw new Error(`Failed to create pool: ${response.status} ${body}`);
        }

        onCreated();
      } catch (err: unknown) {
        setSubmitError(
          err instanceof Error ? err.message : "Failed to create pool",
        );
      } finally {
        setSubmitting(false);
      }
    },
    [form, onCreated],
  );

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-6">
      <h3 className="mb-4 text-lg font-semibold text-gray-900">Create Pool</h3>
      {submitError && (
        <div className="mb-4">
          <ErrorAlert message={submitError} />
        </div>
      )}
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <label
              htmlFor="pool-name"
              className="block text-sm font-medium text-gray-700"
            >
              Pool Name
            </label>
            <input
              id="pool-name"
              type="text"
              required
              value={form.name}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              placeholder="e.g. Engineering Pool"
            />
          </div>
          <div>
            <label
              htmlFor="pool-org"
              className="block text-sm font-medium text-gray-700"
            >
              Org ID
            </label>
            <input
              id="pool-org"
              type="text"
              required
              value={form.org_id}
              onChange={(e) =>
                setForm((f) => ({ ...f, org_id: e.target.value }))
              }
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              placeholder="e.g. org-001"
            />
          </div>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <label
              htmlFor="pool-type"
              className="block text-sm font-medium text-gray-700"
            >
              Type
            </label>
            <select
              id="pool-type"
              value={form.type}
              onChange={(e) => setForm((f) => ({ ...f, type: e.target.value }))}
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              {POOL_TYPES.map((pt) => (
                <option key={pt.value} value={pt.value}>
                  {pt.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label
              htmlFor="pool-routing"
              className="block text-sm font-medium text-gray-700"
            >
              Routing Strategy
            </label>
            <select
              id="pool-routing"
              value={form.routing_strategy}
              onChange={(e) =>
                setForm((f) => ({
                  ...f,
                  routing_strategy: e.target.value,
                }))
              }
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              {ROUTING_STRATEGIES.map((rs) => (
                <option key={rs.value} value={rs.value}>
                  {rs.label}
                </option>
              ))}
            </select>
          </div>
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
            {submitting ? "Creating..." : "Create Pool"}
          </button>
        </div>
      </form>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function PoolsPage() {
  const { user } = useAuth();
  const [showCreate, setShowCreate] = useState(false);
  const [pools, setPools] = useState<Pool[]>([]);
  const [detail, setDetail] = useState<PoolDetail | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  // Fetch pools list
  const fetchPools = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch("/api/v1/pools");
      if (!response.ok) {
        throw new Error(`Failed to load pools: ${response.status}`);
      }
      const result = await response.json();
      setPools(result.data?.pools ?? result.pools ?? []);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load pools");
    } finally {
      setLoading(false);
    }
  }, []);

  // Initial load
  useState(() => {
    fetchPools();
  });

  // Fetch pool detail
  const fetchDetail = useCallback(async (id: string) => {
    setDetailLoading(true);
    setSelectedId(id);
    setDetail(null);
    try {
      const response = await fetch(`/api/v1/pools/${encodeURIComponent(id)}`);
      if (!response.ok) {
        throw new Error(`Failed to load pool detail: ${response.status}`);
      }
      const result = await response.json();
      setDetail(result.data ?? result);
    } catch {
      setDetail(null);
    } finally {
      setDetailLoading(false);
    }
  }, []);

  // Summary stats
  const totalMembers = useMemo(
    () => pools.reduce((sum, p) => sum + p.member_count, 0),
    [pools],
  );
  const totalCapacity = useMemo(
    () => pools.reduce((sum, p) => sum + p.capacity, 0),
    [pools],
  );
  const totalActive = useMemo(
    () => pools.reduce((sum, p) => sum + p.active_requests, 0),
    [pools],
  );

  const handleCreated = useCallback(() => {
    setShowCreate(false);
    fetchPools();
  }, [fetchPools]);

  const handleMemberChange = useCallback(() => {
    if (selectedId) {
      fetchDetail(selectedId);
    }
    fetchPools();
  }, [selectedId, fetchDetail, fetchPools]);

  return (
    <DashboardShell
      activePath="/pools"
      title="Pool Management"
      breadcrumbs={[{ label: "Dashboard", href: "/" }, { label: "Pools" }]}
      actions={
        <div className="flex gap-2">
          <button
            onClick={() => setShowCreate(true)}
            className="rounded-md bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
          >
            New Pool
          </button>
          <button
            onClick={fetchPools}
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
          Agent pools group workers by capability and route requests using
          configurable strategies. Each pool has a capacity limit and tracks
          active request load across its members.
        </p>

        {/* Summary bar */}
        {!loading && pools.length > 0 && (
          <div className="flex flex-wrap items-center gap-6 rounded-lg border border-gray-200 bg-white px-4 py-3">
            <div>
              <span className="text-2xl font-bold text-gray-900">
                {pools.length}
              </span>
              <span className="ml-1 text-sm text-gray-500">
                pool{pools.length !== 1 ? "s" : ""}
              </span>
            </div>
            <div className="h-8 w-px bg-gray-200" />
            <div>
              <span className="text-2xl font-bold text-gray-900">
                {totalMembers}
              </span>
              <span className="ml-1 text-sm text-gray-500">
                / {totalCapacity} members
              </span>
            </div>
            <div className="h-8 w-px bg-gray-200" />
            <div>
              <span className="text-2xl font-bold text-gray-900">
                {totalActive}
              </span>
              <span className="ml-1 text-sm text-gray-500">
                active request{totalActive !== 1 ? "s" : ""}
              </span>
            </div>
          </div>
        )}

        {/* Create form */}
        {showCreate && (
          <CreatePoolPanel
            onCreated={handleCreated}
            onCancel={() => setShowCreate(false)}
          />
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
        {error && <ErrorAlert message={error} onRetry={fetchPools} />}

        {/* Detail panel */}
        {selectedId && detail && !detailLoading && (
          <PoolDetailPanel
            pool={detail}
            onClose={() => {
              setSelectedId(null);
              setDetail(null);
            }}
            onMemberRemoved={handleMemberChange}
            onMemberAdded={handleMemberChange}
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

        {/* Pool cards */}
        {!loading && !error && (
          <>
            {pools.length > 0 ? (
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {pools.map((pool) => (
                  <PoolCard
                    key={pool.id}
                    pool={pool}
                    onClick={() => fetchDetail(pool.id)}
                  />
                ))}
              </div>
            ) : (
              <div className="rounded-lg border border-gray-200 bg-white p-8 text-center">
                <p className="text-sm text-gray-500">
                  No pools configured yet. Create one to start routing work to
                  agents.
                </p>
              </div>
            )}
          </>
        )}
      </div>
    </DashboardShell>
  );
}
