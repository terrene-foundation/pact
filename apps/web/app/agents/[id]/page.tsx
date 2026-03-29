// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * Agent detail page -- shows agent info, current posture, capabilities,
 * posture change history, and governance actions (suspend, revoke, change posture).
 *
 * Uses React Query hooks for data fetching and mutations, Shadcn UI components
 * for layout, and AlertDialog for destructive action confirmations.
 */

"use client";

import { use, useState, useCallback } from "react";
import DashboardShell from "../../../components/layout/DashboardShell";
import PostureBadge from "../../../components/agents/PostureBadge";
import PostureUpgradeWizard from "../../../components/agents/PostureUpgradeWizard";
import {
  useAgentDetail,
  useSuspendAgent,
  useRevokeAgent,
  useChangePosture,
} from "@/hooks";
import { useAuth } from "../../../lib/auth-context";
import type { TrustPosture } from "../../../types/pact";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Badge,
  Button,
  Skeleton,
  Tabs,
  TabsList,
  TabsTrigger,
  TabsContent,
  Alert,
  AlertTitle,
  AlertDescription,
  AlertDialog,
  AlertDialogTrigger,
  AlertDialogContent,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogCancel,
  AlertDialogAction,
  Input,
  Label,
  Separator,
} from "@/components/ui/shadcn";

/** All trust postures in ascending autonomy order. */
const ALL_POSTURES: TrustPosture[] = [
  "pseudo_agent",
  "supervised",
  "shared_planning",
  "continuous_insight",
  "delegated",
];

/** Human-readable posture labels. */
const POSTURE_LABELS: Record<TrustPosture, string> = {
  pseudo_agent: "Pseudo Agent",
  supervised: "Supervised",
  shared_planning: "Shared Planning",
  continuous_insight: "Continuous Insight",
  delegated: "Delegated",
};

/** Format an ISO timestamp to a readable string. */
function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

