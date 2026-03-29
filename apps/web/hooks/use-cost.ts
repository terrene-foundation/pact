// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * React Query hooks for API cost reporting data.
 */

import { useQuery } from "@tanstack/react-query";
import { getApiClientAsync } from "@/lib/use-api";
import { queryKeys } from "@/lib/query-keys";
import { STALE_TIMES } from "@/lib/query-provider";

/** Fetch API cost report with optional filters. */
export function useCostReport(params?: {
  teamId?: string;
  agentId?: string;
  days?: number;
}) {
  const keyParams: Record<string, unknown> = {};
  if (params?.teamId) keyParams.teamId = params.teamId;
  if (params?.agentId) keyParams.agentId = params.agentId;
  if (params?.days !== undefined) keyParams.days = params.days;

  const hasParams = Object.keys(keyParams).length > 0;

  return useQuery({
    queryKey: queryKeys.cost.report(hasParams ? keyParams : undefined),
    queryFn: async () => {
      const client = await getApiClientAsync();
      const res = await client.costReport(params);
      if (res.status === "error")
        throw new Error(res.error ?? "Failed to load cost report");
      return res.data!;
    },
    staleTime: STALE_TIMES.standard,
  });
}
