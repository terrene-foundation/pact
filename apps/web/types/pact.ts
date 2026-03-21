// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * TypeScript interfaces matching the PACT Python models.
 *
 * These types mirror the Pydantic models and API response shapes from
 * src/pact/api/endpoints.py and related modules.
 */

// ---------------------------------------------------------------------------
// API Response
// ---------------------------------------------------------------------------

/** Standardized API response wrapper matching ApiResponse in Python. */
export interface ApiResponse<T = Record<string, unknown>> {
  status: "ok" | "error";
  data: T | null;
  error: string | null;
}

// ---------------------------------------------------------------------------
// Verification Levels & Trust Postures
// ---------------------------------------------------------------------------

/** Verification gradient levels for agent actions. */
export type VerificationLevel =
  | "AUTO_APPROVED"
  | "FLAGGED"
  | "HELD"
  | "BLOCKED";

/** EATP trust posture levels. */
export type TrustPosture =
  | "pseudo_agent"
  | "supervised"
  | "shared_planning"
  | "continuous_insight"
  | "delegated";

/** Agent lifecycle status. */
export type AgentStatus = "active" | "suspended" | "revoked" | "inactive";

// ---------------------------------------------------------------------------
// Trust Chain
// ---------------------------------------------------------------------------

/** Summary of a trust chain entry (from GET /api/v1/trust-chains). */
export interface TrustChainSummary {
  agent_id: string;
  name: string;
  team_id: string;
  posture: string;
  status: AgentStatus;
}

/** Detailed trust chain info (from GET /api/v1/trust-chains/{agent_id}). */
export interface TrustChainDetail {
  agent_id: string;
  name: string;
  role: string;
  team_id: string;
  posture: string;
  status: AgentStatus;
  capabilities: string[];
}

// ---------------------------------------------------------------------------
// Constraint Envelope
// ---------------------------------------------------------------------------

/** Financial dimension of a constraint envelope. */
export interface FinancialConstraint {
  max_spend_usd: number;
  api_cost_budget_usd: number | null;
  requires_approval_above_usd: number | null;
}

/** Operational dimension of a constraint envelope. */
export interface OperationalConstraint {
  allowed_actions: string[];
  blocked_actions: string[];
  max_actions_per_day: number | null;
}

/** Temporal dimension of a constraint envelope. */
export interface TemporalConstraint {
  active_hours_start: string | null;
  active_hours_end: string | null;
  timezone: string;
  blackout_periods: string[];
}

/** Data access dimension of a constraint envelope. */
export interface DataAccessConstraint {
  read_paths: string[];
  write_paths: string[];
  blocked_data_types: string[];
}

/** Communication dimension of a constraint envelope. */
export interface CommunicationConstraint {
  internal_only: boolean;
  allowed_channels: string[];
  external_requires_approval: boolean;
}

/** Full constraint envelope with all five PACT dimensions. */
export interface ConstraintEnvelope {
  envelope_id: string;
  description: string;
  financial: FinancialConstraint;
  operational: OperationalConstraint;
  temporal: TemporalConstraint;
  data_access: DataAccessConstraint;
  communication: CommunicationConstraint;
}

// ---------------------------------------------------------------------------
// Workspace
// ---------------------------------------------------------------------------

/** Workspace state (top-level lifecycle). */
export type WorkspaceState =
  | "provisioning"
  | "active"
  | "archived"
  | "decommissioned";

/** CO methodology phase. */
export type WorkspacePhase =
  | "analyze"
  | "plan"
  | "implement"
  | "validate"
  | "codify";

/** Workspace summary (from GET /api/v1/workspaces). */
export interface Workspace {
  id: string;
  path: string;
  description: string;
  state: WorkspaceState;
  phase: WorkspacePhase;
  team_id: string;
}

// ---------------------------------------------------------------------------
// Cross-Functional Bridge
// ---------------------------------------------------------------------------

/** Bridge types. */
export type BridgeType = "standing" | "scoped" | "ad_hoc";

/** Bridge lifecycle status. */
export type BridgeStatus =
  | "pending"
  | "negotiating"
  | "active"
  | "suspended"
  | "expired"
  | "closed"
  | "revoked";

/** Bridge summary (from GET /api/v1/bridges). */
export interface Bridge {
  bridge_id: string;
  bridge_type: BridgeType;
  source_team_id: string;
  target_team_id: string;
  purpose: string;
  status: BridgeStatus;
  created_at: string;
}

/** Bridge permissions. */
export interface BridgePermissions {
  read_paths: string[];
  write_paths: string[];
  message_types: string[];
  requires_attribution: boolean;
}

/** Detailed bridge info (from GET /api/v1/bridges/{bridge_id}). */
export interface BridgeDetail {
  bridge_id: string;
  bridge_type: BridgeType;
  source_team_id: string;
  target_team_id: string;
  purpose: string;
  status: BridgeStatus;
  created_at: string;
  created_by: string;
  approved_by_source: string | null; // RT13: approver_id or null
  approved_by_target: string | null; // RT13: approver_id or null
  valid_until: string | null;
  one_time_use: boolean;
  used: boolean;
  request_payload: Record<string, unknown>;
  response_payload: Record<string, unknown> | null;
  responded_at: string | null;
  permissions: BridgePermissions;
  replaced_by: string | null;
  replacement_for: string | null;
  access_log_count: number;
}

