// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * React Query hooks for agent data and mutations.
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getApiClientAsync } from "@/lib/use-api";
import { queryKeys } from "@/lib/query-keys";
import { STALE_TIMES } from "@/lib/query-provider";
import type { TrustPosture, AgentStatus } from "@/types/pact";

/** Agent entry combined with its team (used by useAllAgents). */
export interface AgentEntry {
  agent_id: string;
  name: string;
  role: string;
  posture: TrustPosture;
  status: AgentStatus;
  team_id: string;
}

/** Fetch all agents across all teams. */
export function useAllAgents() {
  return useQuery({
    queryKey: [...queryKeys.agents.all, "all-teams"],
    queryFn: async () => {
      const client = await getApiClientAsync();
      const teamsRes = await client.listTeams();
      if (teamsRes.status === "error" || !teamsRes.data)
        throw new Error(teamsRes.error ?? "Failed to load teams");

      const allAgents: AgentEntry[] = [];
      for (const teamId of teamsRes.data.teams) {
        const agentsRes = await client.listAgents(teamId);
        if (agentsRes.status === "ok" && agentsRes.data) {
          for (const agent of agentsRes.data.agents) {
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
      return allAgents;
    },
    staleTime: STALE_TIMES.frequent,
  });
}

/** Fetch agents for a specific team. */
export function useAgents(teamId: string) {
  return useQuery({
    queryKey: queryKeys.agents.list(teamId),
    queryFn: async () => {
      const client = await getApiClientAsync();
      const res = await client.listAgents(teamId);
      if (res.status === "error")
        throw new Error(res.error ?? "Failed to load agents");
      return res.data!;
    },
    staleTime: STALE_TIMES.frequent,
    enabled: !!teamId,
  });
}

/** Fetch detailed agent info with posture history. */
export function useAgentDetail(agentId: string) {
  return useQuery({
    queryKey: queryKeys.agents.detail(agentId),
    queryFn: async () => {
      const client = await getApiClientAsync();
      const res = await client.getAgentDetail(agentId);
      if (res.status === "error")
        throw new Error(res.error ?? "Failed to load agent detail");
      return res.data!;
    },
    staleTime: STALE_TIMES.frequent,
    enabled: !!agentId,
  });
}

/** Suspend an active agent. */
export function useSuspendAgent() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      agentId,
      reason,
      suspendedBy,
    }: {
      agentId: string;
      reason: string;
      suspendedBy: string;
    }) => {
      const client = await getApiClientAsync();
      const res = await client.suspendAgent(agentId, reason, suspendedBy);
      if (res.status === "error")
        throw new Error(res.error ?? "Failed to suspend agent");
      return res.data!;
    },
    onSuccess: (_data, variables) => {
      void queryClient.invalidateQueries({
        queryKey: queryKeys.agents.detail(variables.agentId),
      });
      void queryClient.invalidateQueries({
        queryKey: queryKeys.agents.all,
      });
      void queryClient.invalidateQueries({
        queryKey: queryKeys.trustChains.all,
      });
    },
  });
}

/** Revoke an agent (irreversible). */
export function useRevokeAgent() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      agentId,
      reason,
      revokedBy,
    }: {
      agentId: string;
      reason: string;
      revokedBy: string;
    }) => {
      const client = await getApiClientAsync();
      const res = await client.revokeAgent(agentId, reason, revokedBy);
      if (res.status === "error")
        throw new Error(res.error ?? "Failed to revoke agent");
      return res.data!;
    },
    onSuccess: (_data, variables) => {
      void queryClient.invalidateQueries({
        queryKey: queryKeys.agents.detail(variables.agentId),
      });
      void queryClient.invalidateQueries({
        queryKey: queryKeys.agents.all,
      });
      void queryClient.invalidateQueries({
        queryKey: queryKeys.trustChains.all,
      });
    },
  });
}

/** Change an agent's trust posture. */
export function useChangePosture() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      agentId,
      newPosture,
      reason,
      changedBy,
    }: {
      agentId: string;
      newPosture: string;
      reason: string;
      changedBy: string;
    }) => {
      const client = await getApiClientAsync();
      const res = await client.changePosture(
        agentId,
        newPosture,
        reason,
        changedBy,
      );
      if (res.status === "error")
        throw new Error(res.error ?? "Failed to change posture");
      return res.data!;
    },
    onSuccess: (_data, variables) => {
      void queryClient.invalidateQueries({
        queryKey: queryKeys.agents.detail(variables.agentId),
      });
      void queryClient.invalidateQueries({
        queryKey: queryKeys.agents.all,
      });
      void queryClient.invalidateQueries({
        queryKey: queryKeys.trustChains.all,
      });
    },
  });
}
