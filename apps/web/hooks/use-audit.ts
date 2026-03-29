// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * React Query hooks for audit anchor data.
 */

import { useQuery } from "@tanstack/react-query";
import { getApiClientAsync } from "@/lib/use-api";
import { queryKeys } from "@/lib/query-keys";
import { STALE_TIMES } from "@/lib/query-provider";

/** Fetch audit anchors with optional filters. */
export function useAuditAnchors(filters?: {
  agentId?: string;
  level?: string;
  startDate?: string;
  endDate?: string;
}) {
  const filterRecord: Record<string, string> = {};
  if (filters?.agentId) filterRecord.agentId = filters.agentId;
  if (filters?.level) filterRecord.level = filters.level;
  if (filters?.startDate) filterRecord.startDate = filters.startDate;
  if (filters?.endDate) filterRecord.endDate = filters.endDate;

  const hasFilters = Object.keys(filterRecord).length > 0;

  return useQuery({
    queryKey: queryKeys.audit.list(hasFilters ? filterRecord : undefined),
    queryFn: async () => {
      const client = await getApiClientAsync();
      const res = await client.listAuditAnchors(filters);
      if (res.status === "error")
        throw new Error(res.error ?? "Failed to load audit anchors");
      return res.data!;
    },
    staleTime: STALE_TIMES.frequent,
  });
}
