// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * Agents page -- overview cards showing all agents from all teams.
 *
 * Fetches teams first, then agents for each team, rendering agent cards
 * with status, posture, and team information.
 */

"use client";

import { useState, useEffect } from "react";
import DashboardShell from "../../components/layout/DashboardShell";
import PostureBadge from "../../components/agents/PostureBadge";
import StatusBadge from "../../components/ui/StatusBadge";
import ErrorAlert from "../../components/ui/ErrorAlert";
import { CardSkeleton } from "../../components/ui/Skeleton";
import { getApiClient } from "../../lib/use-api";
import type { TrustPosture, AgentStatus } from "../../types/pact";

/** Agent entry combined with its team. */
interface AgentEntry {
  agent_id: string;
  name: string;
  role: string;
  posture: TrustPosture;
  status: AgentStatus;
  team_id: string;
}

export default function AgentsPage() {
  const [agents, setAgents] = useState<AgentEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchAgents = () => {
    setLoading(true);
    setError(null);

    const client = getApiClient();

    client
      .listTeams()
      .then(async (teamsResponse) => {
        if (teamsResponse.status === "error" || !teamsResponse.data) {
          setError(teamsResponse.error ?? "Failed to load teams");
          setLoading(false);
          return;
        }

        const allAgents: AgentEntry[] = [];

        for (const teamId of teamsResponse.data.teams) {
          const agentsResponse = await client.listAgents(teamId);
          if (agentsResponse.status === "ok" && agentsResponse.data) {
            for (const agent of agentsResponse.data.agents) {
              allAgents.push({
                agent_id: agent.agent_id,
                name: agent.name,
                role: agent.role,
                posture: agent.posture as TrustPosture,
                status: agent.status as AgentStatus,
                team_id: teamId,
              });
            }
          }
        }

        setAgents(allAgents);
        setLoading(false);
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : "Failed to load agents");
        setLoading(false);
      });
  };

  useEffect(() => {
    fetchAgents();
  }, []);

  /** Count agents by status for the summary. */
  const statusCounts = agents.reduce<Record<string, number>>((acc, a) => {
    acc[a.status] = (acc[a.status] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <DashboardShell
      activePath="/agents"
      title="Agents"
      breadcrumbs={[{ label: "Dashboard", href: "/" }, { label: "Agents" }]}
    >
      <div className="space-y-6">
        <p className="text-sm text-gray-600">
          All AI agents operating under EATP trust governance. Each agent
          operates within a constraint envelope and at a defined trust posture
          level.
        </p>

        {/* Summary stats */}
        {!loading && agents.length > 0 && (
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <div className="rounded-lg border border-gray-200 bg-white p-4 text-center">
              <p className="text-2xl font-bold text-gray-900">
                {agents.length}
              </p>
              <p className="text-xs text-gray-500">Total Agents</p>
            </div>
            <div className="rounded-lg border border-green-200 bg-green-50 p-4 text-center">
              <p className="text-2xl font-bold text-green-700">
                {statusCounts["active"] ?? 0}
              </p>
              <p className="text-xs text-green-600">Active</p>
            </div>
            <div className="rounded-lg border border-yellow-200 bg-yellow-50 p-4 text-center">
              <p className="text-2xl font-bold text-yellow-700">
                {statusCounts["suspended"] ?? 0}
              </p>
              <p className="text-xs text-yellow-600">Suspended</p>
            </div>
            <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-center">
              <p className="text-2xl font-bold text-red-700">
                {statusCounts["revoked"] ?? 0}
              </p>
              <p className="text-xs text-red-600">Revoked</p>
            </div>
          </div>
        )}

        {/* Loading state */}
        {loading && (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <CardSkeleton key={i} />
            ))}
          </div>
        )}

        {/* Error state */}
        {error && <ErrorAlert message={error} onRetry={fetchAgents} />}

        {/* Agent cards */}
        {!loading && !error && (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {agents.map((agent) => (
              <a
                key={agent.agent_id}
                href={`/agents/${agent.agent_id}`}
                className="group rounded-lg border border-gray-200 bg-white p-5 transition-shadow hover:shadow-md"
              >
                <div className="mb-3 flex items-start justify-between">
                  <div className="min-w-0 flex-1">
                    <h3 className="text-sm font-semibold text-gray-900 group-hover:text-blue-600 truncate">
                      {agent.name}
                    </h3>
                    <p className="text-xs text-gray-500">{agent.role}</p>
                  </div>
                  <StatusBadge value={agent.status} size="xs" />
                </div>

                <div className="flex items-center justify-between">
                  <PostureBadge posture={agent.posture} size="sm" />
                  <span className="text-xs text-gray-400">
                    Team: {agent.team_id}
                  </span>
                </div>
              </a>
            ))}
          </div>
        )}

        {!loading && !error && agents.length === 0 && (
          <div className="rounded-lg border border-gray-200 bg-white p-8 text-center text-gray-500">
            No agents found. Teams may not have been provisioned yet.
          </div>
        )}
      </div>
    </DashboardShell>
  );
}
