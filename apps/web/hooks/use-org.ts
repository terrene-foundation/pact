// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * React Query hooks for org builder API integration.
 */

import { useQuery, useMutation } from "@tanstack/react-query";
import { getApiClientAsync } from "@/lib/use-api";
import { queryKeys } from "@/lib/query-keys";
import { STALE_TIMES } from "@/lib/query-provider";

/** Fetch the current org structure from the backend. */
export function useOrgStructure() {
  return useQuery({
    queryKey: queryKeys.org.structure(),
    queryFn: async () => {
      const client = await getApiClientAsync();
      const res = await client.loadOrgStructure();
      if (res.status === "error")
        throw new Error(res.error ?? "Failed to load org structure");
      return res.data!;
    },
    staleTime: STALE_TIMES.standard,
    enabled: false, // Only fetch on manual trigger
  });
}

/** Deploy org YAML to the backend for compilation. */
export function useDeployOrg() {
  return useMutation({
    mutationFn: async (yaml: string) => {
      const client = await getApiClientAsync();
      const res = await client.deployOrg(yaml);
      if (res.status === "error")
        throw new Error(res.error ?? "Failed to deploy org");
      return res.data!;
    },
  });
}
