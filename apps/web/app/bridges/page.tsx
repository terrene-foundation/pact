// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * Bridge list page -- shows all Cross-Functional Bridges with lifecycle
 * status badges (color-coded), type indicators, and team connections.
 *
 * Links to bridge detail pages and the bridge creation wizard.
 */

"use client";

import { useState } from "react";
import DashboardShell from "../../components/layout/DashboardShell";
import ErrorAlert from "../../components/ui/ErrorAlert";
import StatusBadge from "../../components/ui/StatusBadge";
import { CardSkeleton } from "../../components/ui/Skeleton";
import { useApi } from "../../lib/use-api";
import type { BridgeStatus } from "../../types/pact";

/** Human-readable labels for bridge types. */
const BRIDGE_TYPE_LABELS: Record<string, string> = {
  standing: "Standing",
  scoped: "Scoped",
  ad_hoc: "Ad-Hoc",
};

/** All possible bridge statuses for the filter dropdown. */
const STATUS_OPTIONS: Array<{ value: BridgeStatus | "all"; label: string }> = [
  { value: "all", label: "All Statuses" },
  { value: "active", label: "Active" },
  { value: "pending", label: "Pending" },
  { value: "negotiating", label: "Negotiating" },
  { value: "suspended", label: "Suspended" },
  { value: "expired", label: "Expired" },
  { value: "closed", label: "Closed" },
  { value: "revoked", label: "Revoked" },
];

export default function BridgesPage() {
  const [statusFilter, setStatusFilter] = useState<BridgeStatus | "all">("all");

  const {
    data: bridgesData,
    loading,
    error,
    refetch,
  } = useApi((client) => client.listBridges(), []);

  const allBridges = bridgesData?.bridges ?? [];
  const bridges =
    statusFilter === "all"
      ? allBridges
      : allBridges.filter((b) => b.status === statusFilter);

  // Group bridges by status for summary counts
  const statusCounts = bridges.reduce(
    (acc, b) => {
      acc[b.status] = (acc[b.status] ?? 0) + 1;
      return acc;
    },
    {} as Record<string, number>,
  );

  return (
    <DashboardShell
      activePath="/bridges"
      title="Cross-Functional Bridges"
      breadcrumbs={[{ label: "Dashboard", href: "/" }, { label: "Bridges" }]}
      actions={
        <div className="flex gap-2">
          <a
            href="/bridges/create"
            className="rounded-md bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
          >
            Create Bridge
          </a>
          <button
            onClick={refetch}
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
          Cross-Functional Bridges enable controlled data and communication flow
          between agent teams. Standing bridges are permanent, Scoped bridges
          are time-bounded, and Ad-Hoc bridges serve one-time requests.
        </p>

        {error && <ErrorAlert message={error} onRetry={refetch} />}

        {/* Summary stat cards */}
        {!loading && bridges.length > 0 && (
          <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-6">
            {[
              {
                label: "Total",
                count: bridges.length,
                color: "bg-gray-50 text-gray-900",
              },
              {
                label: "Active",
                count: statusCounts["active"] ?? 0,
                color: "bg-green-50 text-green-700",
              },
              {
                label: "Pending",
                count: statusCounts["pending"] ?? 0,
                color: "bg-yellow-50 text-yellow-700",
              },
              {
                label: "Suspended",
                count: statusCounts["suspended"] ?? 0,
                color: "bg-orange-50 text-orange-700",
              },
              {
                label: "Closed",
                count: statusCounts["closed"] ?? 0,
                color: "bg-gray-50 text-gray-600",
              },
              {
                label: "Revoked",
                count: statusCounts["revoked"] ?? 0,
                color: "bg-red-50 text-red-700",
              },
            ].map((stat) => (
              <div
                key={stat.label}
                className={`rounded-lg border border-gray-200 p-3 text-center ${stat.color}`}
              >
                <p className="text-lg font-bold">{stat.count}</p>
                <p className="text-xs">{stat.label}</p>
              </div>
            ))}
          </div>
        )}

        {/* Loading skeleton */}
        {loading && (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <CardSkeleton key={i} />
            ))}
          </div>
        )}

        {/* Bridge list */}
        {!loading && bridges.length > 0 && (
          <div className="overflow-hidden rounded-lg border border-gray-200 bg-white">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    Bridge
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    Type
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    Source / Target
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    Status
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    Created
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {bridges.map((bridge) => (
                  <tr
                    key={bridge.bridge_id}
                    className="hover:bg-gray-50 cursor-pointer transition-colors"
                    onClick={() => {
                      window.location.href = `/bridges/${bridge.bridge_id}`;
                    }}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        window.location.href = `/bridges/${bridge.bridge_id}`;
                      }
                    }}
                    tabIndex={0}
                    role="link"
                    aria-label={`Bridge: ${bridge.purpose}, status ${bridge.status}`}
                  >
                    <td className="px-4 py-3">
                      <div>
                        <p className="text-sm font-medium text-gray-900 truncate max-w-xs">
                          {bridge.purpose}
                        </p>
                        <p className="text-xs text-gray-400 font-mono">
                          {bridge.bridge_id}
                        </p>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <span className="text-sm text-gray-700">
                        {BRIDGE_TYPE_LABELS[bridge.bridge_type] ??
                          bridge.bridge_type}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="text-sm text-gray-700">
                        <span className="font-medium">
                          {bridge.source_team_id}
                        </span>
                        <span className="mx-1 text-gray-400">&rarr;</span>
                        <span className="font-medium">
                          {bridge.target_team_id}
                        </span>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge value={bridge.status} size="xs" />
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-500">
                      {new Date(bridge.created_at).toLocaleDateString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Empty state */}
        {!loading && bridges.length === 0 && (
          <div className="rounded-lg border border-gray-200 bg-white p-8 text-center">
            <p className="text-gray-500">
              No bridges found. Cross-Functional Bridges connect agent teams for
              controlled data sharing.
            </p>
            <a
              href="/bridges/create"
              className="mt-4 inline-block rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
            >
              Create Your First Bridge
            </a>
          </div>
        )}
      </div>
    </DashboardShell>
  );
}
