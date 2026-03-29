"use client";

import { useAllAgents } from "@/hooks";

interface OrgAgent {
  agent_id: string;
  name: string;
  role: string;
  posture: string;
  status: string;
}

interface OrgTeamData {
  team_id: string;
  agents: OrgAgent[];
}

export default function OrgBuilderPage() {
  const {
    data: agentEntries,
    isLoading: loading,
    error: queryError,
    refetch,
  } = useAllAgents();
  const error = queryError?.message ?? null;

  // Group agents by team
  const teamMap = new Map<string, OrgAgent[]>();
  for (const entry of agentEntries ?? []) {
    const list = teamMap.get(entry.team_id) ?? [];
    list.push({
      agent_id: entry.agent_id,
      name: entry.name,
      role: entry.role ?? "",
      posture: entry.posture,
      status: entry.status,
    });
    teamMap.set(entry.team_id, list);
  }
  const teams: OrgTeamData[] = Array.from(teamMap.entries()).map(
    ([team_id, agents]) => ({ team_id, agents }),
  );
  const totalAgents = teams.reduce((sum, t) => sum + t.agents.length, 0);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
          Organization Structure
        </h1>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
          Teams, agents, and their governance relationships
        </p>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
          <p className="text-sm text-gray-500 dark:text-gray-400">Teams</p>
          <p className="text-2xl font-bold text-gray-900 dark:text-white">
            {loading ? "—" : teams.length}
          </p>
        </div>
        <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
          <p className="text-sm text-gray-500 dark:text-gray-400">Agents</p>
          <p className="text-2xl font-bold text-gray-900 dark:text-white">
            {loading ? "—" : totalAgents}
          </p>
        </div>
        <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
          <p className="text-sm text-gray-500 dark:text-gray-400">Status</p>
          <p className="text-2xl font-bold text-green-600 dark:text-green-400">
            {loading ? "—" : "Operational"}
          </p>
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 dark:bg-red-900/20 dark:border-red-800 p-4">
          <p className="text-sm text-red-700 dark:text-red-300">{error}</p>
          <button
            onClick={() => refetch()}
            className="mt-2 text-sm text-red-600 underline"
          >
            Retry
          </button>
        </div>
      )}

      {loading && (
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-6 animate-pulse"
            >
              <div className="h-5 w-40 bg-gray-200 dark:bg-gray-700 rounded mb-4" />
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {[1, 2, 3].map((j) => (
                  <div
                    key={j}
                    className="h-20 bg-gray-100 dark:bg-gray-700/50 rounded"
                  />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {!loading &&
        teams.map((team) => (
          <div
            key={team.team_id}
            className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-6"
          >
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                {team.team_id}
              </h2>
              <span className="text-sm text-gray-500 dark:text-gray-400">
                {team.agents.length} agent{team.agents.length !== 1 ? "s" : ""}
              </span>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {team.agents.map((agent) => (
                <a
                  key={agent.agent_id}
                  href={`/agents/${agent.agent_id}`}
                  className="block rounded-lg border border-gray-100 dark:border-gray-700 p-3 hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors"
                >
                  <div className="flex items-start justify-between">
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium text-gray-900 dark:text-white truncate">
                        {agent.name}
                      </p>
                      <p className="text-xs text-gray-500 dark:text-gray-400 truncate mt-0.5">
                        {agent.role}
                      </p>
                    </div>
                    <span
                      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium capitalize ${
                        agent.posture === "delegated"
                          ? "bg-green-100 text-green-700"
                          : agent.posture === "continuous_insight"
                            ? "bg-purple-100 text-purple-700"
                            : agent.posture === "shared_planning"
                              ? "bg-indigo-100 text-indigo-700"
                              : agent.posture === "supervised"
                                ? "bg-blue-100 text-blue-700"
                                : "bg-gray-100 text-gray-700"
                      }`}
                    >
                      {agent.posture?.replace(/_/g, " ") ?? "unknown"}
                    </span>
                  </div>
                  <div className="mt-2 flex items-center gap-2">
                    <span
                      className={`inline-block w-2 h-2 rounded-full ${
                        agent.status === "active"
                          ? "bg-green-500"
                          : agent.status === "suspended"
                            ? "bg-yellow-500"
                            : "bg-gray-400"
                      }`}
                    />
                    <span className="text-xs text-gray-500 dark:text-gray-400 capitalize">
                      {agent.status}
                    </span>
                  </div>
                </a>
              ))}
            </div>
          </div>
        ))}
    </div>
  );
}
