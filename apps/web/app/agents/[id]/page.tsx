// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * Agent detail page -- shows agent info, current posture, capabilities,
 * posture change history, and governance actions (suspend, revoke, change posture).
 */

"use client";

import { use, useState, useCallback } from "react";
import DashboardShell from "../../../components/layout/DashboardShell";
import PostureBadge from "../../../components/agents/PostureBadge";
import PostureUpgradeWizard from "../../../components/agents/PostureUpgradeWizard";
import StatusBadge from "../../../components/ui/StatusBadge";
import ErrorAlert from "../../../components/ui/ErrorAlert";
import ConfirmationModal from "../../../components/ui/ConfirmationModal";
import { CardSkeleton } from "../../../components/ui/Skeleton";
import { useApi, getApiClient } from "../../../lib/use-api";
import { useAuth } from "../../../lib/auth-context";
import type { TrustPosture } from "../../../types/pact";

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

interface AgentDetailPageProps {
  params: Promise<{ id: string }>;
}

export default function AgentDetailPage({ params }: AgentDetailPageProps) {
  const { id } = use(params);
  const { user } = useAuth();
  const officerId = user?.name ?? "unknown-operator";

  const { data, loading, error, refetch } = useApi(
    (client) => client.getAgentDetail(id),
    [id],
  );

  // Governance action modal state
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
    async (reason: string) => {
      clearMessages();
      const client = getApiClient();
      const result = await client.suspendAgent(id, reason, officerId);
      if (result.status === "error") {
        throw new Error(result.error ?? "Failed to suspend agent");
      }
      setSuspendOpen(false);
      setActionSuccess("Agent has been suspended.");
      refetch();
    },
    [id, officerId, refetch, clearMessages],
  );

  const handleRevoke = useCallback(
    async (reason: string) => {
      clearMessages();
      const client = getApiClient();
      const result = await client.revokeAgent(id, reason, officerId);
      if (result.status === "error") {
        throw new Error(result.error ?? "Failed to revoke agent");
      }
      setRevokeOpen(false);
      setActionSuccess("Agent has been revoked. This action cannot be undone.");
      refetch();
    },
    [id, officerId, refetch, clearMessages],
  );

  const handleChangePosture = useCallback(
    async (reason: string) => {
      if (!selectedPosture) return;
      clearMessages();
      const client = getApiClient();
      const result = await client.changePosture(
        id,
        selectedPosture,
        reason,
        officerId,
      );
      if (result.status === "error") {
        throw new Error(result.error ?? "Failed to change posture");
      }
      setPostureOpen(false);
      setSelectedPosture(null);
      setActionSuccess(
        `Posture changed to ${POSTURE_LABELS[selectedPosture]}.`,
      );
      refetch();
    },
    [id, selectedPosture, officerId, refetch, clearMessages],
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
      // Determine the next posture level
      const currentIdx = ALL_POSTURES.indexOf(data.posture);
      if (currentIdx < 0 || currentIdx >= ALL_POSTURES.length - 1) return;
      const nextPosture = ALL_POSTURES[currentIdx + 1];

      const client = getApiClient();
      const fullReason = override ? `[GOVERNANCE OVERRIDE] ${reason}` : reason;
      const result = await client.changePosture(
        id,
        nextPosture,
        fullReason,
        officerId,
      );
      if (result.status === "error") {
        throw new Error(result.error ?? "Failed to upgrade posture");
      }
      setUpgradeWizardOpen(false);
      setActionSuccess(
        `Posture upgraded to ${POSTURE_LABELS[nextPosture]}${override ? " (governance override)" : ""}.`,
      );
      refetch();
    },
    [data, id, officerId, refetch, clearMessages],
  );

  /** Whether the agent might be eligible for an upgrade (not at max posture). */
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
        {loading && (
          <div className="space-y-6">
            <CardSkeleton />
            <CardSkeleton />
          </div>
        )}

        {/* Error */}
        {error && <ErrorAlert message={error} onRetry={refetch} />}

        {/* Action feedback */}
        {actionSuccess && (
          <div className="rounded-lg border border-green-200 bg-green-50 p-4">
            <div className="flex items-center justify-between">
              <p className="text-sm font-medium text-green-800">
                {actionSuccess}
              </p>
              <button
                onClick={clearMessages}
                className="text-sm text-green-600 hover:text-green-800"
              >
                Dismiss
              </button>
            </div>
          </div>
        )}

        {actionError && (
          <ErrorAlert
            message={actionError}
            onRetry={() => setActionError(null)}
          />
        )}

        {data && (
          <>
            {/* Agent overview card */}
            <div className="rounded-lg border border-gray-200 bg-white p-6">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <h2 className="text-lg font-semibold text-gray-900">
                    {data.name}
                  </h2>
                  <p className="text-sm text-gray-500">{data.role}</p>
                </div>
                <div className="flex items-center gap-2">
                  <StatusBadge value={data.status} size="md" />
                  <PostureBadge posture={data.posture} size="md" />
                </div>
              </div>

              <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <div>
                  <p className="text-xs text-gray-500">Agent ID</p>
                  <p className="font-mono text-sm text-gray-900">
                    {data.agent_id}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-gray-500">Team</p>
                  <p className="text-sm text-gray-900">{data.team_id}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-500">Created</p>
                  <p className="text-sm text-gray-900">
                    {formatDate(data.created_at)}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-gray-500">Last Active</p>
                  <p className="text-sm text-gray-900">
                    {formatDate(data.last_active_at)}
                  </p>
                </div>
              </div>

              {/* Envelope link */}
              {data.envelope_id && (
                <div className="mt-4 border-t border-gray-100 pt-4">
                  <p className="text-xs text-gray-500">Constraint Envelope</p>
                  <a
                    href={`/envelopes/${data.envelope_id}`}
                    className="text-sm font-medium text-blue-600 hover:text-blue-800"
                  >
                    {data.envelope_id}
                  </a>
                </div>
              )}
            </div>

            {/* Governance actions */}
            {!isRevoked && (
              <div className="rounded-lg border border-gray-200 bg-white p-6">
                <h3 className="mb-4 text-sm font-semibold text-gray-900">
                  Governance Actions
                </h3>

                <div className="space-y-4">
                  {/* Upgrade Posture (wizard) */}
                  {canShowUpgrade && (
                    <div>
                      <button
                        onClick={() => {
                          clearMessages();
                          setUpgradeWizardOpen(true);
                        }}
                        className="inline-flex items-center gap-2 rounded-md bg-care-primary px-4 py-2 text-sm font-medium text-white hover:bg-care-primary-dark transition-colors focus:outline-none focus:ring-2 focus:ring-care-primary focus:ring-offset-2"
                      >
                        <svg
                          className="h-4 w-4"
                          fill="none"
                          stroke="currentColor"
                          viewBox="0 0 24 24"
                          aria-hidden="true"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"
                          />
                        </svg>
                        Upgrade Posture
                      </button>
                      <p className="mt-1.5 text-xs text-gray-500">
                        Review evidence and approve a posture upgrade to the
                        next trust level.
                      </p>
                    </div>
                  )}

                  {/* Change Posture */}
                  {(isActive || isSuspended) && (
                    <div>
                      <p className="mb-2 text-xs text-gray-500">
                        Change Trust Posture
                      </p>
                      <div className="flex flex-wrap gap-2">
                        {ALL_POSTURES.filter((p) => p !== data.posture).map(
                          (posture) => (
                            <button
                              key={posture}
                              onClick={() => openPostureModal(posture)}
                              className="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50 transition-colors"
                            >
                              {POSTURE_LABELS[posture]}
                            </button>
                          ),
                        )}
                      </div>
                    </div>
                  )}

                  {/* Suspend / Revoke buttons */}
                  <div className="flex flex-wrap gap-3 border-t border-gray-100 pt-4">
                    {isActive && (
                      <button
                        onClick={() => {
                          clearMessages();
                          setSuspendOpen(true);
                        }}
                        className="rounded-md bg-orange-600 px-4 py-2 text-sm font-medium text-white hover:bg-orange-700 transition-colors"
                      >
                        Suspend Agent
                      </button>
                    )}
                    <button
                      onClick={() => {
                        clearMessages();
                        setRevokeOpen(true);
                      }}
                      className="rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 transition-colors"
                    >
                      Revoke Agent
                    </button>
                  </div>

                  {isSuspended && (
                    <p className="text-xs text-gray-500">
                      This agent is currently suspended. You can change its
                      posture or permanently revoke it.
                    </p>
                  )}
                </div>
              </div>
            )}

            {isRevoked && (
              <div className="rounded-lg border border-red-200 bg-red-50 p-6">
                <h3 className="mb-2 text-sm font-semibold text-red-800">
                  Agent Revoked
                </h3>
                <p className="text-sm text-red-700">
                  This agent has been permanently revoked and cannot be
                  reactivated. All trust credentials have been invalidated.
                </p>
              </div>
            )}

            {/* Capabilities */}
            <div className="rounded-lg border border-gray-200 bg-white p-6">
              <h3 className="mb-3 text-sm font-semibold text-gray-900">
                Capabilities
              </h3>
              {data.capabilities.length > 0 ? (
                <div className="flex flex-wrap gap-2">
                  {data.capabilities.map((cap) => (
                    <span
                      key={cap}
                      className="rounded-md border border-gray-200 bg-gray-50 px-2.5 py-1 text-xs font-medium text-gray-700"
                    >
                      {cap}
                    </span>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-gray-500">
                  No capabilities declared.
                </p>
              )}
            </div>

            {/* Posture history */}
            <div className="rounded-lg border border-gray-200 bg-white p-6">
              <h3 className="mb-4 text-sm font-semibold text-gray-900">
                Posture History
              </h3>
              {data.posture_history.length > 0 ? (
                <div className="space-y-4">
                  {data.posture_history.map((change, index) => (
                    <div
                      key={`${change.changed_at}-${index}`}
                      className="flex items-start gap-4 border-l-2 border-gray-200 pl-4"
                    >
                      <div className="flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <PostureBadge
                            posture={change.from_posture}
                            size="sm"
                          />
                          <svg
                            className="h-4 w-4 text-gray-400"
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                            aria-hidden="true"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth={2}
                              d="M14 5l7 7m0 0l-7 7m7-7H3"
                            />
                          </svg>
                          <PostureBadge posture={change.to_posture} size="sm" />
                        </div>
                        <p className="mt-1 text-sm text-gray-600">
                          {change.reason}
                        </p>
                        <p className="text-xs text-gray-400">
                          Changed by {change.changed_by} on{" "}
                          {formatDate(change.changed_at)}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-gray-500">
                  No posture changes recorded. The agent has maintained its
                  initial posture since creation.
                </p>
              )}
            </div>
          </>
        )}
      </div>

      {/* Suspend Modal */}
      <ConfirmationModal
        open={suspendOpen}
        onClose={() => setSuspendOpen(false)}
        onConfirm={handleSuspend}
        title="Suspend Agent"
        description="Suspending this agent will immediately halt all its operations. The agent can be reactivated later or permanently revoked. Please provide a reason for the suspension."
        confirmLabel="Suspend Agent"
        destructive
        inputRequired
        inputLabel="Suspension Reason"
        inputPlaceholder="Why is this agent being suspended?"
      />

      {/* Revoke Modal */}
      <ConfirmationModal
        open={revokeOpen}
        onClose={() => setRevokeOpen(false)}
        onConfirm={handleRevoke}
        title="Revoke Agent"
        description="This action is irreversible. Revoking this agent will permanently invalidate all its trust credentials, attestations, and delegations. The agent will never be able to operate again."
        confirmLabel="Permanently Revoke"
        destructive
        inputRequired
        inputLabel="Revocation Reason"
        inputPlaceholder="Why is this agent being permanently revoked?"
      />

      {/* Change Posture Modal */}
      <ConfirmationModal
        open={postureOpen}
        onClose={() => {
          setPostureOpen(false);
          setSelectedPosture(null);
        }}
        onConfirm={handleChangePosture}
        title={`Change Posture to ${selectedPosture ? POSTURE_LABELS[selectedPosture] : ""}`}
        description={`This will change the agent's trust posture from "${data ? POSTURE_LABELS[data.posture] : ""}" to "${selectedPosture ? POSTURE_LABELS[selectedPosture] : ""}". This affects what level of autonomy the agent has and what actions require human oversight.`}
        confirmLabel="Change Posture"
        inputRequired
        inputLabel="Reason for Posture Change"
        inputPlaceholder="Why is this posture change needed?"
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
