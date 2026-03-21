// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * DmTeamSummary -- team-level summary statistics cards.
 *
 * Computes totals from the per-agent task counts returned by
 * GET /api/v1/dm/status.
 */

"use client";

import type { DmStatus } from "../../../types/pact";

interface DmTeamSummaryProps {
  status: DmStatus;
}

/** Stat card helper. */
function StatCard({
  label,
  value,
  colorBorder,
  colorBg,
  colorValue,
  colorLabel,
}: {
  label: string;
  value: string;
  colorBorder: string;
  colorBg: string;
  colorValue: string;
  colorLabel: string;
}) {
  return (
    <div
      className={`rounded-lg border p-4 text-center ${colorBorder} ${colorBg}`}
    >
      <p className={`text-2xl font-bold ${colorValue}`}>{value}</p>
      <p className={`text-xs ${colorLabel}`}>{label}</p>
    </div>
  );
}

/** Team-level summary row for the DM dashboard. */
export default function DmTeamSummary({ status }: DmTeamSummaryProps) {
  const totalTasks = status.agents.reduce(
    (sum, a) => sum + (a.tasks_submitted ?? 0),
    0,
  );
  const completedTasks = status.agents.reduce(
    (sum, a) => sum + (a.tasks_completed ?? 0),
    0,
  );
  const heldTasks = status.agents.reduce(
    (sum, a) => sum + (a.tasks_held ?? 0),
    0,
  );
  const activeAgents = status.agents.filter(
    (a) => a.status === "active",
  ).length;
  const approvalRate =
    totalTasks > 0 ? Math.round((completedTasks / totalTasks) * 100) : 100;

  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
      <StatCard
        label="Total Tasks"
        value={String(totalTasks)}
        colorBorder="border-gray-200"
        colorBg="bg-white"
        colorValue="text-gray-900"
        colorLabel="text-gray-500"
      />
      <StatCard
        label="Completion Rate"
        value={`${approvalRate}%`}
        colorBorder="border-green-200"
        colorBg="bg-green-50"
        colorValue="text-green-700"
        colorLabel="text-green-600"
      />
      <StatCard
        label="Active Agents"
        value={String(activeAgents)}
        colorBorder="border-blue-200"
        colorBg="bg-blue-50"
        colorValue="text-blue-700"
        colorLabel="text-blue-600"
      />
      <StatCard
        label="Held Tasks"
        value={String(heldTasks)}
        colorBorder={heldTasks > 0 ? "border-yellow-200" : "border-gray-200"}
        colorBg={heldTasks > 0 ? "bg-yellow-50" : "bg-white"}
        colorValue={heldTasks > 0 ? "text-yellow-700" : "text-gray-900"}
        colorLabel={heldTasks > 0 ? "text-yellow-600" : "text-gray-500"}
      />
    </div>
  );
}
