// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * React Query hooks for objective data and mutations.
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getApiClientAsync } from "@/lib/use-api";
import { queryKeys } from "@/lib/query-keys";
import { STALE_TIMES } from "@/lib/query-provider";

/** Fetch all objectives with optional filters. */
export function useObjectives(filters?: { status?: string }) {
  const filterRecord: Record<string, string> = {};
  if (filters?.status) filterRecord.status = filters.status;

  const hasFilters = Object.keys(filterRecord).length > 0;

  return useQuery({
    queryKey: queryKeys.objectives.list(hasFilters ? filterRecord : undefined),
    queryFn: async () => {
      const client = await getApiClientAsync();
      const res = await client.listObjectives(filters);
      if (res.status === "error")
        throw new Error(res.error ?? "Failed to load objectives");
      return res.data!;
    },
    staleTime: STALE_TIMES.frequent,
  });
}

/** Fetch objective detail by ID. */
export function useObjectiveDetail(id: string) {
  return useQuery({
    queryKey: queryKeys.objectives.detail(id),
    queryFn: async () => {
      const client = await getApiClientAsync();
      const res = await client.getObjective(id);
      if (res.status === "error")
        throw new Error(res.error ?? "Failed to load objective detail");
      return res.data!;
    },
    staleTime: STALE_TIMES.frequent,
    enabled: !!id,
  });
}

/** Create a new objective. */
export function useCreateObjective() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: {
      title: string;
      org_address: string;
      budget: number;
      priority: string;
      description?: string;
    }) => {
      const client = await getApiClientAsync();
      const res = await client.createObjective(data);
      if (res.status === "error")
        throw new Error(res.error ?? "Failed to create objective");
      return res.data!;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: queryKeys.objectives.all,
      });
    },
  });
}

/** Cancel an objective. */
export function useCancelObjective() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      const client = await getApiClientAsync();
      const res = await client.cancelObjective(id);
      if (res.status === "error")
        throw new Error(res.error ?? "Failed to cancel objective");
      return res.data!;
    },
    onSuccess: (_data, id) => {
      void queryClient.invalidateQueries({
        queryKey: queryKeys.objectives.detail(id),
      });
      void queryClient.invalidateQueries({
        queryKey: queryKeys.objectives.all,
      });
    },
  });
}
