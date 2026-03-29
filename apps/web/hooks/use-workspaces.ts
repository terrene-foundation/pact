// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * React Query hooks for workspace data.
 */

import { useQuery } from "@tanstack/react-query";
import { getApiClientAsync } from "@/lib/use-api";
import { queryKeys } from "@/lib/query-keys";
import { STALE_TIMES } from "@/lib/query-provider";

/** Fetch all workspaces with state and phase. */
export function useWorkspaces() {
  return useQuery({
    queryKey: queryKeys.workspaces.list(),
    queryFn: async () => {
      const client = await getApiClientAsync();
      const res = await client.listWorkspaces();
      if (res.status === "error")
        throw new Error(res.error ?? "Failed to load workspaces");
      return res.data!;
    },
    staleTime: STALE_TIMES.standard,
  });
}
