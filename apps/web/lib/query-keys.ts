// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * Query key factory for TanStack React Query.
 *
 * Provides structured, type-safe query keys for cache management,
 * invalidation, and optimistic updates across all PACT domains.
 */

export const queryKeys = {
  teams: {
    all: ["teams"] as const,
    list: () => [...queryKeys.teams.all, "list"] as const,
  },
  agents: {
    all: ["agents"] as const,
    list: (teamId?: string) =>
      [...queryKeys.agents.all, "list", teamId] as const,
    detail: (agentId: string) =>
      [...queryKeys.agents.all, "detail", agentId] as const,
  },
  trustChains: {
    all: ["trustChains"] as const,
    list: () => [...queryKeys.trustChains.all, "list"] as const,
    detail: (agentId: string) =>
      [...queryKeys.trustChains.all, "detail", agentId] as const,
  },
  envelopes: {
    all: ["envelopes"] as const,
    list: () => [...queryKeys.envelopes.all, "list"] as const,
    detail: (id: string) => [...queryKeys.envelopes.all, "detail", id] as const,
  },
  audit: {
    all: ["audit"] as const,
    list: (filters?: Record<string, string>) =>
      [...queryKeys.audit.all, "list", filters] as const,
  },
  approvals: {
    all: ["approvals"] as const,
    heldActions: () => [...queryKeys.approvals.all, "held"] as const,
  },
  bridges: {
    all: ["bridges"] as const,
    list: () => [...queryKeys.bridges.all, "list"] as const,
    detail: (id: string) => [...queryKeys.bridges.all, "detail", id] as const,
  },
  workspaces: {
    all: ["workspaces"] as const,
    list: () => [...queryKeys.workspaces.all, "list"] as const,
  },
  verification: {
    all: ["verification"] as const,
    stats: () => [...queryKeys.verification.all, "stats"] as const,
    trends: () => [...queryKeys.verification.all, "trends"] as const,
  },
  cost: {
    all: ["cost"] as const,
    report: (params?: Record<string, unknown>) =>
      [...queryKeys.cost.all, "report", params] as const,
  },
  shadow: {
    all: ["shadow"] as const,
    metrics: (agentId: string) =>
      [...queryKeys.shadow.all, "metrics", agentId] as const,
    report: (agentId: string) =>
      [...queryKeys.shadow.all, "report", agentId] as const,
  },
  dm: {
    all: ["dm"] as const,
    status: () => [...queryKeys.dm.all, "status"] as const,
  },
  objectives: {
    all: ["objectives"] as const,
    list: (filters?: Record<string, string>) =>
      [...queryKeys.objectives.all, "list", filters] as const,
    detail: (id: string) =>
      [...queryKeys.objectives.all, "detail", id] as const,
  },
  requests: {
    all: ["requests"] as const,
    list: (filters?: Record<string, string>) =>
      [...queryKeys.requests.all, "list", filters] as const,
    detail: (id: string) => [...queryKeys.requests.all, "detail", id] as const,
  },
  pools: {
    all: ["pools"] as const,
    list: () => [...queryKeys.pools.all, "list"] as const,
    detail: (id: string) => [...queryKeys.pools.all, "detail", id] as const,
  },
  org: {
    all: ["org"] as const,
    structure: () => [...queryKeys.org.all, "structure"] as const,
  },
} as const;
