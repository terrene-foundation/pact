// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * React Query hooks for verification gradient data.
 */

import { useQuery } from "@tanstack/react-query";
import { getApiClientAsync } from "@/lib/use-api";
import { queryKeys } from "@/lib/query-keys";
import { STALE_TIMES } from "@/lib/query-provider";

/** Fetch verification gradient counts by level. */
export function useVerificationStats() {
  return useQuery({
    queryKey: queryKeys.verification.stats(),
    queryFn: async () => {
      const client = await getApiClientAsync();
      const res = await client.verificationStats();
      if (res.status === "error")
        throw new Error(res.error ?? "Failed to load verification stats");
      return res.data!;
    },
    staleTime: STALE_TIMES.frequent,
  });
}

/** Fetch 7-day verification gradient trends for sparklines. */
export function useDashboardTrends() {
  return useQuery({
    queryKey: queryKeys.verification.trends(),
    queryFn: async () => {
      const client = await getApiClientAsync();
      const res = await client.dashboardTrends();
      if (res.status === "error")
        throw new Error(res.error ?? "Failed to load dashboard trends");
      return res.data!;
    },
    staleTime: STALE_TIMES.standard,
  });
}
