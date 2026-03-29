// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * React Query hooks for team data.
 */

import { useQuery } from "@tanstack/react-query";
import { getApiClientAsync } from "@/lib/use-api";
import { queryKeys } from "@/lib/query-keys";
import { STALE_TIMES } from "@/lib/query-provider";

/** Fetch all active teams. */
export function useTeams() {
  return useQuery({
    queryKey: queryKeys.teams.list(),
    queryFn: async () => {
      const client = await getApiClientAsync();
      const res = await client.listTeams();
      if (res.status === "error")
        throw new Error(res.error ?? "Failed to load teams");
      return res.data!;
    },
    staleTime: STALE_TIMES.static,
  });
}
