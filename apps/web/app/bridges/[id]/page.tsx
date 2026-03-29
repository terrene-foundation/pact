// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * Bridge detail page -- shows full bridge information including permissions,
 * constraint intersection, approval status, and audit log.
 *
 * Uses React Query hooks for data fetching and mutations, Shadcn UI
 * components for layout, and AlertDialog for destructive confirmations.
 */

"use client";

import { useParams } from "next/navigation";
import { useState, useCallback } from "react";
import DashboardShell from "../../../components/layout/DashboardShell";
import {
  useBridgeDetail,
  useBridgeAudit,
  useApproveBridge,
  useSuspendBridge,
  useCloseBridge,
} from "@/hooks";
import { useAuth } from "../../../lib/auth-context";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Badge,
  Button,
  Skeleton,
  Alert,
  AlertTitle,
  AlertDescription,
  AlertDialog,
  AlertDialogContent,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogCancel,
  AlertDialogAction,
  Table,
  TableHeader,
  TableBody,
  TableHead,
  TableRow,
  TableCell,
  Separator,
  Input,
  Label,
} from "@/components/ui/shadcn";

/** Human-readable labels for bridge types. */
const BRIDGE_TYPE_LABELS: Record<string, string> = {
  standing: "Standing",
  scoped: "Scoped",
  ad_hoc: "Ad-Hoc",
};

/** Map status to badge variant. */
function statusVariant(
  status: string,
): "default" | "secondary" | "destructive" | "outline" {
  switch (status) {
    case "active":
      return "default";
    case "pending":
    case "negotiating":
      return "secondary";
    case "suspended":
    case "revoked":
      return "destructive";
    default:
      return "outline";
  }
}

