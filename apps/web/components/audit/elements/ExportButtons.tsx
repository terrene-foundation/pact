// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * ExportButtons -- CSV and JSON export for audit trail data.
 *
 * Uses browser-native Blob + URL.createObjectURL to trigger downloads.
 * No external dependencies required.
 *
 * Exports include: timestamp, agent_id, action, verification_level, anchor_id.
 */

"use client";

import type { AuditAnchor } from "../../../types/pact";

interface ExportButtonsProps {
  /** The filtered audit anchors to export. */
  anchors: AuditAnchor[];
  /** Whether export is disabled (e.g., no data). */
  disabled?: boolean;
}

/** Fields included in exported files. */
const EXPORT_FIELDS = [
  "timestamp",
  "agent_id",
  "action",
  "verification_level",
  "anchor_id",
] as const;

/** Trigger a browser download for the given content. */
function downloadFile(content: string, filename: string, mimeType: string) {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

/** Generate a timestamped filename for exports. */
function exportFilename(extension: string): string {
  const date = new Date().toISOString().slice(0, 10);
  return `audit-trail-${date}.${extension}`;
}

/** Escape a CSV field value (wrap in quotes if it contains commas or quotes). */
function escapeCsvField(value: string): string {
  if (value.includes(",") || value.includes('"') || value.includes("\n")) {
    return `"${value.replace(/"/g, '""')}"`;
  }
  return value;
}

/** Export anchors as CSV. */
function exportCsv(anchors: AuditAnchor[]) {
  const header = EXPORT_FIELDS.join(",");
  const rows = anchors.map((anchor) =>
    EXPORT_FIELDS.map((field) => escapeCsvField(String(anchor[field]))).join(
      ",",
    ),
  );
  const csv = [header, ...rows].join("\n");
  downloadFile(csv, exportFilename("csv"), "text/csv;charset=utf-8");
}

/** Export anchors as formatted JSON. */
function exportJson(anchors: AuditAnchor[]) {
  const data = anchors.map((anchor) => {
    const record: Record<string, string> = {};
    for (const field of EXPORT_FIELDS) {
      record[field] = anchor[field];
    }
    return record;
  });
  const json = JSON.stringify(data, null, 2);
  downloadFile(json, exportFilename("json"), "application/json;charset=utf-8");
}

/** CSV and JSON export buttons for audit trail data. */
export default function ExportButtons({
  anchors,
  disabled = false,
}: ExportButtonsProps) {
  const isDisabled = disabled || anchors.length === 0;

  return (
    <div className="flex items-center gap-2">
      <button
        onClick={() => exportCsv(anchors)}
        disabled={isDisabled}
        className="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-xs font-medium text-gray-700 transition-colors hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
        title="Export current filtered results as CSV"
      >
        Export CSV
      </button>
      <button
        onClick={() => exportJson(anchors)}
        disabled={isDisabled}
        className="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-xs font-medium text-gray-700 transition-colors hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
        title="Export current filtered results as JSON"
      >
        Export JSON
      </button>
    </div>
  );
}