/** Skeleton for the detail page. */
function AgentDetailSkeleton() {
  return (
    <div className="space-y-6">
      <Card>
        <CardContent className="p-6 space-y-4">
          <div className="flex items-start justify-between">
            <div className="space-y-2">
              <Skeleton className="h-6 w-48" />
              <Skeleton className="h-4 w-32" />
            </div>
            <div className="flex gap-2">
              <Skeleton className="h-6 w-16 rounded-full" />
              <Skeleton className="h-6 w-24 rounded-full" />
            </div>
          </div>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="space-y-1">
                <Skeleton className="h-3 w-16" />
                <Skeleton className="h-4 w-24" />
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
      <Card>
        <CardContent className="p-6 space-y-3">
          <Skeleton className="h-5 w-40" />
          <div className="flex gap-2">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-8 w-20 rounded-md" />
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

/** AlertDialog wrapper for destructive actions requiring a reason. */
function ReasonAlertDialog({
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
          <Label htmlFor="action-reason">Reason</Label>
          <Input
            id="action-reason"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Provide a reason for this action..."
          />
        </div>
        <AlertDialogFooter>
          <AlertDialogCancel
            onClick={() => {
              setReason("");
            }}
          >
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

interface AgentDetailPageProps {
  params: Promise<{ id: string }>;
}

export default function AgentDetailPage({ params }: AgentDetailPageProps) {
  const { id } = use(params);
  const { user } = useAuth();
  const officerId = user?.name ?? "unknown-operator";

  const { data, isLoading, error, refetch } = useAgentDetail(id);
  const suspendMutation = useSuspendAgent();
  const revokeMutation = useRevokeAgent();
  const changePostureMutation = useChangePosture();

  // Dialog state
  const [suspendOpen, setSuspendOpen] = useState(false);
  const [revokeOpen, setRevokeOpen] = useState(false);
  const [postureOpen, setPostureOpen] = useState(false);
  const [upgradeWizardOpen, setUpgradeWizardOpen] = useState(false);
  const [selectedPosture, setSelectedPosture] = useState<TrustPosture | null>(
    null,
  );
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const clearMessages = useCallback(() => {
    setActionSuccess(null);
    setActionError(null);
  }, []);

  const handleSuspend = useCallback(
    (reason: string) => {
      clearMessages();
      suspendMutation.mutate(
        { agentId: id, reason, suspendedBy: officerId },
        {
          onSuccess: () => {
            setSuspendOpen(false);
            setActionSuccess("Agent has been suspended.");
          },
          onError: (err) => {
            setActionError(
              err instanceof Error ? err.message : "Failed to suspend agent",
            );
          },
        },
      );
    },
    [id, officerId, suspendMutation, clearMessages],
  );

  const handleRevoke = useCallback(
    (reason: string) => {
      clearMessages();
      revokeMutation.mutate(
        { agentId: id, reason, revokedBy: officerId },
        {
          onSuccess: () => {
            setRevokeOpen(false);
            setActionSuccess(
              "Agent has been revoked. This action cannot be undone.",
            );
          },
          onError: (err) => {
            setActionError(
              err instanceof Error ? err.message : "Failed to revoke agent",
            );
          },
        },
      );
    },
    [id, officerId, revokeMutation, clearMessages],
  );

  const handleChangePosture = useCallback(
    (reason: string) => {
      if (!selectedPosture) return;
      clearMessages();
      changePostureMutation.mutate(
        {
          agentId: id,
          newPosture: selectedPosture,
          reason,
          changedBy: officerId,
        },
        {
          onSuccess: () => {
            setPostureOpen(false);
            setActionSuccess(
              `Posture changed to ${POSTURE_LABELS[selectedPosture]}.`,
            );
            setSelectedPosture(null);
          },
          onError: (err) => {
            setActionError(
              err instanceof Error ? err.message : "Failed to change posture",
            );
          },
        },
      );
    },
    [id, selectedPosture, officerId, changePostureMutation, clearMessages],
  );

  const openPostureModal = useCallback(
    (posture: TrustPosture) => {
      clearMessages();
      setSelectedPosture(posture);
      setPostureOpen(true);
    },
    [clearMessages],
  );

  const handleUpgradeApprove = useCallback(
    async (reason: string, override: boolean) => {
      if (!data) return;
      clearMessages();
      const currentIdx = ALL_POSTURES.indexOf(data.posture);
      if (currentIdx < 0 || currentIdx >= ALL_POSTURES.length - 1) return;
      const nextPosture = ALL_POSTURES[currentIdx + 1];

      const fullReason = override ? `[GOVERNANCE OVERRIDE] ${reason}` : reason;
      changePostureMutation.mutate(
        {
          agentId: id,
          newPosture: nextPosture,
          reason: fullReason,
          changedBy: officerId,
        },
        {
          onSuccess: () => {
            setUpgradeWizardOpen(false);
            setActionSuccess(
              `Posture upgraded to ${POSTURE_LABELS[nextPosture]}${override ? " (governance override)" : ""}.`,
            );
          },
          onError: (err) => {
            setActionError(
              err instanceof Error ? err.message : "Failed to upgrade posture",
            );
          },
        },
      );
    },
    [data, id, officerId, changePostureMutation, clearMessages],
  );

  const canShowUpgrade =
    data?.status === "active" &&
    ALL_POSTURES.indexOf(data.posture) < ALL_POSTURES.length - 1;

  const isActive = data?.status === "active";
  const isSuspended = data?.status === "suspended";
  const isRevoked = data?.status === "revoked";

  return (
    <DashboardShell
      activePath="/agents"
      title={data?.name ?? `Agent ${id}`}
      breadcrumbs={[
        { label: "Dashboard", href: "/" },
        { label: "Agents", href: "/agents" },
        { label: data?.name ?? id },
      ]}
    >
      <div className="space-y-6">
        {/* Loading */}
        {isLoading && <AgentDetailSkeleton />}

        {/* Error */}
        {error && (
          <Alert variant="destructive">
            <AlertTitle>Failed to load agent</AlertTitle>
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

        {/* Action feedback */}
        {actionSuccess && (
          <Alert>
            <AlertTitle>Success</AlertTitle>
            <AlertDescription className="flex items-center justify-between">
              <span>{actionSuccess}</span>
              <Button variant="ghost" size="sm" onClick={clearMessages}>
                Dismiss
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

        {data && (
          <Tabs defaultValue="overview">
            <TabsList>
              <TabsTrigger value="overview">Overview</TabsTrigger>
              <TabsTrigger value="governance">Governance</TabsTrigger>
              <TabsTrigger value="history">History</TabsTrigger>
            </TabsList>

            {/* Overview tab */}
            <TabsContent value="overview" className="space-y-6">
              {/* Agent overview card */}
              <Card>
                <CardContent className="p-6">
                  <div className="flex flex-wrap items-start justify-between gap-4">
                    <div>
                      <h2 className="text-lg font-semibold text-foreground">
                        {data.name}
                      </h2>
                      <p className="text-sm text-muted-foreground">
                        {data.role}
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge
                        variant={
                          data.status === "active"
                            ? "default"
                            : data.status === "revoked"
                              ? "destructive"
                              : "secondary"
                        }
                      >
                        {data.status}
                      </Badge>
                      <PostureBadge posture={data.posture} size="md" />
                    </div>
                  </div>

                  <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                    <div>
                      <p className="text-xs text-muted-foreground">Agent ID</p>
                      <p className="font-mono text-sm text-foreground">
                        {data.agent_id}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground">Team</p>
                      <p className="text-sm text-foreground">{data.team_id}</p>
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground">Created</p>
                      <p className="text-sm text-foreground">
                        {formatDate(data.created_at)}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground">
                        Last Active
                      </p>
                      <p className="text-sm text-foreground">
                        {formatDate(data.last_active_at)}
                      </p>
                    </div>
                  </div>

                  {data.envelope_id && (
                    <>
                      <Separator className="my-4" />
                      <div>
                        <p className="text-xs text-muted-foreground">
                          Constraint Envelope
                        </p>
                        <a
                          href={`/envelopes/${data.envelope_id}`}
                          className="text-sm font-medium text-primary hover:underline"
                        >
                          {data.envelope_id}
                        </a>
                      </div>
                    </>
                  )}
                </CardContent>
              </Card>

              {/* Capabilities */}
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm">Capabilities</CardTitle>
                </CardHeader>
                <CardContent>
                  {data.capabilities.length > 0 ? (
                    <div className="flex flex-wrap gap-2">
                      {data.capabilities.map((cap) => (
                        <Badge key={cap} variant="outline">
                          {cap}
                        </Badge>
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm text-muted-foreground">
                      No capabilities declared.
                    </p>
                  )}
                </CardContent>
              </Card>

              {isRevoked && (
                <Alert variant="destructive">
                  <AlertTitle>Agent Revoked</AlertTitle>
                  <AlertDescription>
                    This agent has been permanently revoked and cannot be
                    reactivated. All trust credentials have been invalidated.
                  </AlertDescription>
                </Alert>
              )}
            </TabsContent>

            {/* Governance tab */}
            <TabsContent value="governance" className="space-y-6">
              {isRevoked ? (
                <Alert variant="destructive">
                  <AlertTitle>Agent Revoked</AlertTitle>
                  <AlertDescription>
                    This agent has been permanently revoked. No governance
                    actions are available.
                  </AlertDescription>
                </Alert>
              ) : (
                <Card>
                  <CardHeader className="pb-3">
                    <CardTitle className="text-sm">
                      Governance Actions
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    {/* Upgrade Posture */}
                    {canShowUpgrade && (
                      <div>
                        <Button
                          onClick={() => {
                            clearMessages();
                            setUpgradeWizardOpen(true);
                          }}
                        >
                          Upgrade Posture
                        </Button>
                        <p className="mt-1.5 text-xs text-muted-foreground">
                          Review evidence and approve a posture upgrade to the
                          next trust level.
                        </p>
                      </div>
                    )}

                    {/* Change Posture */}
                    {(isActive || isSuspended) && (
                      <div>
                        <p className="mb-2 text-xs text-muted-foreground">
                          Change Trust Posture
                        </p>
                        <div className="flex flex-wrap gap-2">
                          {ALL_POSTURES.filter((p) => p !== data.posture).map(
                            (posture) => (
                              <Button
                                key={posture}
                                variant="outline"
                                size="sm"
                                onClick={() => openPostureModal(posture)}
                              >
                                {POSTURE_LABELS[posture]}
                              </Button>
                            ),
                          )}
                        </div>
                      </div>
                    )}

                    <Separator />

                    {/* Suspend / Revoke buttons */}
                    <div className="flex flex-wrap gap-3">
                      {isActive && (
                        <AlertDialog
                          open={suspendOpen}
                          onOpenChange={setSuspendOpen}
                        >
                          <AlertDialogTrigger asChild>
                            <Button
                              variant="secondary"
                              onClick={() => {
                                clearMessages();
                                setSuspendOpen(true);
                              }}
                            >
                              Suspend Agent
                            </Button>
                          </AlertDialogTrigger>
                        </AlertDialog>
                      )}
                      <AlertDialog
                        open={revokeOpen}
                        onOpenChange={setRevokeOpen}
                      >
                        <AlertDialogTrigger asChild>
                          <Button
                            variant="destructive"
                            onClick={() => {
                              clearMessages();
                              setRevokeOpen(true);
                            }}
                          >
                            Revoke Agent
                          </Button>
                        </AlertDialogTrigger>
                      </AlertDialog>
                    </div>

                    {isSuspended && (
                      <p className="text-xs text-muted-foreground">
                        This agent is currently suspended. You can change its
                        posture or permanently revoke it.
                      </p>
                    )}
                  </CardContent>
                </Card>
              )}
            </TabsContent>

            {/* History tab */}
            <TabsContent value="history" className="space-y-6">
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm">Posture History</CardTitle>
                </CardHeader>
                <CardContent>
                  {data.posture_history.length > 0 ? (
                    <div className="space-y-4">
                      {data.posture_history.map((change, index) => (
                        <div
                          key={`${change.changed_at}-${index}`}
                          className="flex items-start gap-4 border-l-2 border-border pl-4"
                        >
                          <div className="flex-1">
                            <div className="flex flex-wrap items-center gap-2">
                              <PostureBadge
                                posture={change.from_posture}
                                size="sm"
                              />
                              <span className="text-muted-foreground">
                                &rarr;
                              </span>
                              <PostureBadge
                                posture={change.to_posture}
                                size="sm"
                              />
                            </div>
                            <p className="mt-1 text-sm text-muted-foreground">
                              {change.reason}
                            </p>
                            <p className="text-xs text-muted-foreground/70">
                              Changed by {change.changed_by} on{" "}
                              {formatDate(change.changed_at)}
                            </p>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm text-muted-foreground">
                      No posture changes recorded. The agent has maintained its
                      initial posture since creation.
                    </p>
                  )}
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        )}
      </div>

      {/* Suspend Dialog */}
      <ReasonAlertDialog
        open={suspendOpen}
        onOpenChange={setSuspendOpen}
        title="Suspend Agent"
        description="Suspending this agent will immediately halt all its operations. The agent can be reactivated later or permanently revoked."
        confirmLabel="Suspend Agent"
        destructive
        isPending={suspendMutation.isPending}
        onConfirm={handleSuspend}
      />

      {/* Revoke Dialog */}
      <ReasonAlertDialog
        open={revokeOpen}
        onOpenChange={setRevokeOpen}
        title="Revoke Agent"
        description="This action is irreversible. Revoking this agent will permanently invalidate all its trust credentials, attestations, and delegations."
        confirmLabel="Permanently Revoke"
        destructive
        isPending={revokeMutation.isPending}
        onConfirm={handleRevoke}
      />

      {/* Change Posture Dialog */}
      <ReasonAlertDialog
        open={postureOpen}
        onOpenChange={(open) => {
          setPostureOpen(open);
          if (!open) setSelectedPosture(null);
        }}
        title={`Change Posture to ${selectedPosture ? POSTURE_LABELS[selectedPosture] : ""}`}
        description={`This will change the agent's trust posture from "${data ? POSTURE_LABELS[data.posture] : ""}" to "${selectedPosture ? POSTURE_LABELS[selectedPosture] : ""}". This affects the level of autonomy the agent has.`}
        confirmLabel="Change Posture"
        isPending={changePostureMutation.isPending}
        onConfirm={handleChangePosture}
      />

      {/* Posture Upgrade Wizard */}
      {data && (
        <PostureUpgradeWizard
          open={upgradeWizardOpen}
          onClose={() => setUpgradeWizardOpen(false)}
          agent={data}
          onApprove={handleUpgradeApprove}
        />
      )}
    </DashboardShell>
  );
}
