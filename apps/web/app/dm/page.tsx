// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * DM Team dashboard page.
 *
 * Shows the Decision-Making team overview: team-level summary stats,
 * agent cards with posture badges and quick stats, and a task
 * submission form with live status tracking.
 *
 * Data sources:
 *   GET /api/v1/dm/status -- team status with agents and summary stats
 *   POST /api/v1/dm/tasks -- submit a new task
 *   GET /api/v1/dm/tasks/{task_id} -- poll task status
 *
 * Fallback: If the DM status endpoint returns 404 (not yet provisioned),
 * the page falls back to loading DM team agents from the standard
 * teams/agents API.
 */

"use client";

import { useMemo } from "react";
import DashboardShell from "../../components/layout/DashboardShell";
import { Alert, AlertDescription } from "@/components/ui/shadcn/alert";
import { AlertCircle } from "lucide-react";
import DmSkeleton from "./elements/DmSkeleton";
import DmTeamSummary from "./elements/DmTeamSummary";
import DmAgentCards from "./elements/DmAgentCards";
import TaskSubmissionForm from "./elements/TaskSubmissionForm";
import { useDmStatus as useDmStatusHook } from "@/hooks";
import { ApiError } from "../../lib/api";
import type {
  DmStatus,
  DmAgentSummary,
  TrustPosture,
  AgentStatus,
} from "../../types/pact";

// ---------------------------------------------------------------------------
// DM Status Loader
// ---------------------------------------------------------------------------

/**
 * Wrapper that uses the shared React Query hook for DM status.
 */
function useDmStatusLocal(): {
  status: DmStatus | null;
  loading: boolean;
  error: string | null;
  refetch: () => void;
} {
  const { data, isLoading, error, refetch } = useDmStatusHook();
  return {
    status: (data as DmStatus | undefined) ?? null,
    loading: isLoading,
    error: error?.message ?? null,
    refetch,
  };
}

// ---------------------------------------------------------------------------
// Page Component
// ---------------------------------------------------------------------------

export default function DmPage() {
  const { status, loading, error, refetch } = useDmStatusLocal();

  // Memoize agents list for child components
  const agents = useMemo(() => status?.agents ?? [], [status]);

  return (
    <DashboardShell
      activePath="/dm"
      title="DM Team"
      breadcrumbs={[{ label: "Dashboard", href: "/" }, { label: "DM Team" }]}
      actions={
        <button
          onClick={refetch}
          disabled={loading}
          className="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 transition-colors"
        >
          Refresh
        </button>
      }
    >
      <div className="space-y-6">
        {/* Page description */}
        <p className="text-sm text-gray-600">
          The Decision-Making team coordinates AI agent operations under EATP
          trust governance. Each agent operates within its constraint envelope
          at a defined trust posture level. Submit tasks for the team to route
          and execute.
        </p>

        {/* Error state */}
        {error && (<Alert variant="destructive"><AlertCircle className="h-4 w-4" /><AlertDescription>{error}</AlertDescription></Alert>)}

        {/* Loading state */}
        {loading && <DmSkeleton />}

        {/* Dashboard content */}
        {!loading && !error && status && (
          <>
            {/* Team summary stats */}
            <DmTeamSummary status={status} />

            {/* Agent cards */}
            <div>
              <h2 className="mb-3 text-base font-semibold text-gray-900">
                Team Agents
              </h2>
              <DmAgentCards agents={agents} />
            </div>

            {/* Task submission form */}
            <TaskSubmissionForm agents={agents} />
          </>
        )}

        {/* Empty state: loaded but no status (both endpoints unavailable) */}
        {!loading && !error && !status && (
          <div className="rounded-lg border border-gray-200 bg-white p-8 text-center text-gray-500">
            The DM team has not been provisioned yet. Configure the team in the
            PACT backend to see agent status and submit tasks.
          </div>
        )}
      </div>
    </DashboardShell>
  );
}
