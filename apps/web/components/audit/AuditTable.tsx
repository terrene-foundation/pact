// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * AuditTable -- audit anchor table with agent, time, level, and action columns.
 *
 * Displays audit trail entries using the DataTable component with
 * color-coded verification level badges. Supports clicking an anchor ID
 * to open the detail panel.
 */

"use client";

import type { AuditAnchor } from "../../types/pact";
import DataTable, { type Column } from "../ui/DataTable";
import StatusBadge from "../ui/StatusBadge";

interface AuditTableProps {
  /** Audit anchor entries to display (current page only). */
  anchors: AuditAnchor[];
  /** Callback when an anchor ID is clicked. */
  onAnchorClick?: (anchor: AuditAnchor) => void;
}

/** Format an ISO timestamp to a readable date/time string. */
function formatTimestamp(iso: string): string {
  try {
    const date = new Date(iso);
    return date.toLocaleString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return iso;
  }
}

/** Build column definitions. Accepts the click handler to close over it. */
function buildColumns(
  onAnchorClick?: (anchor: AuditAnchor) => void,
): Column<AuditAnchor>[] {
  return [
    {
      key: "timestamp",
      header: "Time",
      accessor: (row) => row.timestamp,
      render: (row) => (
        <span className="text-gray-600 tabular-nums">
          {formatTimestamp(row.timestamp)}
        </span>
      ),
    },
    {
      key: "agent_name",
      header: "Agent",
      render: (row) => (
        <div>
          <a
            href={`/agents/${row.agent_id}`}
            className="font-medium text-gray-900 hover:text-blue-600"
          >
            {row.agent_name}
          </a>
          <p className="text-xs text-gray-500">{row.team_id}</p>
        </div>
      ),
    },
    {
      key: "action",
      header: "Action",
      render: (row) => (
        <div>
          <p className="text-gray-900">{row.action}</p>
          {row.details && (
            <p className="max-w-xs truncate text-xs text-gray-500">
              {row.details}
            </p>
          )}
        </div>
      ),
    },
    {
      key: "verification_level",
      header: "Level",
      accessor: (row) => row.verification_level,
      render: (row) => <StatusBadge value={row.verification_level} size="sm" />,
    },
    {
      key: "anchor_id",
      header: "Anchor ID",
      render: (row) => (
        <button
          onClick={(e) => {
            e.stopPropagation();
            onAnchorClick?.(row);
          }}
          className="font-mono text-xs text-blue-600 hover:text-blue-800 hover:underline"
          title="View full anchor details"
        >
          {row.anchor_id.slice(0, 12)}...
        </button>
      ),
    },
  ];
}

/** Audit trail table component. */
export default function AuditTable({
  anchors,
  onAnchorClick,
}: AuditTableProps) {
  const columns = buildColumns(onAnchorClick);

  return (
    <DataTable
      columns={columns}
      data={anchors}
      rowKey={(row) => row.anchor_id}
      filterable={false}
      emptyMessage="No audit anchors found matching the current filters."
    />
  );
}
