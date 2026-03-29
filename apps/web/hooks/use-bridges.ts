// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * React Query hooks for cross-functional bridge data and mutations.
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getApiClientAsync } from "@/lib/use-api";
import { queryKeys } from "@/lib/query-keys";
import { STALE_TIMES } from "@/lib/query-provider";
import type { CreateBridgeRequest } from "@/types/pact";

/** Fetch all bridges. */
export function useBridges() {
  return useQuery({
    queryKey: queryKeys.bridges.list(),
    queryFn: async () => {
      const client = await getApiClientAsync();
      const res = await client.listBridges();
      if (res.status === "error")
        throw new Error(res.error ?? "Failed to load bridges");
      return res.data!;
    },
    staleTime: STALE_TIMES.frequent,
  });
}

/** Fetch bridge detail by ID. */
export function useBridgeDetail(bridgeId: string) {
  return useQuery({
    queryKey: queryKeys.bridges.detail(bridgeId),
    queryFn: async () => {
      const client = await getApiClientAsync();
      const res = await client.getBridge(bridgeId);
      if (res.status === "error")
        throw new Error(res.error ?? "Failed to load bridge detail");
      return res.data!;
    },
    staleTime: STALE_TIMES.frequent,
    enabled: !!bridgeId,
  });
}

/** Create a new cross-functional bridge. */
export function useCreateBridge() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: CreateBridgeRequest) => {
      const client = await getApiClientAsync();
      const res = await client.createBridge(data);
      if (res.status === "error")
        throw new Error(res.error ?? "Failed to create bridge");
      return res.data!;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: queryKeys.bridges.all,
      });
    },
  });
}

/** Approve a bridge on source or target side. */
export function useApproveBridge() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      bridgeId,
      side,
      approverId,
    }: {
      bridgeId: string;
      side: "source" | "target";
      approverId: string;
    }) => {
      const client = await getApiClientAsync();
      const res = await client.approveBridge(bridgeId, side, approverId);
      if (res.status === "error")
        throw new Error(res.error ?? "Failed to approve bridge");
      return res.data!;
    },
    onSuccess: (_data, variables) => {
      void queryClient.invalidateQueries({
        queryKey: queryKeys.bridges.detail(variables.bridgeId),
      });
      void queryClient.invalidateQueries({
        queryKey: queryKeys.bridges.all,
      });
    },
  });
}

/** Suspend an active bridge. */
export function useSuspendBridge() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      bridgeId,
      reason,
    }: {
      bridgeId: string;
      reason: string;
    }) => {
      const client = await getApiClientAsync();
      const res = await client.suspendBridge(bridgeId, reason);
      if (res.status === "error")
        throw new Error(res.error ?? "Failed to suspend bridge");
      return res.data!;
    },
    onSuccess: (_data, variables) => {
      void queryClient.invalidateQueries({
        queryKey: queryKeys.bridges.detail(variables.bridgeId),
      });
      void queryClient.invalidateQueries({
        queryKey: queryKeys.bridges.all,
      });
    },
  });
}

/** Close a bridge. */
export function useCloseBridge() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      bridgeId,
      reason,
    }: {
      bridgeId: string;
      reason: string;
    }) => {
      const client = await getApiClientAsync();
      const res = await client.closeBridge(bridgeId, reason);
      if (res.status === "error")
        throw new Error(res.error ?? "Failed to close bridge");
      return res.data!;
    },
    onSuccess: (_data, variables) => {
      void queryClient.invalidateQueries({
        queryKey: queryKeys.bridges.detail(variables.bridgeId),
      });
      void queryClient.invalidateQueries({
        queryKey: queryKeys.bridges.all,
      });
    },
  });
}
