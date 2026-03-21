// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * AuditFilters -- filter bar for the audit trail table.
 *
 * Provides controls for filtering audit anchors by:
 *   - Agent name or ID (text)
 *   - Action name substring (text)
 *   - Team (dropdown)
 *   - Verification level (dropdown with colored badges)
 *   - Date range (start + end date pickers)
 *
 * Shows active filter count on the "Clear Filters" button.
 */

"use client";

import type { VerificationLevel } from "../../types/pact";

/** Current filter state. */
export interface AuditFilterState {
  agentQuery: string;
  actionQuery: string;
  teamId: string;
  level: VerificationLevel | "";
  startDate: string;
  endDate: string;
}

interface AuditFiltersProps {
  /** Current filter values. */
  filters: AuditFilterState;
  /** Callback when any filter value changes. */
  onChange: (filters: AuditFilterState) => void;
  /** Callback to reset all filters. */
  onReset: () => void;
  /** Available team IDs for the team dropdown. */
  teams: string[];
}

/** Verification level options with color dots matching the CARE gradient. */
const LEVELS: Array<{
  value: VerificationLevel | "";
  label: string;
  dotColor: string;
}> = [
  { value: "", label: "All Levels", dotColor: "" },
  { value: "AUTO_APPROVED", label: "Auto Approved", dotColor: "bg-green-500" },
  { value: "FLAGGED", label: "Flagged", dotColor: "bg-yellow-500" },
  { value: "HELD", label: "Held", dotColor: "bg-orange-500" },
  { value: "BLOCKED", label: "Blocked", dotColor: "bg-red-500" },
];

/** Count active filters (non-empty values). */
function countActiveFilters(filters: AuditFilterState): number {
  let count = 0;
  if (filters.agentQuery) count++;
  if (filters.actionQuery) count++;
  if (filters.teamId) count++;
  if (filters.level) count++;
  if (filters.startDate) count++;
  if (filters.endDate) count++;
  return count;
}

/** Filter bar for audit trail entries. */
export default function AuditFilters({
  filters,
  onChange,
  onReset,
  teams,
}: AuditFiltersProps) {
  const activeCount = countActiveFilters(filters);

  return (
    <div className="space-y-3 rounded-lg border border-gray-200 bg-white p-4">
      {/* First row: text searches */}
      <div className="flex flex-wrap items-end gap-4">
        {/* Agent search */}
        <div className="min-w-[200px] flex-1">
          <label
            htmlFor="audit-agent-filter"
            className="mb-1 block text-xs font-medium text-gray-600"
          >
            Agent
          </label>
          <input
            id="audit-agent-filter"
            type="text"
            value={filters.agentQuery}
            onChange={(e) =>
              onChange({ ...filters, agentQuery: e.target.value })
            }
            placeholder="Search by agent name or ID..."
            className="w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>

        {/* Action search */}
        <div className="min-w-[200px] flex-1">
          <label
            htmlFor="audit-action-filter"
            className="mb-1 block text-xs font-medium text-gray-600"
          >
            Action
          </label>
          <input
            id="audit-action-filter"
            type="text"
            value={filters.actionQuery}
            onChange={(e) =>
              onChange({ ...filters, actionQuery: e.target.value })
            }
            placeholder="Search by action name..."
            className="w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>
      </div>

      {/* Second row: dropdowns and dates */}
      <div className="flex flex-wrap items-end gap-4">
        {/* Team dropdown */}
        <div className="min-w-[160px]">
          <label
            htmlFor="audit-team-filter"
            className="mb-1 block text-xs font-medium text-gray-600"
          >
            Team
          </label>
          <select
            id="audit-team-filter"
            value={filters.teamId}
            onChange={(e) => onChange({ ...filters, teamId: e.target.value })}
            className="w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            <option value="">All Teams</option>
            {teams.map((team) => (
              <option key={team} value={team}>
                {team}
              </option>
            ))}
          </select>
        </div>

        {/* Verification level dropdown with colored dots */}
        <div className="min-w-[180px]">
          <label
            htmlFor="audit-level-filter"
            className="mb-1 block text-xs font-medium text-gray-600"
          >
            Verification Level
          </label>
          <div className="relative">
            {/* Colored dot indicator for selected level */}
            {filters.level && (
              <span
                className={`pointer-events-none absolute left-2.5 top-1/2 h-2 w-2 -translate-y-1/2 rounded-full ${
                  LEVELS.find((l) => l.value === filters.level)?.dotColor ?? ""
                }`}
              />
            )}
            <select
              id="audit-level-filter"
              value={filters.level}
              onChange={(e) =>
                onChange({
                  ...filters,
                  level: e.target.value as VerificationLevel | "",
                })
              }
              className={`w-full rounded-md border border-gray-300 py-1.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 ${
                filters.level ? "pl-7 pr-3" : "px-3"
              }`}
            >
              {LEVELS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Start date */}
        <div className="min-w-[150px]">
          <label
            htmlFor="audit-start-date"
            className="mb-1 block text-xs font-medium text-gray-600"
          >
            From
          </label>
          <input
            id="audit-start-date"
            type="date"
            value={filters.startDate}
            onChange={(e) =>
              onChange({ ...filters, startDate: e.target.value })
            }
            className="w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>

        {/* End date */}
        <div className="min-w-[150px]">
          <label
            htmlFor="audit-end-date"
            className="mb-1 block text-xs font-medium text-gray-600"
          >
            To
          </label>
          <input
            id="audit-end-date"
            type="date"
            value={filters.endDate}
            onChange={(e) => onChange({ ...filters, endDate: e.target.value })}
            className="w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>

        {/* Clear Filters button with active count */}
        {activeCount > 0 && (
          <button
            onClick={onReset}
            className="flex items-center gap-1.5 rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50"
          >
            Clear Filters
            <span className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-gray-200 text-xs font-semibold text-gray-700">
              {activeCount}
            </span>
          </button>
        )}
      </div>
    </div>
  );
}
