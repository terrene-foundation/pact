// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * Audit Trail page -- searchable, filterable view of all audit anchors.
 *
 * Uses React Query (useAuditAnchors) for data fetching, Shadcn UI components
 * for filters (Select, Input) and display (Table, Skeleton), and the existing
 * AuditTable/Pagination/ExportButtons/AnchorDetailPanel subcomponents.
 *
 * NOTE: Pagination is currently client-side. When the API supports offset/limit
 * parameters, this should be replaced with server-side pagination to avoid
 * loading all records into memory.
 */

"use client";

export const dynamic = "force-dynamic";

import { Suspense, useState, useMemo, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import DashboardShell from "../../components/layout/DashboardShell";
import AuditTable from "../../components/audit/AuditTable";
import Pagination from "../../components/audit/elements/Pagination";
import ExportButtons from "../../components/audit/elements/ExportButtons";
import AnchorDetailPanel from "../../components/audit/elements/AnchorDetailPanel";
import { useAuditAnchors } from "@/hooks";
import type { AuditAnchor, VerificationLevel } from "../../types/pact";
import {
  Card,
  CardContent,
  Input,
  Label,
  Button,
  Badge,
  Skeleton,
  Alert,
  AlertTitle,
  AlertDescription,
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/shadcn";

const DEFAULT_PAGE_SIZE = 25;

/** Filter state for audit anchors. */
interface AuditFilterState {
  agentQuery: string;
  actionQuery: string;
  teamId: string;
  level: VerificationLevel | "";
  startDate: string;
  endDate: string;
}

const EMPTY_FILTERS: AuditFilterState = {
  agentQuery: "",
  actionQuery: "",
  teamId: "",
  level: "",
  startDate: "",
  endDate: "",
};

/** Verification level options with semantic colors. */
const LEVELS: Array<{
  value: VerificationLevel | "";
  label: string;
  variant: "default" | "secondary" | "destructive" | "outline";
}> = [
  { value: "", label: "All Levels", variant: "outline" },
  { value: "AUTO_APPROVED", label: "Auto Approved", variant: "default" },
  { value: "FLAGGED", label: "Flagged", variant: "secondary" },
  { value: "HELD", label: "Held", variant: "secondary" },
  { value: "BLOCKED", label: "Blocked", variant: "destructive" },
];

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

/** Paginate an array client-side. */
function paginateClientSide<T>(
  items: T[],
  page: number,
  pageSize: number,
): T[] {
  const start = (page - 1) * pageSize;
  return items.slice(start, start + pageSize);
}

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

/** Table loading skeleton. */
function AuditTableSkeleton() {
  return (
    <Card>
      <CardContent className="p-4 space-y-3">
        {Array.from({ length: 8 }).map((_, i) => (
          <div key={i} className="flex gap-4">
            <Skeleton className="h-4 w-32" />
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-4 flex-1" />
            <Skeleton className="h-4 w-20 rounded-full" />
            <Skeleton className="h-4 w-16" />
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

/** Valid verification levels for URL param validation. */
const VALID_LEVELS = new Set<string>([
  "AUTO_APPROVED",
  "FLAGGED",
  "HELD",
  "BLOCKED",
]);

export default function AuditPage() {
  return (
    <Suspense>
      <AuditPageInner />
    </Suspense>
  );
}

function AuditPageInner() {
  const searchParams = useSearchParams();
  const [filters, setFilters] = useState<AuditFilterState>(() => {
    const levelParam = searchParams.get("level") ?? "";
    const normalizedLevel = levelParam.toUpperCase();
    return {
      ...EMPTY_FILTERS,
      level: VALID_LEVELS.has(normalizedLevel)
        ? (normalizedLevel as VerificationLevel)
        : "",
    };
  });
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);
  const [selectedAnchor, setSelectedAnchor] = useState<AuditAnchor | null>(
    null,
  );

  // Sync filter state when URL search params change externally
  useEffect(() => {
    const levelParam = searchParams.get("level") ?? "";
    const normalizedLevel = levelParam.toUpperCase();
    if (VALID_LEVELS.has(normalizedLevel)) {
      setFilters((prev) => ({
        ...prev,
        level: normalizedLevel as VerificationLevel,
      }));
      setPage(1);
    }
  }, [searchParams]);

  const { data, isLoading, error, refetch } = useAuditAnchors();

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

  const activeFilterCount = countActiveFilters(filters);

  // Reset to page 1 when filters change
  const handleFilterChange = (partial: Partial<AuditFilterState>) => {
    setFilters((prev) => ({ ...prev, ...partial }));
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
          <p className="text-sm text-muted-foreground">
            Cryptographic audit anchors recording every significant agent
            action. Each anchor provides an immutable proof of the trust state
            at a point in time.
          </p>

          {/* Export buttons */}
          {data && !isLoading && <ExportButtons anchors={filteredAnchors} />}
        </div>

        {/* Filters */}
        <Card>
          <CardContent className="p-4 space-y-3">
            {/* First row: text searches */}
            <div className="flex flex-wrap items-end gap-4">
              <div className="min-w-[200px] flex-1">
                <Label
                  htmlFor="audit-agent-filter"
                  className="mb-1 block text-xs"
                >
                  Agent
                </Label>
                <Input
                  id="audit-agent-filter"
                  value={filters.agentQuery}
                  onChange={(e) =>
                    handleFilterChange({ agentQuery: e.target.value })
                  }
                  placeholder="Search by agent name or ID..."
                />
              </div>
              <div className="min-w-[200px] flex-1">
                <Label
                  htmlFor="audit-action-filter"
                  className="mb-1 block text-xs"
                >
                  Action
                </Label>
                <Input
                  id="audit-action-filter"
                  value={filters.actionQuery}
                  onChange={(e) =>
                    handleFilterChange({ actionQuery: e.target.value })
                  }
                  placeholder="Search by action name..."
                />
              </div>
            </div>

            {/* Second row: dropdowns and dates */}
            <div className="flex flex-wrap items-end gap-4">
              {/* Team dropdown */}
              <div className="min-w-[160px]">
                <Label className="mb-1 block text-xs">Team</Label>
                <Select
                  value={filters.teamId || "all"}
                  onValueChange={(value) =>
                    handleFilterChange({
                      teamId: value === "all" ? "" : value,
                    })
                  }
                >
                  <SelectTrigger>
                    <SelectValue placeholder="All Teams" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Teams</SelectItem>
                    {teams.map((team) => (
                      <SelectItem key={team} value={team}>
                        {team}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Verification level dropdown */}
              <div className="min-w-[180px]">
                <Label className="mb-1 block text-xs">Verification Level</Label>
                <Select
                  value={filters.level || "all"}
                  onValueChange={(value) =>
                    handleFilterChange({
                      level:
                        value === "all" ? "" : (value as VerificationLevel),
                    })
                  }
                >
                  <SelectTrigger>
                    <SelectValue placeholder="All Levels" />
                  </SelectTrigger>
                  <SelectContent>
                    {LEVELS.map((opt) => (
                      <SelectItem
                        key={opt.value || "all"}
                        value={opt.value || "all"}
                      >
                        {opt.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Start date */}
              <div className="min-w-[150px]">
                <Label className="mb-1 block text-xs">From</Label>
                <Input
                  type="date"
                  value={filters.startDate}
                  onChange={(e) =>
                    handleFilterChange({ startDate: e.target.value })
                  }
                />
              </div>

              {/* End date */}
              <div className="min-w-[150px]">
                <Label className="mb-1 block text-xs">To</Label>
                <Input
                  type="date"
                  value={filters.endDate}
                  onChange={(e) =>
                    handleFilterChange({ endDate: e.target.value })
                  }
                />
              </div>

              {/* Clear Filters button */}
              {activeFilterCount > 0 && (
                <Button variant="outline" size="sm" onClick={handleFilterReset}>
                  Clear Filters
                  <Badge variant="secondary" className="ml-1.5">
                    {activeFilterCount}
                  </Badge>
                </Button>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Loading state */}
        {isLoading && <AuditTableSkeleton />}

        {/* Error state */}
        {error && (
          <Alert variant="destructive">
            <AlertTitle>Failed to load audit anchors</AlertTitle>
            <AlertDescription className="flex items-center justify-between">
              <span>
                {error instanceof Error ? error.message : "Unknown error"}
              </span>
              <Button variant="outline" size="sm" onClick={() => refetch()}>
                Retry
              </Button>
            </AlertDescription>
          </Alert>
        )}

        {/* Results summary */}
        {data && !isLoading && (
          <p className="text-xs text-muted-foreground">
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
        {data && !isLoading && filteredAnchors.length > 0 && (
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
