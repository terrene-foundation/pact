// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * React Query hooks for constraint envelope data.
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getApiClientAsync } from "@/lib/use-api";
import { queryKeys } from "@/lib/query-keys";
import { STALE_TIMES } from "@/lib/query-provider";
import type { ConstraintEnvelope } from "@/types/pact";

/** Fetch all constraint envelopes. */
export function useEnvelopes() {
  return useQuery({
    queryKey: queryKeys.envelopes.list(),
    queryFn: async () => {
      const client = await getApiClientAsync();
      const res = await client.listEnvelopes();
      if (res.status === "error")
        throw new Error(res.error ?? "Failed to load envelopes");
      return res.data!;
    },
    staleTime: STALE_TIMES.standard,
  });
}

/** Fetch a specific constraint envelope with all five dimensions. */
export function useEnvelopeDetail(envelopeId: string) {
  return useQuery({
    queryKey: queryKeys.envelopes.detail(envelopeId),
    queryFn: async () => {
      const client = await getApiClientAsync();
      const res = await client.getEnvelope(envelopeId);
      if (res.status === "error")
        throw new Error(res.error ?? "Failed to load envelope detail");
      return res.data!;
    },
    staleTime: STALE_TIMES.standard,
    enabled: !!envelopeId,
  });
}

/** Update envelope constraint values via PUT. */
export function useUpdateEnvelope() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      envelopeId,
      data,
    }: {
      envelopeId: string;
      data: Parameters<
        Awaited<ReturnType<typeof getApiClientAsync>>["updateEnvelope"]
      >[1];
    }) => {
      const client = await getApiClientAsync();
      const res = await client.updateEnvelope(envelopeId, data);
      if (res.status === "error")
        throw new Error(res.error ?? "Failed to update envelope");
      return res.data as ConstraintEnvelope;
    },
    onSuccess: (_data, variables) => {
      void queryClient.invalidateQueries({
        queryKey: queryKeys.envelopes.detail(variables.envelopeId),
      });
      void queryClient.invalidateQueries({
        queryKey: queryKeys.envelopes.all,
      });
    },
  });
}
