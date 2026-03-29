// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * React Query hooks for ShadowEnforcer data.
 */

import { useQuery } from "@tanstack/react-query";
import { getApiClientAsync } from "@/lib/use-api";
import { queryKeys } from "@/lib/query-keys";
import { STALE_TIMES } from "@/lib/query-provider";

/** Fetch ShadowEnforcer metrics for a specific agent. */
export function useShadowMetrics(agentId: string) {
  return useQuery({
    queryKey: queryKeys.shadow.metrics(agentId),
    queryFn: async () => {
      const client = await getApiClientAsync();
      const res = await client.shadowMetrics(agentId);
      if (res.status === "error")
        throw new Error(res.error ?? "Failed to load shadow metrics");
      return res.data!;
    },
    staleTime: STALE_TIMES.frequent,
    enabled: !!agentId,
  });
}

/** Fetch ShadowEnforcer report for a specific agent. */
export function useShadowReport(agentId: string) {
  return useQuery({
    queryKey: queryKeys.shadow.report(agentId),
    queryFn: async () => {
      const client = await getApiClientAsync();
      const res = await client.shadowReport(agentId);
      if (res.status === "error")
        throw new Error(res.error ?? "Failed to load shadow report");
      return res.data!;
    },
    staleTime: STALE_TIMES.standard,
    enabled: !!agentId,
  });
}
