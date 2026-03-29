// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * React Query hooks for pool data and mutations.
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getApiClientAsync } from "@/lib/use-api";
import { queryKeys } from "@/lib/query-keys";
import { STALE_TIMES } from "@/lib/query-provider";

/** Fetch all pools. */
export function usePools() {
  return useQuery({
    queryKey: queryKeys.pools.list(),
    queryFn: async () => {
      const client = await getApiClientAsync();
      const res = await client.listPools();
      if (res.status === "error")
        throw new Error(res.error ?? "Failed to load pools");
      return res.data!;
    },
    staleTime: STALE_TIMES.frequent,
  });
}

/** Fetch pool detail by ID. */
export function usePoolDetail(id: string) {
  return useQuery({
    queryKey: queryKeys.pools.detail(id),
    queryFn: async () => {
      const client = await getApiClientAsync();
      const res = await client.getPool(id);
      if (res.status === "error")
        throw new Error(res.error ?? "Failed to load pool detail");
      return res.data!;
    },
    staleTime: STALE_TIMES.frequent,
    enabled: !!id,
  });
}

/** Create a new pool. */
export function useCreatePool() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: {
      name: string;
      org_id: string;
      type: string;
      routing_strategy: string;
    }) => {
      const client = await getApiClientAsync();
      const res = await client.createPool(data);
      if (res.status === "error")
        throw new Error(res.error ?? "Failed to create pool");
      return res.data!;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: queryKeys.pools.all,
      });
    },
  });
}
