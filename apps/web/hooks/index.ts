// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * Barrel export for all React Query hooks.
 *
 * Usage:
 *   import { useTeams, useAgents, useBridges } from "@/hooks";
 */

// Teams
export { useTeams } from "./use-teams";

// Agents
export {
  useAllAgents,
  useAgents,
  useAgentDetail,
  useSuspendAgent,
  useRevokeAgent,
  useChangePosture,
} from "./use-agents";
export type { AgentEntry } from "./use-agents";

// Trust Chains
export { useTrustChains, useTrustChainDetail } from "./use-trust-chains";

// Envelopes
export {
  useEnvelopes,
  useEnvelopeDetail,
  useUpdateEnvelope,
} from "./use-envelopes";

// Approvals
export {
  useHeldActions,
  useApproveAction,
  useRejectAction,
} from "./use-approvals";

// Bridges
export {
  useBridges,
  useBridgeDetail,
  useBridgeAudit,
  useCreateBridge,
  useApproveBridge,
  useSuspendBridge,
  useCloseBridge,
} from "./use-bridges";

// Workspaces
export { useWorkspaces } from "./use-workspaces";

// Audit
export { useAuditAnchors } from "./use-audit";

// Verification
export { useVerificationStats, useDashboardTrends } from "./use-verification";

// Cost
export { useCostReport } from "./use-cost";

// Shadow Enforcer
export { useShadowMetrics, useShadowReport } from "./use-shadow";

// DM Team
export { useDmStatus, useSubmitDmTask } from "./use-dm";

// Objectives
export {
  useObjectives,
  useObjectiveDetail,
  useCreateObjective,
  useCancelObjective,
} from "./use-objectives";

// Requests
export {
  useRequests,
  useRequestDetail,
  useSubmitRequest,
  useCancelRequest,
} from "./use-requests";

// Pools
export {
  usePools,
  usePoolDetail,
  useCreatePool,
  useAddPoolMember,
  useRemovePoolMember,
} from "./use-pools";

// Org Builder
export { useOrgStructure, useDeployOrg } from "./use-org";
