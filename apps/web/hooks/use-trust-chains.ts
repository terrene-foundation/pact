// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * React Query hooks for trust chain data.
 */

import { useQuery } from "@tanstack/react-query";
import { getApiClientAsync } from "@/lib/use-api";
import { queryKeys } from "@/lib/query-keys";
import { STALE_TIMES } from "@/lib/query-provider";

/** Fetch all trust chains with status. */
export function useTrustChains() {
  return useQuery({
    queryKey: queryKeys.trustChains.list(),
    queryFn: async () => {
      const client = await getApiClientAsync();
      const res = await client.listTrustChains();
      if (res.status === "error")
        throw new Error(res.error ?? "Failed to load trust chains");
      return res.data!;
    },
    staleTime: STALE_TIMES.frequent,
  });
}

/** Fetch trust chain detail for a specific agent. */
export function useTrustChainDetail(agentId: string) {
  return useQuery({
    queryKey: queryKeys.trustChains.detail(agentId),
    queryFn: async () => {
      const client = await getApiClientAsync();
      const res = await client.getTrustChainDetail(agentId);
      if (res.status === "error")
        throw new Error(res.error ?? "Failed to load trust chain detail");
      return res.data!;
    },
    staleTime: STALE_TIMES.frequent,
    enabled: !!agentId,
  });
}
