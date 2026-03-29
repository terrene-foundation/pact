// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * React Query hooks for work request data and mutations.
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getApiClientAsync } from "@/lib/use-api";
import { queryKeys } from "@/lib/query-keys";
import { STALE_TIMES } from "@/lib/query-provider";

/** Fetch work requests with optional filters. */
export function useRequests(filters?: {
  status?: string;
  objective_id?: string;
}) {
  const filterRecord: Record<string, string> = {};
  if (filters?.status) filterRecord.status = filters.status;
  if (filters?.objective_id) filterRecord.objective_id = filters.objective_id;

  const hasFilters = Object.keys(filterRecord).length > 0;

  return useQuery({
    queryKey: queryKeys.requests.list(hasFilters ? filterRecord : undefined),
    queryFn: async () => {
      const client = await getApiClientAsync();
      const res = await client.listRequests(filters);
      if (res.status === "error")
        throw new Error(res.error ?? "Failed to load requests");
      return res.data!;
    },
    staleTime: STALE_TIMES.frequent,
  });
}

/** Fetch request detail by ID. */
export function useRequestDetail(id: string) {
  return useQuery({
    queryKey: queryKeys.requests.detail(id),
    queryFn: async () => {
      const client = await getApiClientAsync();
      const res = await client.getRequest(id);
      if (res.status === "error")
        throw new Error(res.error ?? "Failed to load request detail");
      return res.data!;
    },
    staleTime: STALE_TIMES.frequent,
    enabled: !!id,
  });
}

/** Submit a new work request. */
export function useSubmitRequest() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: {
      title: string;
      objective_id: string;
      priority: string;
      description?: string;
    }) => {
      const client = await getApiClientAsync();
      const res = await client.submitRequest(data);
      if (res.status === "error")
        throw new Error(res.error ?? "Failed to submit request");
      return res.data!;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: queryKeys.requests.all,
      });
      void queryClient.invalidateQueries({
        queryKey: queryKeys.objectives.all,
      });
    },
  });
}

/** Cancel a work request. */
export function useCancelRequest() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      const client = await getApiClientAsync();
      const res = await client.cancelRequest(id);
      if (res.status === "error")
        throw new Error(res.error ?? "Failed to cancel request");
      return res.data!;
    },
    onSuccess: (_data, id) => {
      void queryClient.invalidateQueries({
        queryKey: queryKeys.requests.detail(id),
      });
      void queryClient.invalidateQueries({
        queryKey: queryKeys.requests.all,
      });
      void queryClient.invalidateQueries({
        queryKey: queryKeys.objectives.all,
      });
    },
  });
}