/** AlertDialog requiring a reason input. */
function ReasonDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel,
  destructive,
  isPending,
  onConfirm,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: string;
  confirmLabel: string;
  destructive?: boolean;
  isPending: boolean;
  onConfirm: (reason: string) => void;
}) {
  const [reason, setReason] = useState("");

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{title}</AlertDialogTitle>
          <AlertDialogDescription>{description}</AlertDialogDescription>
        </AlertDialogHeader>
        <div className="space-y-2 py-2">
          <Label htmlFor="bridge-action-reason">Reason</Label>
          <Input
            id="bridge-action-reason"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Provide a reason for this action..."
          />
        </div>
        <AlertDialogFooter>
          <AlertDialogCancel onClick={() => setReason("")}>
            Cancel
          </AlertDialogCancel>
          <AlertDialogAction
            disabled={!reason.trim() || isPending}
            onClick={() => {
              onConfirm(reason.trim());
              setReason("");
            }}
            className={
              destructive
                ? "bg-destructive text-destructive-foreground hover:bg-destructive/90"
                : ""
            }
          >
            {isPending ? "Processing..." : confirmLabel}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

/** Bridge detail page skeleton. */
function BridgeDetailSkeleton() {
  return (
    <div className="space-y-6">
      <Card>
        <CardContent className="p-6 space-y-4">
          <div className="flex items-start justify-between">
            <div className="space-y-2">
              <Skeleton className="h-6 w-64" />
              <Skeleton className="h-4 w-48" />
            </div>
            <Skeleton className="h-6 w-16 rounded-full" />
          </div>
          <div className="grid gap-4 sm:grid-cols-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="space-y-1">
                <Skeleton className="h-3 w-16" />
                <Skeleton className="h-4 w-24" />
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
      <div className="grid gap-4 sm:grid-cols-2">
        <Card>
          <CardContent className="p-6 space-y-3">
            <Skeleton className="h-4 w-32" />
            <Skeleton className="h-8 w-full" />
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-6 space-y-3">
            <Skeleton className="h-4 w-32" />
            <Skeleton className="h-8 w-full" />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

export default function BridgeDetailPage() {
  const { user } = useAuth();
  const approverId = user?.name ?? "unknown-operator";
  const params = useParams();
  const bridgeId = params.id as string;

  const [actionError, setActionError] = useState<string | null>(null);
  const [suspendOpen, setSuspendOpen] = useState(false);
  const [closeOpen, setCloseOpen] = useState(false);

  const {
    data: bridgeData,
    isLoading: bridgeLoading,
    error: bridgeError,
    refetch: bridgeRefetch,
  } = useBridgeDetail(bridgeId);

  const {
    data: auditData,
    isLoading: auditLoading,
    error: auditError,
    refetch: auditRefetch,
  } = useBridgeAudit(bridgeId);

  const approveMutation = useApproveBridge();
  const suspendMutation = useSuspendBridge();
  const closeMutation = useCloseBridge();

  const handleRefetch = useCallback(() => {
    bridgeRefetch();
    auditRefetch();
    setActionError(null);
  }, [bridgeRefetch, auditRefetch]);

  const handleApprove = useCallback(
    (side: "source" | "target") => {
      setActionError(null);
      approveMutation.mutate(
        { bridgeId, side, approverId },
        {
          onSuccess: () => handleRefetch(),
          onError: (err) =>
            setActionError(
              err instanceof Error ? err.message : "Approval failed",
            ),
        },
      );
    },
    [bridgeId, approverId, approveMutation, handleRefetch],
  );

  const handleSuspend = useCallback(
    (reason: string) => {
      setActionError(null);
      suspendMutation.mutate(
        { bridgeId, reason },
        {
          onSuccess: () => {
            setSuspendOpen(false);
            handleRefetch();
          },
          onError: (err) =>
            setActionError(
              err instanceof Error ? err.message : "Suspension failed",
            ),
        },
      );
    },
    [bridgeId, suspendMutation, handleRefetch],
  );

  const handleClose = useCallback(
    (reason: string) => {
      setActionError(null);
      closeMutation.mutate(
        { bridgeId, reason },
        {
          onSuccess: () => {
            setCloseOpen(false);
            handleRefetch();
          },
          onError: (err) =>
            setActionError(
              err instanceof Error ? err.message : "Closure failed",
            ),
        },
      );
    },
    [bridgeId, closeMutation, handleRefetch],
  );

  const isLoading = bridgeLoading || auditLoading;
  const fetchError = bridgeError ?? auditError;

  return (
    <DashboardShell
      activePath="/bridges"
      title="Bridge Detail"
      breadcrumbs={[
        { label: "Dashboard", href: "/" },
        { label: "Bridges", href: "/bridges" },
        { label: bridgeData?.bridge_id ?? bridgeId },
      ]}
      actions={
        <Button variant="outline" onClick={handleRefetch} disabled={isLoading}>
          Refresh
        </Button>
      }
    >
      <div className="space-y-6">
        {fetchError && (
          <Alert variant="destructive">
            <AlertTitle>Failed to load bridge</AlertTitle>
            <AlertDescription className="flex items-center justify-between">
              <span>
                {fetchError instanceof Error
                  ? fetchError.message
                  : "Unknown error"}
              </span>
              <Button variant="outline" size="sm" onClick={handleRefetch}>
                Retry
              </Button>
            </AlertDescription>
          </Alert>
        )}

        {actionError && (
          <Alert variant="destructive">
            <AlertTitle>Action failed</AlertTitle>
            <AlertDescription>{actionError}</AlertDescription>
          </Alert>
        )}

        {isLoading && <BridgeDetailSkeleton />}

        {bridgeData && (
          <>
            {/* Header card */}
            <Card>
              <CardContent className="p-6">
                <div className="flex items-start justify-between">
                  <div>
                    <h2 className="text-lg font-semibold text-foreground">
                      {bridgeData.purpose}
                    </h2>
                    <p className="mt-1 text-sm text-muted-foreground font-mono">
                      {bridgeData.bridge_id}
                    </p>
                  </div>
                  <Badge variant={statusVariant(bridgeData.status)}>
                    {bridgeData.status}
                  </Badge>
                </div>

                <div className="mt-4 grid gap-4 sm:grid-cols-3">
                  <div>
                    <p className="text-xs text-muted-foreground uppercase tracking-wider">
                      Type
                    </p>
                    <p className="mt-1 text-sm font-medium text-foreground">
                      {BRIDGE_TYPE_LABELS[bridgeData.bridge_type] ??
                        bridgeData.bridge_type}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground uppercase tracking-wider">
                      Source Team
                    </p>
                    <p className="mt-1 text-sm font-medium text-foreground">
                      {bridgeData.source_team_id}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground uppercase tracking-wider">
                      Target Team
                    </p>
                    <p className="mt-1 text-sm font-medium text-foreground">
                      {bridgeData.target_team_id}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground uppercase tracking-wider">
                      Created By
                    </p>
                    <p className="mt-1 text-sm text-foreground">
                      {bridgeData.created_by || "Unknown"}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground uppercase tracking-wider">
                      Created At
                    </p>
                    <p className="mt-1 text-sm text-foreground">
                      {new Date(bridgeData.created_at).toLocaleString()}
                    </p>
                  </div>
                  {bridgeData.valid_until && (
                    <div>
                      <p className="text-xs text-muted-foreground uppercase tracking-wider">
                        Valid Until
                      </p>
                      <p className="mt-1 text-sm text-foreground">
                        {new Date(bridgeData.valid_until).toLocaleString()}
                      </p>
                    </div>
                  )}
                </div>

                {/* Replacement chain */}
                {(bridgeData.replaced_by || bridgeData.replacement_for) && (
                  <Alert className="mt-4">
                    <AlertTitle>Replacement Chain</AlertTitle>
                    <AlertDescription>
                      {bridgeData.replacement_for && (
                        <p className="text-xs">
                          Replaces:{" "}
                          <a
                            href={`/bridges/${bridgeData.replacement_for}`}
                            className="underline text-primary"
                          >
                            {bridgeData.replacement_for}
                          </a>
                        </p>
                      )}
                      {bridgeData.replaced_by && (
                        <p className="text-xs">
                          Replaced by:{" "}
                          <a
                            href={`/bridges/${bridgeData.replaced_by}`}
                            className="underline text-primary"
                          >
                            {bridgeData.replaced_by}
                          </a>
                        </p>
                      )}
                    </AlertDescription>
                  </Alert>
                )}
              </CardContent>
            </Card>

            {/* Approval status */}
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm">
                  Bilateral Approval Status
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid gap-4 sm:grid-cols-2">
                  <Card
                    className={
                      bridgeData.approved_by_source
                        ? "border-green-200 dark:border-green-800"
                        : "border-yellow-200 dark:border-yellow-800"
                    }
                  >
                    <CardContent className="p-4">
                      <div className="flex items-center justify-between">
                        <p className="text-sm font-medium text-foreground">
                          Source Approval
                        </p>
                        <Badge
                          variant={
                            bridgeData.approved_by_source
                              ? "default"
                              : "secondary"
                          }
                        >
                          {bridgeData.approved_by_source
                            ? "Approved"
                            : "Pending"}
                        </Badge>
                      </div>
                      <p className="mt-1 text-xs text-muted-foreground">
                        Team: {bridgeData.source_team_id}
                      </p>
                      {!bridgeData.approved_by_source &&
                        bridgeData.status === "pending" && (
                          <Button
                            size="sm"
                            className="mt-2"
                            onClick={() => handleApprove("source")}
                            disabled={approveMutation.isPending}
                          >
                            Approve Source
                          </Button>
                        )}
                    </CardContent>
                  </Card>
                  <Card
                    className={
                      bridgeData.approved_by_target
                        ? "border-green-200 dark:border-green-800"
                        : "border-yellow-200 dark:border-yellow-800"
                    }
                  >
                    <CardContent className="p-4">
                      <div className="flex items-center justify-between">
                        <p className="text-sm font-medium text-foreground">
                          Target Approval
                        </p>
                        <Badge
                          variant={
                            bridgeData.approved_by_target
                              ? "default"
                              : "secondary"
                          }
                        >
                          {bridgeData.approved_by_target
                            ? "Approved"
                            : "Pending"}
                        </Badge>
                      </div>
                      <p className="mt-1 text-xs text-muted-foreground">
                        Team: {bridgeData.target_team_id}
                      </p>
                      {!bridgeData.approved_by_target &&
                        bridgeData.status === "pending" && (
                          <Button
                            size="sm"
                            className="mt-2"
                            onClick={() => handleApprove("target")}
                            disabled={approveMutation.isPending}
                          >
                            Approve Target
                          </Button>
                        )}
                    </CardContent>
                  </Card>
                </div>
              </CardContent>
            </Card>

            {/* Permissions / Constraint Intersection */}
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm">
                  Permissions (Constraint Intersection)
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid gap-4 sm:grid-cols-3">
                  <div>
                    <p className="text-xs text-muted-foreground uppercase tracking-wider mb-2">
                      Read Paths
                    </p>
                    {bridgeData.permissions.read_paths.length > 0 ? (
                      <ul className="space-y-1">
                        {bridgeData.permissions.read_paths.map((path) => (
                          <li
                            key={path}
                            className="text-xs font-mono text-foreground bg-muted rounded px-2 py-1"
                          >
                            {path}
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="text-xs text-muted-foreground italic">
                        None
                      </p>
                    )}
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground uppercase tracking-wider mb-2">
                      Write Paths
                    </p>
                    {bridgeData.permissions.write_paths.length > 0 ? (
                      <ul className="space-y-1">
                        {bridgeData.permissions.write_paths.map((path) => (
                          <li
                            key={path}
                            className="text-xs font-mono text-foreground bg-muted rounded px-2 py-1"
                          >
                            {path}
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="text-xs text-muted-foreground italic">
                        None
                      </p>
                    )}
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground uppercase tracking-wider mb-2">
                      Message Types
                    </p>
                    {bridgeData.permissions.message_types.length > 0 ? (
                      <ul className="space-y-1">
                        {bridgeData.permissions.message_types.map((mt) => (
                          <li
                            key={mt}
                            className="text-xs font-mono text-foreground bg-muted rounded px-2 py-1"
                          >
                            {mt}
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="text-xs text-muted-foreground italic">
                        None
                      </p>
                    )}
                  </div>
                </div>
                {bridgeData.permissions.requires_attribution && (
                  <Badge variant="secondary" className="mt-3">
                    Requires attribution
                  </Badge>
                )}
                {bridgeData.one_time_use && (
                  <Badge variant="outline" className="mt-2 ml-2">
                    One-time use{" "}
                    {bridgeData.used ? "(consumed)" : "(available)"}
                  </Badge>
                )}
              </CardContent>
            </Card>

            {/* Actions */}
            {(bridgeData.status === "active" ||
              bridgeData.status === "pending") && (
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm">Actions</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="flex gap-3">
                    {bridgeData.status === "active" && (
                      <>
                        <Button
                          variant="secondary"
                          onClick={() => setSuspendOpen(true)}
                          disabled={suspendMutation.isPending}
                        >
                          Suspend Bridge
                        </Button>
                        <Button
                          variant="outline"
                          onClick={() => setCloseOpen(true)}
                          disabled={closeMutation.isPending}
                        >
                          Close Bridge
                        </Button>
                      </>
                    )}
                    {bridgeData.status === "pending" && (
                      <Button
                        variant="outline"
                        onClick={() => setCloseOpen(true)}
                        disabled={closeMutation.isPending}
                      >
                        Close Bridge
                      </Button>
                    )}
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Audit log */}
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm">
                  Audit Log ({auditData?.total ?? 0} entries)
                </CardTitle>
              </CardHeader>
              <CardContent>
                {auditData && auditData.entries.length > 0 ? (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Timestamp</TableHead>
                        <TableHead>Agent</TableHead>
                        <TableHead>Path</TableHead>
                        <TableHead>Access Type</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {auditData.entries.map((entry, idx) => (
                        <TableRow key={idx}>
                          <TableCell className="text-xs">
                            {new Date(entry.timestamp).toLocaleString()}
                          </TableCell>
                          <TableCell className="text-xs font-mono">
                            {entry.agent_id}
                          </TableCell>
                          <TableCell className="text-xs font-mono">
                            {entry.path}
                          </TableCell>
                          <TableCell className="text-xs">
                            {entry.access_type}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                ) : (
                  <p className="text-xs text-muted-foreground italic">
                    No access log entries recorded yet.
                  </p>
                )}
              </CardContent>
            </Card>
          </>
        )}
      </div>

      {/* Suspend Bridge Dialog */}
      <ReasonDialog
        open={suspendOpen}
        onOpenChange={setSuspendOpen}
        title="Suspend Bridge"
        description="Suspending this bridge will immediately halt all cross-team data access through it. The bridge can be reactivated later."
        confirmLabel="Suspend Bridge"
        destructive
        isPending={suspendMutation.isPending}
        onConfirm={handleSuspend}
      />

      {/* Close Bridge Dialog */}
      <ReasonDialog
        open={closeOpen}
        onOpenChange={setCloseOpen}
        title="Close Bridge"
        description="Closing this bridge will permanently end the cross-team connection. A new bridge will need to be created if teams need to collaborate again."
        confirmLabel="Close Bridge"
        isPending={closeMutation.isPending}
        onConfirm={handleClose}
      />
    </DashboardShell>
  );
}
