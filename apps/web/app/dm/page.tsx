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
import ErrorAlert from "../../components/ui/ErrorAlert";
import DmSkeleton from "./elements/DmSkeleton";
import DmTeamSummary from "./elements/DmTeamSummary";
import DmAgentCards from "./elements/DmAgentCards";
import TaskSubmissionForm from "./elements/TaskSubmissionForm";
import { useApi } from "../../lib/use-api";
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
 * Custom hook that loads DM team status.
 *
 * Tries the dedicated DM status endpoint first. If it returns 404
 * (endpoint not yet provisioned), falls back to loading agents from
 * the standard teams/agents API and constructing a synthetic DmStatus.
 */
function useDmStatus(): {
  status: DmStatus | null;
  loading: boolean;
  error: string | null;
  refetch: () => void;
} {
  // Try the dedicated DM status endpoint
  const {
    data: dmData,
    loading: dmLoading,
    error: dmError,
    refetch: dmRefetch,
  } = useApi(async (client) => {
    try {
      return await client.getDmStatus();
    } catch (err) {
      // If 404, the DM status endpoint is not provisioned yet.
      // Return a sentinel so we know to fall back.
      if (err instanceof ApiError && err.statusCode === 404) {
        return {
          status: "ok" as const,
          data: null,
          error: null,
        };
      }
      throw err;
    }
  }, []);

  // Determine if we need the fallback (dmData loaded but null = 404)
  const needsFallback = !dmLoading && dmData === null && dmError === null;

  // Fallback: load agents from the standard teams API
  const {
    data: fallbackData,
    loading: fallbackLoading,
    error: fallbackError,
    refetch: fallbackRefetch,
  } = useApi(
    async (client) => {
      if (!needsFallback) {
        // Skip fallback -- dedicated endpoint returned data or errored
        return { status: "ok" as const, data: null, error: null };
      }

      const agentsResp = await client.listAgents("dm-team");
      if (agentsResp.status === "ok" && agentsResp.data) {
        const agents: DmAgentSummary[] = agentsResp.data.agents.map(
          (a: Record<string, unknown>) => ({
            agent_id: a.agent_id as string,
            name: a.name as string,
            role: a.role as string,
            posture: a.posture as TrustPosture,
            status: a.status as AgentStatus,
            tasks_submitted: 0,
            tasks_completed: 0,
            tasks_held: 0,
            tasks_blocked: 0,
          }),
        );

        const synthetic: DmStatus = {
          team_id: "dm-team",
          agents,
          total_agents: agents.length,
        };

        return {
          status: "ok" as const,
          data: synthetic,
          error: null,
        };
      }

      return { status: "ok" as const, data: null, error: null };
    },
    [needsFallback],
  );

  // Merge results: prefer dedicated endpoint, then fallback
  const status = dmData ?? fallbackData ?? null;
  const loading = dmLoading || (needsFallback && fallbackLoading);
  const error = dmError ?? (needsFallback ? fallbackError : null);

  const refetch = () => {
    dmRefetch();
    if (needsFallback) {
      fallbackRefetch();
    }
  };

  return { status, loading, error, refetch };
}

// ---------------------------------------------------------------------------
// Page Component
// ---------------------------------------------------------------------------

export default function DmPage() {
  const { status, loading, error, refetch } = useDmStatus();

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
        {error && <ErrorAlert message={error} onRetry={refetch} />}

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
