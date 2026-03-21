// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * Audit Trail page -- searchable, filterable view of all audit anchors.
 *
 * Provides filters for agent, action, team, verification level, and date range.
 * Displays matching anchors in a sortable table with client-side pagination.
 * Supports CSV/JSON export and a slide-out detail panel for each anchor.
 *
 * NOTE: Pagination is currently client-side. When the API supports offset/limit
 * parameters, this should be replaced with server-side pagination to avoid
 * loading all records into memory.
 */

"use client";

import { useState, useMemo } from "react";
import DashboardShell from "../../components/layout/DashboardShell";
import AuditFilters, {
  type AuditFilterState,
} from "../../components/audit/AuditFilters";
import AuditTable from "../../components/audit/AuditTable";
import Pagination from "../../components/audit/elements/Pagination";
import ExportButtons from "../../components/audit/elements/ExportButtons";
import AnchorDetailPanel from "../../components/audit/elements/AnchorDetailPanel";
import ErrorAlert from "../../components/ui/ErrorAlert";
import { TableSkeleton } from "../../components/ui/Skeleton";
import { useApi } from "../../lib/use-api";
import type { AuditAnchor } from "../../types/pact";

const DEFAULT_PAGE_SIZE = 25;

const EMPTY_FILTERS: AuditFilterState = {
  agentQuery: "",
  actionQuery: "",
  teamId: "",
  level: "",
  startDate: "",
  endDate: "",
};

/** Apply client-side filters to audit anchors. */
function applyFilters(
  anchors: AuditAnchor[],
  filters: AuditFilterState,
): AuditAnchor[] {
  let result = anchors;

  if (filters.agentQuery) {
    const query = filters.agentQuery.toLowerCase();
    result = result.filter(
      (a) =>
        a.agent_name.toLowerCase().includes(query) ||
        a.agent_id.toLowerCase().includes(query),
    );
  }

  if (filters.actionQuery) {
    const query = filters.actionQuery.toLowerCase();
    result = result.filter((a) => a.action.toLowerCase().includes(query));
  }

  if (filters.teamId) {
    result = result.filter((a) => a.team_id === filters.teamId);
  }

  if (filters.level) {
    result = result.filter((a) => a.verification_level === filters.level);
  }

  if (filters.startDate) {
    const start = new Date(filters.startDate);
    result = result.filter((a) => new Date(a.timestamp) >= start);
  }

  if (filters.endDate) {
    const end = new Date(filters.endDate);
    end.setHours(23, 59, 59, 999);
    result = result.filter((a) => new Date(a.timestamp) <= end);
  }

  return result;
}

/** Extract unique team IDs from anchors for the team filter dropdown. */
function extractTeams(anchors: AuditAnchor[]): string[] {
  const teams = new Set(anchors.map((a) => a.team_id));
  return Array.from(teams).sort();
}

/**
 * Paginate an array client-side.
 *
 * NOTE: This is a temporary measure. When the API supports offset/limit
 * query parameters, pagination should be done server-side to avoid loading
 * all records into the browser.
 */
function paginateClientSide<T>(
  items: T[],
  page: number,
  pageSize: number,
): T[] {
  const start = (page - 1) * pageSize;
  return items.slice(start, start + pageSize);
}

export default function AuditPage() {
  const [filters, setFilters] = useState<AuditFilterState>(EMPTY_FILTERS);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);
  const [selectedAnchor, setSelectedAnchor] = useState<AuditAnchor | null>(
    null,
  );

  const { data, loading, error, refetch } = useApi(
    (client) => client.listAuditAnchors(),
    [],
  );

  // Extract unique team IDs for the dropdown
  const teams = useMemo(() => {
    if (!data?.anchors) return [];
    return extractTeams(data.anchors);
  }, [data]);

  // Apply filters
  const filteredAnchors = useMemo(() => {
    if (!data?.anchors) return [];
    return applyFilters(data.anchors, filters);
  }, [data, filters]);

  // Reset to page 1 when filters change
  const handleFilterChange = (newFilters: AuditFilterState) => {
    setFilters(newFilters);
    setPage(1);
  };

  const handleFilterReset = () => {
    setFilters(EMPTY_FILTERS);
    setPage(1);
  };

  const handlePageSizeChange = (newSize: number) => {
    setPageSize(newSize);
    setPage(1);
  };

  // Paginate the filtered results (client-side)
  const paginatedAnchors = useMemo(
    () => paginateClientSide(filteredAnchors, page, pageSize),
    [filteredAnchors, page, pageSize],
  );

  return (
    <DashboardShell
      activePath="/audit"
      title="Audit Trail"
      breadcrumbs={[
        { label: "Dashboard", href: "/" },
        { label: "Audit Trail" },
      ]}
    >
      <div className="space-y-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <p className="text-sm text-gray-600">
            Cryptographic audit anchors recording every significant agent
            action. Each anchor provides an immutable proof of the trust state
            at a point in time.
          </p>

          {/* Export buttons */}
          {data && !loading && <ExportButtons anchors={filteredAnchors} />}
        </div>

        {/* Filters */}
        <AuditFilters
          filters={filters}
          onChange={handleFilterChange}
          onReset={handleFilterReset}
          teams={teams}
        />

        {/* Loading state */}
        {loading && <TableSkeleton rows={8} />}

        {/* Error state */}
        {error && <ErrorAlert message={error} onRetry={refetch} />}

        {/* Results summary */}
        {data && !loading && (
          <p className="text-xs text-gray-500">
            {filteredAnchors.length} of {data.anchors.length} audit anchors
            match the current filters
          </p>
        )}

        {/* Audit table (paginated) */}
        {data && (
          <AuditTable
            anchors={paginatedAnchors}
            onAnchorClick={setSelectedAnchor}
          />
        )}

        {/* Pagination */}
        {data && !loading && filteredAnchors.length > 0 && (
          <Pagination
            page={page}
            pageSize={pageSize}
            totalRecords={filteredAnchors.length}
            onPageChange={setPage}
            onPageSizeChange={handlePageSizeChange}
          />
        )}
      </div>

      {/* Anchor detail slide-out panel */}
      {selectedAnchor && (
        <AnchorDetailPanel
          anchor={selectedAnchor}
          onClose={() => setSelectedAnchor(null)}
        />
      )}
    </DashboardShell>
  );
}
