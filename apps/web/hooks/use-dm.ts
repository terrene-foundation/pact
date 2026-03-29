// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * React Query hooks for DM (Decision-Making) team data and mutations.
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getApiClientAsync } from "@/lib/use-api";
import { queryKeys } from "@/lib/query-keys";
import { STALE_TIMES } from "@/lib/query-provider";

/** Fetch DM team status overview. */
export function useDmStatus() {
  return useQuery({
    queryKey: queryKeys.dm.status(),
    queryFn: async () => {
      const client = await getApiClientAsync();
      const res = await client.getDmStatus();
      if (res.status === "error")
        throw new Error(res.error ?? "Failed to load DM status");
      return res.data!;
    },
    staleTime: STALE_TIMES.frequent,
  });
}

/** Submit a task to the DM team. */
export function useSubmitDmTask() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      description,
      targetAgent,
    }: {
      description: string;
      targetAgent?: string;
    }) => {
      const client = await getApiClientAsync();
      const res = await client.submitDmTask(description, targetAgent);
      if (res.status === "error")
        throw new Error(res.error ?? "Failed to submit DM task");
      return res.data!;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: queryKeys.dm.all,
      });
    },
  });
}
