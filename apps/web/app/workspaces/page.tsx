// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * Workspaces page -- workspace cards with state, CO phase, and bridge
 * connections between workspace teams.
 */

"use client";

import DashboardShell from "../../components/layout/DashboardShell";
import WorkspaceCard from "../../components/workspaces/WorkspaceCard";
import BridgeConnections from "../../components/workspaces/BridgeConnections";
import ErrorAlert from "../../components/ui/ErrorAlert";
import { CardSkeleton } from "../../components/ui/Skeleton";
import { useApi } from "../../lib/use-api";

export default function WorkspacesPage() {
  const {
    data: workspacesData,
    loading: wsLoading,
    error: wsError,
    refetch: wsRefetch,
  } = useApi((client) => client.listWorkspaces(), []);

  const {
    data: bridgesData,
    loading: brLoading,
    error: brError,
    refetch: brRefetch,
  } = useApi((client) => client.listBridges(), []);

  const loading = wsLoading || brLoading;
  const error = wsError ?? brError;

  const handleRefetch = () => {
    wsRefetch();
    brRefetch();
  };

  return (
    <DashboardShell
      activePath="/workspaces"
      title="Workspaces"
      breadcrumbs={[
        { label: "Dashboard", href: "/" },
        { label: "Workspaces" },
      ]}
    >
      <div className="space-y-8">
        <p className="text-sm text-gray-600">
          Workspace-as-knowledge-base view showing all Foundation workspaces
          with their current lifecycle state and CO methodology phase. Each
          workspace is the knowledge base for an agent team.
        </p>

        {/* Error */}
        {error && <ErrorAlert message={error} onRetry={handleRefetch} />}

        {/* Workspace cards */}
        <div>
          <h2 className="mb-4 text-sm font-semibold text-gray-900">
            Active Workspaces
          </h2>

          {loading && (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {Array.from({ length: 6 }).map((_, i) => (
                <CardSkeleton key={i} />
              ))}
            </div>
          )}

          {workspacesData && (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {workspacesData.workspaces.map((ws) => (
                <WorkspaceCard key={ws.id} workspace={ws} />
              ))}
            </div>
          )}

          {workspacesData && workspacesData.workspaces.length === 0 && (
            <div className="rounded-lg border border-gray-200 bg-white p-8 text-center text-gray-500">
              No workspaces found. Workspaces are provisioned as part of
              organizational setup.
            </div>
          )}
        </div>

        {/* Bridge connections */}
        {!brLoading && bridgesData && (
          <BridgeConnections bridges={bridgesData.bridges} />
        )}
      </div>
    </DashboardShell>
  );
}
