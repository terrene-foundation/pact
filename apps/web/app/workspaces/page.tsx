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
import { Alert, AlertDescription } from "@/components/ui/shadcn/alert";
import { Skeleton } from "@/components/ui/shadcn/skeleton";
import { useWorkspaces, useBridges } from "@/hooks";
import { AlertCircle } from "lucide-react";

export default function WorkspacesPage() {
  const {
    data: workspacesData,
    isLoading: wsLoading,
    error: wsError,
    refetch: wsRefetch,
  } = useWorkspaces();

  const {
    data: bridgesData,
    isLoading: brLoading,
    error: brError,
    refetch: brRefetch,
  } = useBridges();

  const loading = wsLoading || brLoading;
  const error = wsError?.message ?? brError?.message ?? null;

  const handleRefetch = () => {
    wsRefetch();
    brRefetch();
  };

  return (
    <DashboardShell
      activePath="/workspaces"
      title="Workspaces"
      breadcrumbs={[{ label: "Dashboard", href: "/" }, { label: "Workspaces" }]}
    >
      <div className="space-y-8">
        <p className="text-sm text-gray-600">
          Workspace-as-knowledge-base view showing all Foundation workspaces
          with their current lifecycle state and CO methodology phase. Each
          workspace is the knowledge base for an agent team.
        </p>

        {/* Error */}
        {error && (<Alert variant="destructive"><AlertCircle className="h-4 w-4" /><AlertDescription>{error}</AlertDescription></Alert>)}

        {/* Workspace cards */}
        <div>
          <h2 className="mb-4 text-sm font-semibold text-gray-900">
            Active Workspaces
          </h2>

          {loading && (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {Array.from({ length: 6 }).map((_, i) => (
                <Skeleton key={i} className="h-32 rounded-lg" />
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
