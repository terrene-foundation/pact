// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * Envelopes list page -- displays all constraint envelopes from the API.
 *
 * Each row links to the envelope detail view showing five dimension gauges.
 */

"use client";

import DashboardShell from "../../components/layout/DashboardShell";
import DataTable, { type Column } from "../../components/ui/DataTable";
import ErrorAlert from "../../components/ui/ErrorAlert";
import { TableSkeleton } from "../../components/ui/Skeleton";
import { useApi } from "../../lib/use-api";
import type { EnvelopeSummary } from "../../types/pact";

/** Column definitions for the envelope list table. */
const COLUMNS: Column<EnvelopeSummary>[] = [
  {
    key: "envelope_id",
    header: "Envelope ID",
    render: (row) => (
      <a
        href={`/envelopes/${row.envelope_id}`}
        className="font-medium text-blue-600 hover:text-blue-800 hover:underline"
      >
        {row.envelope_id}
      </a>
    ),
  },
  {
    key: "description",
    header: "Description",
  },
  {
    key: "agent_id",
    header: "Agent",
  },
  {
    key: "team_id",
    header: "Team",
  },
];

export default function EnvelopesPage() {
  const { data, loading, error, refetch } = useApi(
    (client) => client.listEnvelopes(),
    [],
  );

  return (
    <DashboardShell
      activePath="/envelopes"
      title="Constraint Envelopes"
      breadcrumbs={[{ label: "Dashboard", href: "/" }, { label: "Envelopes" }]}
    >
      <div className="space-y-6">
        <p className="text-sm text-gray-600">
          Constraint envelopes define the five-dimensional boundaries for agent
          actions: Financial, Operational, Temporal, Data Access, and
          Communication. Select an envelope to see utilization details.
        </p>

        {loading && <TableSkeleton rows={5} />}
        {error && <ErrorAlert message={error} onRetry={refetch} />}
        {data && (
          <DataTable
            columns={COLUMNS}
            data={data.envelopes}
            rowKey={(row) => row.envelope_id}
            filterPlaceholder="Search envelopes..."
            emptyMessage="No constraint envelopes found."
          />
        )}
      </div>
    </DashboardShell>
  );
}