/** Request body for creating a bridge (POST /api/v1/bridges). */
export interface CreateBridgeRequest {
  bridge_type: BridgeType;
  source_team_id: string;
  target_team_id: string;
  purpose: string;
  permissions?: {
    read_paths?: string[];
    write_paths?: string[];
    message_types?: string[];
  };
  valid_days?: number;
  request_payload?: Record<string, unknown>;
  created_by?: string;
}

/** Bridge audit trail entry. */
export interface BridgeAuditEntry {
  agent_id: string;
  path: string;
  access_type: string;
  timestamp: string;
}

/** Response from GET /api/v1/bridges/{bridge_id}/audit. */
export interface BridgeAuditResponse {
  bridge_id: string;
  entries: BridgeAuditEntry[];
  total: number;
  limit: number;
  offset: number;
}

// ---------------------------------------------------------------------------
// Verification Stats
// ---------------------------------------------------------------------------

/** Verification gradient counts by level (from GET /api/v1/verification/stats). */
export interface VerificationStats {
  AUTO_APPROVED: number;
  FLAGGED: number;
  HELD: number;
  BLOCKED: number;
  total: number;
}

// ---------------------------------------------------------------------------
// Constraint Envelope Summary (for list views)
// ---------------------------------------------------------------------------

/** Envelope summary for list display (from GET /api/v1/envelopes). */
export interface EnvelopeSummary {
  envelope_id: string;
  description: string;
  agent_id: string;
  team_id: string;
}

// ---------------------------------------------------------------------------
// Audit Trail
// ---------------------------------------------------------------------------

/** Audit anchor entry (from GET /api/v1/audit). */
export interface AuditAnchor {
  anchor_id: string;
  agent_id: string;
  agent_name: string;
  team_id: string;
  action: string;
  verification_level: VerificationLevel;
  timestamp: string;
  details: string;
}

// ---------------------------------------------------------------------------
// Agent Detail (extended info with posture history)
// ---------------------------------------------------------------------------

/** Historical posture change record. */
export interface PostureChange {
  from_posture: TrustPosture;
  to_posture: TrustPosture;
  reason: string;
  changed_at: string;
  changed_by: string;
}

/** Full agent detail with posture history (from GET /api/v1/agents/{id}). */
export interface AgentDetail {
  agent_id: string;
  name: string;
  role: string;
  team_id: string;
  posture: TrustPosture;
  status: AgentStatus;
  capabilities: string[];
  envelope_id: string | null;
  created_at: string;
  last_active_at: string;
  posture_history: PostureChange[];
}

// ---------------------------------------------------------------------------
// ShadowEnforcer
// ---------------------------------------------------------------------------

/** Mirrors pact.trust.shadow_enforcer.ShadowMetrics. */
export interface ShadowMetrics {
  agent_id: string;
  total_evaluations: number;
  auto_approved_count: number;
  flagged_count: number;
  held_count: number;
  blocked_count: number;
  dimension_trigger_counts: Record<string, number>;
  window_start: string;
  window_end: string;
  previous_pass_rate: number;
}

/** Mirrors pact.trust.shadow_enforcer.ShadowReport. */
export interface ShadowReport {
  agent_id: string;
  evaluation_period_days: number;
  total_evaluations: number;
  pass_rate: number;
  block_rate: number;
  hold_rate: number;
  flag_rate: number;
  dimension_breakdown: Record<string, number>;
  upgrade_eligible: boolean;
  upgrade_blockers: string[];
  recommendation: string;
}

// ---------------------------------------------------------------------------
// DM (Decision-Making) Team
// ---------------------------------------------------------------------------

/** DM task lifecycle status. */
export type DmTaskStatus =
  | "pending"
  | "routing"
  | "executing"
  | "complete"
  | "held"
  | "failed";

/** DM agent summary within the team dashboard. */
export interface DmAgentSummary {
  agent_id: string;
  name: string;
  role: string;
  posture: TrustPosture;
  status: AgentStatus;
  tasks_submitted: number;
  tasks_completed: number;
  tasks_held: number;
  tasks_blocked: number;
}

/** DM team status overview (from GET /api/v1/dm/status). */
export interface DmStatus {
  team_id: string;
  agents: DmAgentSummary[];
  total_agents: number;
}

/** DM task submission response (from POST /api/v1/dm/tasks). */
export interface DmTask {
  task_id: string;
  description: string;
  target_agent: string | null;
  status: DmTaskStatus;
  result: string | null;
  created_at: string;
  completed_at: string | null;
}

// ---------------------------------------------------------------------------
// Real-time Events (WebSocket)
// ---------------------------------------------------------------------------

/** Event types emitted via WebSocket. */
export type EventType =
  | "audit_anchor"
  | "held_action"
  | "posture_change"
  | "bridge_status"
  | "verification_result"
  | "workspace_transition";

/** Real-time platform event from the WebSocket stream. */
export interface PlatformEvent {
  event_id: string;
  event_type: EventType;
  data: Record<string, unknown>;
  source_agent_id: string;
  source_team_id: string;
  timestamp: string;
}
