// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * Request Queue page -- displays work requests with governance verdicts,
 * status tracking, priority indicators, and assignment details.
 *
 * Uses React Query hooks for data fetching. Shared PACT compound
 * components for verdict badges and priority indicators.
 */

"use client";

import { useState, useMemo } from "react";
import DashboardShell from "../../components/layout/DashboardShell";
import StatusBadge from "../../components/ui/StatusBadge";

import { VerdictBadge, PriorityIndicator } from "@/components/pact";
import { useRequests, useRequestDetail } from "@/hooks";
import {
  Card,
  CardContent,
  Button,
  Skeleton,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
  Alert,
  AlertTitle,
  AlertDescription,
  Table,
  TableHeader,
  TableBody,
  TableHead,
  TableRow,
  TableCell,
  Badge,
} from "@/components/ui/shadcn";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface WorkRequest {
  id: string;
  title: string;
  objective_id: string;
  objective_title: string;
  status: string;
  priority: "low" | "medium" | "high" | "critical";
  assigned_to: string | null;
  governance_verdict: string | null;
  cost: number;
  created_at: string;
  updated_at: string;
}

interface RequestDetail extends WorkRequest {
  description: string;
  sessions: Array<{
    id: string;
    status: string;
    agent_id: string;
    started_at: string;
    ended_at: string | null;
    cost: number;
  }>;
  artifacts: Array<{
    id: string;
    type: string;
    name: string;
    created_at: string;
  }>;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const STATUS_OPTIONS = [
  { value: "all", label: "All Statuses" },
  { value: "pending", label: "Pending" },
  { value: "queued", label: "Queued" },
  { value: "assigned", label: "Assigned" },
  { value: "in_progress", label: "In Progress" },
  { value: "review", label: "Review" },
  { value: "completed", label: "Completed" },
  { value: "failed", label: "Failed" },
  { value: "cancelled", label: "Cancelled" },
] as const;

// ---------------------------------------------------------------------------
// Detail panel
// ---------------------------------------------------------------------------

function RequestDetailPanel({
  requestId,
  onClose,
}: {
  requestId: string;
  onClose: () => void;
}) {
  const { data: requestData, isLoading, error } = useRequestDetail(requestId);

  if (isLoading) {
    return (
      <Card>
        <CardContent className="p-6 space-y-3">
          <Skeleton className="h-5 w-1/3" />
          <Skeleton className="h-4 w-2/3" />
          <Skeleton className="h-4 w-1/2" />
        </CardContent>
      </Card>
    );
  }

  if (error || !requestData) {
    return (
      <Alert variant="destructive">
        <AlertTitle>Failed to load request</AlertTitle>
        <AlertDescription>
          {error instanceof Error ? error.message : "Unknown error"}
        </AlertDescription>
      </Alert>
    );
  }

  const request = requestData as unknown as RequestDetail;

  return (
    <Card>
      <CardContent className="p-6 space-y-5">
        <div className="flex items-start justify-between">
          <div>
            <h3 className="text-lg font-semibold text-foreground">
              {request.title}
            </h3>
            <p className="mt-1 text-sm text-muted-foreground">
              Objective: {request.objective_title}
            </p>
          </div>
          <Button variant="outline" size="sm" onClick={onClose}>
            Close
          </Button>
        </div>

        {request.description && (
          <p className="text-sm text-muted-foreground">{request.description}</p>
        )}

        <div className="flex flex-wrap gap-3">
          <StatusBadge value={request.status} size="sm" />
          <VerdictBadge level={request.governance_verdict} />
          <PriorityIndicator priority={request.priority} />
          {request.assigned_to && (
            <span className="text-sm text-muted-foreground">
              Assigned to:{" "}
              <span className="font-medium text-foreground">
                {request.assigned_to}
              </span>
            </span>
          )}
        </div>

        {/* Sessions */}
        <div>
          <h4 className="mb-2 text-sm font-semibold text-foreground">
            Sessions ({request.sessions?.length ?? 0})
          </h4>
          {!request.sessions || request.sessions.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No sessions recorded yet.
            </p>
          ) : (
            <div className="rounded-lg border border-border overflow-hidden">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Session</TableHead>
                    <TableHead>Agent</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Started</TableHead>
                    <TableHead className="text-right">Cost</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {request.sessions.map((session) => (
                    <TableRow key={session.id}>
                      <TableCell className="font-mono text-sm text-muted-foreground">
                        {session.id.slice(0, 8)}
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {session.agent_id}
                      </TableCell>
                      <TableCell>
                        <StatusBadge value={session.status} size="xs" />
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {new Date(session.started_at).toLocaleString()}
                      </TableCell>
                      <TableCell className="text-right text-sm text-foreground">
                        ${session.cost.toLocaleString()}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </div>

        {/* Artifacts */}
        <div>
          <h4 className="mb-2 text-sm font-semibold text-foreground">
            Artifacts ({request.artifacts?.length ?? 0})
          </h4>
          {!request.artifacts || request.artifacts.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No artifacts produced yet.
            </p>
          ) : (
            <div className="space-y-2">
              {request.artifacts.map((artifact) => (
                <div
                  key={artifact.id}
                  className="flex items-center justify-between rounded-md border border-border bg-muted/50 px-4 py-2"
                >
                  <div className="flex items-center gap-3">
                    <Badge variant="secondary" className="text-xs">
                      {artifact.type}
                    </Badge>
                    <span className="text-sm text-foreground">
                      {artifact.name}
                    </span>
                  </div>
                  <span className="text-xs text-muted-foreground">
                    {new Date(artifact.created_at).toLocaleDateString()}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function RequestsPage() {
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [objectiveFilter, setObjectiveFilter] = useState<string>("");
  const [selectedId, setSelectedId] = useState<string | null>(null);

  // Fetch requests via React Query with filters
  const filters: { status?: string; objective_id?: string } = {};
  if (statusFilter !== "all") filters.status = statusFilter;
  if (objectiveFilter) filters.objective_id = objectiveFilter;
  const hasFilters = Object.keys(filters).length > 0;

  const {
    data: requestsData,
    isLoading,
    error,
    refetch,
  } = useRequests(hasFilters ? filters : undefined);

  const requests: WorkRequest[] =
    (requestsData as unknown as { requests: WorkRequest[] })?.requests ?? [];

  // Unique objective IDs for filter dropdown
  const objectiveIds = useMemo(() => {
    const ids = new Set<string>();
    for (const req of requests) {
      if (req.objective_id) ids.add(req.objective_id);
    }
    return Array.from(ids);
  }, [requests]);

  // Client-side filtering (when filter not server-side)
  const filtered = useMemo(() => {
    let list = requests;
    if (statusFilter !== "all") {
      list = list.filter((r) => r.status === statusFilter);
    }
    if (objectiveFilter) {
      list = list.filter((r) => r.objective_id === objectiveFilter);
    }
    return list;
  }, [requests, statusFilter, objectiveFilter]);

  return (
    <DashboardShell
      activePath="/requests"
      title="Request Queue"
      breadcrumbs={[{ label: "Dashboard", href: "/" }, { label: "Requests" }]}
      actions={
        <Button
          variant="outline"
          size="sm"
          onClick={() => refetch()}
          disabled={isLoading}
        >
          Refresh
        </Button>
      }
    >
      <div className="space-y-6">
        <p className="text-sm text-muted-foreground">
          Governance-evaluated work requests in the execution queue. Each
          request carries a governance verdict determining its approval status
          and constraint boundaries.
        </p>

        {/* Filters */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2">
            <span className="text-sm text-muted-foreground">Status:</span>
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-[160px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {STATUS_OPTIONS.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {objectiveIds.length > 0 && (
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground">Objective:</span>
              <Select
                value={objectiveFilter}
                onValueChange={setObjectiveFilter}
              >
                <SelectTrigger className="w-[160px]">
                  <SelectValue placeholder="All Objectives" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="">All Objectives</SelectItem>
                  {objectiveIds.map((id) => (
                    <SelectItem key={id} value={id}>
                      {id.slice(0, 8)}...
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}
        </div>

        {/* Loading */}
        {isLoading && <div className="space-y-2">{Array.from({length:6}).map((_,i)=><Skeleton key={i} className="h-12 rounded" />)}</div>}

        {/* Error */}
        {error && (
          <Alert variant="destructive">
            <AlertTitle>Something went wrong</AlertTitle>
            <AlertDescription>
              {error instanceof Error
                ? error.message
                : "Failed to load requests"}
            </AlertDescription>
          </Alert>
        )}

        {/* Detail panel */}
        {selectedId && (
          <RequestDetailPanel
            requestId={selectedId}
            onClose={() => setSelectedId(null)}
          />
        )}

        {/* Table */}
        {!isLoading && !error && (
          <>
            {filtered.length > 0 ? (
              <div className="rounded-lg border border-border overflow-hidden bg-card">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Title</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Priority</TableHead>
                      <TableHead>Verdict</TableHead>
                      <TableHead>Assigned To</TableHead>
                      <TableHead className="text-right">Cost</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filtered.map((req) => (
                      <TableRow
                        key={req.id}
                        onClick={() => setSelectedId(req.id)}
                        className="cursor-pointer"
                      >
                        <TableCell>
                          <div className="text-sm font-medium text-foreground">
                            {req.title}
                          </div>
                          <div className="text-xs text-muted-foreground">
                            {req.objective_title}
                          </div>
                        </TableCell>
                        <TableCell>
                          <StatusBadge value={req.status} size="xs" />
                        </TableCell>
                        <TableCell>
                          <PriorityIndicator priority={req.priority} />
                        </TableCell>
                        <TableCell>
                          <VerdictBadge level={req.governance_verdict} />
                        </TableCell>
                        <TableCell className="text-sm text-muted-foreground">
                          {req.assigned_to ?? (
                            <span className="italic text-muted-foreground/60">
                              Unassigned
                            </span>
                          )}
                        </TableCell>
                        <TableCell className="text-right text-sm text-foreground">
                          ${req.cost.toLocaleString()}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            ) : (
              <Card>
                <CardContent className="p-8 text-center">
                  <p className="text-sm text-muted-foreground">
                    {requests.length === 0
                      ? "No requests in the queue."
                      : "No requests match the selected filters."}
                  </p>
                </CardContent>
              </Card>
            )}
          </>
        )}
      </div>
    </DashboardShell>
  );
}
