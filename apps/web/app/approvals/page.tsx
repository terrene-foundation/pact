// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * Approvals page -- interactive queue of HELD items awaiting human approval.
 *
 * Displays all held actions as cards with approve/reject buttons.
 * Actions are sorted by urgency (critical first) then by submission time.
 * Uses React Query mutations for approve/reject API calls with automatic
 * cache invalidation.
 */

"use client";

import { useState, useCallback, useMemo } from "react";
import { CheckCircle, AlertCircle, RefreshCw } from "lucide-react";
import DashboardShell from "../../components/layout/DashboardShell";
import ApprovalCard from "../../components/approvals/ApprovalCard";
import {
  Card,
  CardContent,
  Skeleton,
  Alert,
  AlertTitle,
  AlertDescription,
  Badge,
  Button,
} from "@/components/ui/shadcn";
import { useHeldActions, useApproveAction, useRejectAction } from "@/hooks";
import { useAuth } from "../../lib/auth-context";

/** Urgency sort order -- lower number = higher priority (shown first). */
const URGENCY_ORDER: Record<string, number> = {
  critical: 0,
  high: 1,
  medium: 2,
  low: 3,
};

// ---------------------------------------------------------------------------
// Loading Skeleton
// ---------------------------------------------------------------------------

function ApprovalsSkeleton() {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {Array.from({ length: 3 }).map((_, i) => (
        <Card key={i}>
          <CardContent className="p-5 space-y-4">
            <div className="flex items-start justify-between">
              <div className="space-y-2 flex-1">
                <Skeleton className="h-4 w-3/4" />
                <Skeleton className="h-3 w-1/3" />
              </div>
              <Skeleton className="h-5 w-16 rounded-full" />
            </div>
            <div className="space-y-2">
              <Skeleton className="h-3 w-full" />
              <Skeleton className="h-3 w-2/3" />
            </div>
            <div className="flex gap-2 pt-2">
              <Skeleton className="h-8 w-20 rounded-md" />
              <Skeleton className="h-8 w-20 rounded-md" />
              <Skeleton className="h-8 w-24 rounded-md" />
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page Component
// ---------------------------------------------------------------------------

export default function ApprovalsPage() {
  const { user } = useAuth();
  const approverId = user?.name ?? "unknown-operator";

  // --- Data fetching via React Query ---
  const { data, isLoading, error, refetch } = useHeldActions();
  const approveMutation = useApproveAction();
  const rejectMutation = useRejectAction();

  const [resolvedIds, setResolvedIds] = useState<Set<string>>(new Set());

  const handleResolved = useCallback(
    (actionId: string, _decision: "approved" | "rejected") => {
      setResolvedIds((prev) => new Set(prev).add(actionId));
    },
    [],
  );

  const handleApprove = useCallback(
    async (agentId: string, actionId: string, reason?: string) => {
      await approveMutation.mutateAsync({
        agentId,
        actionId,
        approverId,
        reason,
      });
    },
    [approveMutation, approverId],
  );

  const handleReject = useCallback(
    async (agentId: string, actionId: string, reason?: string) => {
      await rejectMutation.mutateAsync({
        agentId,
        actionId,
        approverId,
        reason,
      });
    },
    [rejectMutation, approverId],
  );

  /** Sort pending actions by urgency (critical first), then by time (oldest first). */
  const pendingActions = useMemo(() => {
    const actions =
      data?.actions.filter((a) => !resolvedIds.has(a.action_id)) ?? [];
    return actions.sort((a, b) => {
      const urgencyA = URGENCY_ORDER[a.urgency] ?? 99;
      const urgencyB = URGENCY_ORDER[b.urgency] ?? 99;
      if (urgencyA !== urgencyB) return urgencyA - urgencyB;
      // Within the same urgency level, oldest first
      return (
        new Date(a.submitted_at).getTime() - new Date(b.submitted_at).getTime()
      );
    });
  }, [data, resolvedIds]);

  const resolvedCount = resolvedIds.size;
  const criticalCount = pendingActions.filter(
    (a) => a.urgency === "critical",
  ).length;

  return (
    <DashboardShell
      activePath="/approvals"
      title="Approval Queue"
      breadcrumbs={[{ label: "Dashboard", href: "/" }, { label: "Approvals" }]}
      actions={
        <Button
          variant="outline"
          size="sm"
          onClick={() => void refetch()}
          disabled={isLoading}
        >
          <RefreshCw className={`h-4 w-4 ${isLoading ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      }
    >
      <div className="space-y-6">
        <p className="text-sm text-muted-foreground">
          Actions that exceeded a soft constraint limit and require human
          approval. Review each request and approve or reject based on the
          action context and constraint boundaries.
        </p>

        {/* Summary bar */}
        {data && !isLoading && (
          <Card>
            <CardContent className="px-4 py-3">
              <div className="flex flex-wrap items-center gap-4">
                <div className="flex items-center gap-2">
                  <Badge
                    variant="secondary"
                    className="bg-orange-100 text-orange-700 dark:bg-orange-900 dark:text-orange-300 border-transparent"
                  >
                    {pendingActions.length}
                  </Badge>
                  <span className="text-sm text-foreground">Pending</span>
                </div>
                {criticalCount > 0 && (
                  <div className="flex items-center gap-2">
                    <Badge variant="destructive">{criticalCount}</Badge>
                    <span className="text-sm font-medium text-destructive">
                      Critical
                    </span>
                  </div>
                )}
                {resolvedCount > 0 && (
                  <div className="flex items-center gap-2">
                    <Badge
                      variant="secondary"
                      className="bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300 border-transparent"
                    >
                      {resolvedCount}
                    </Badge>
                    <span className="text-sm text-foreground">
                      Resolved this session
                    </span>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Loading */}
        {isLoading && <ApprovalsSkeleton />}

        {/* Error */}
        {error && (
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertTitle>Failed to load approval queue</AlertTitle>
            <AlertDescription className="flex items-center justify-between">
              <span>
                {error instanceof Error
                  ? error.message
                  : "An unexpected error occurred"}
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => void refetch()}
              >
                Retry
              </Button>
            </AlertDescription>
          </Alert>
        )}

        {/* Approval cards */}
        {data && (
          <>
            {pendingActions.length > 0 ? (
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {pendingActions.map((action) => (
                  <ApprovalCard
                    key={action.action_id}
                    item={action}
                    onResolved={handleResolved}
                    onApprove={handleApprove}
                    onReject={handleReject}
                  />
                ))}
              </div>
            ) : (
              <Card className="border-green-200 dark:border-green-800 bg-green-50 dark:bg-green-950">
                <CardContent className="p-8 text-center">
                  <CheckCircle className="mx-auto mb-3 h-10 w-10 text-green-500" />
                  <p className="text-sm font-medium text-green-800 dark:text-green-200">
                    All caught up
                  </p>
                  <p className="text-xs text-green-600 dark:text-green-400">
                    No actions are awaiting approval right now.
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
