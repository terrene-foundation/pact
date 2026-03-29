// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * React Query hooks for approval (held action) data and mutations.
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getApiClientAsync } from "@/lib/use-api";
import { queryKeys } from "@/lib/query-keys";
import { STALE_TIMES } from "@/lib/query-provider";

/** Fetch all pending held actions. */
export function useHeldActions() {
  return useQuery({
    queryKey: queryKeys.approvals.heldActions(),
    queryFn: async () => {
      const client = await getApiClientAsync();
      const res = await client.heldActions();
      if (res.status === "error")
        throw new Error(res.error ?? "Failed to load held actions");
      return res.data!;
    },
    staleTime: STALE_TIMES.realtime,
  });
}

/** Approve a held action. */
export function useApproveAction() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      agentId,
      actionId,
      approverId,
      reason,
    }: {
      agentId: string;
      actionId: string;
      approverId: string;
      reason?: string;
    }) => {
      const client = await getApiClientAsync();
      const res = await client.approveAction(
        agentId,
        actionId,
        approverId,
        reason,
      );
      if (res.status === "error")
        throw new Error(res.error ?? "Failed to approve action");
      return res.data!;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: queryKeys.approvals.all,
      });
      void queryClient.invalidateQueries({
        queryKey: queryKeys.audit.all,
      });
    },
  });
}

/** Reject a held action. */
export function useRejectAction() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      agentId,
      actionId,
      approverId,
      reason,
    }: {
      agentId: string;
      actionId: string;
      approverId: string;
      reason?: string;
    }) => {
      const client = await getApiClientAsync();
      const res = await client.rejectAction(
        agentId,
        actionId,
        approverId,
        reason,
      );
      if (res.status === "error")
        throw new Error(res.error ?? "Failed to reject action");
      return res.data!;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: queryKeys.approvals.all,
      });
      void queryClient.invalidateQueries({
        queryKey: queryKeys.audit.all,
      });
    },
  });
}
