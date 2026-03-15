// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * Mock data for the ShadowEnforcer dashboard.
 *
 * TODO: Replace with real API calls once GET /api/v1/shadow/{agent_id}/report
 * and GET /api/v1/shadow/{agent_id}/metrics endpoints are available.
 *
 * Data structures match the Python ShadowMetrics and ShadowReport models
 * from src/care_platform/trust/shadow_enforcer.py.
 */

// ---------------------------------------------------------------------------
// Types matching Python ShadowMetrics and ShadowReport models
// ---------------------------------------------------------------------------

/** Mirrors care_platform.trust.shadow_enforcer.ShadowMetrics. */
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

/** Mirrors care_platform.trust.shadow_enforcer.ShadowReport. */
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

/** Combined data for the shadow dashboard view. */
export interface ShadowDashboardData {
  metrics: ShadowMetrics;
  report: ShadowReport;
}

// ---------------------------------------------------------------------------
// Agent list for the selector
// ---------------------------------------------------------------------------

export interface ShadowAgentOption {
  agent_id: string;
  name: string;
  team_id: string;
  posture: string;
}

/** Mock agent options available for shadow data. */
export const MOCK_AGENTS: ShadowAgentOption[] = [
  {
    agent_id: "agent-ops-lead",
    name: "Operations Lead",
    team_id: "operations",
    posture: "supervised",
  },
  {
    agent_id: "agent-finance-analyst",
    name: "Finance Analyst",
    team_id: "finance",
    posture: "shared_planning",
  },
  {
    agent_id: "agent-content-writer",
    name: "Content Writer",
    team_id: "communications",
    posture: "continuous_insight",
  },
  {
    agent_id: "agent-code-reviewer",
    name: "Code Reviewer",
    team_id: "engineering",
    posture: "supervised",
  },
];

// ---------------------------------------------------------------------------
// Mock shadow data keyed by agent_id
// ---------------------------------------------------------------------------

const MOCK_DATA: Record<string, ShadowDashboardData> = {
  "agent-ops-lead": {
    metrics: {
      agent_id: "agent-ops-lead",
      total_evaluations: 1247,
      auto_approved_count: 1174,
      flagged_count: 42,
      held_count: 28,
      blocked_count: 3,
      dimension_trigger_counts: {
        financial: 18,
        operational: 31,
        temporal: 8,
        data_access: 12,
        communication: 4,
      },
      window_start: "2026-02-14T00:00:00Z",
      window_end: "2026-03-15T23:59:59Z",
      previous_pass_rate: 0.928,
    },
    report: {
      agent_id: "agent-ops-lead",
      evaluation_period_days: 30,
      total_evaluations: 1247,
      pass_rate: 0.9414,
      block_rate: 0.0024,
      hold_rate: 0.0224,
      flag_rate: 0.0337,
      dimension_breakdown: {
        financial: 0.0144,
        operational: 0.0249,
        temporal: 0.0064,
        data_access: 0.0096,
        communication: 0.0032,
      },
      upgrade_eligible: true,
      upgrade_blockers: [],
      recommendation:
        "Agent 'Operations Lead' shows strong shadow enforcement results " +
        "(94% pass rate across 1,247 evaluations). Eligible for posture " +
        "upgrade consideration.",
    },
  },
  "agent-finance-analyst": {
    metrics: {
      agent_id: "agent-finance-analyst",
      total_evaluations: 834,
      auto_approved_count: 701,
      flagged_count: 67,
      held_count: 52,
      blocked_count: 14,
      dimension_trigger_counts: {
        financial: 82,
        operational: 15,
        temporal: 3,
        data_access: 24,
        communication: 9,
      },
      window_start: "2026-02-14T00:00:00Z",
      window_end: "2026-03-15T23:59:59Z",
      previous_pass_rate: 0.82,
    },
    report: {
      agent_id: "agent-finance-analyst",
      evaluation_period_days: 30,
      total_evaluations: 834,
      pass_rate: 0.8405,
      block_rate: 0.0168,
      hold_rate: 0.0623,
      flag_rate: 0.0803,
      dimension_breakdown: {
        financial: 0.0983,
        operational: 0.018,
        temporal: 0.0036,
        data_access: 0.0288,
        communication: 0.0108,
      },
      upgrade_eligible: false,
      upgrade_blockers: [
        "Shadow pass rate 84% is below required 90%",
        "14 blocked action(s) recorded during shadow evaluation",
      ],
      recommendation:
        "Agent 'Finance Analyst' is not yet eligible for posture upgrade. " +
        "Blockers: Shadow pass rate 84% is below required 90%; " +
        "14 blocked action(s) recorded during shadow evaluation",
    },
  },
  "agent-content-writer": {
    metrics: {
      agent_id: "agent-content-writer",
      total_evaluations: 562,
      auto_approved_count: 548,
      flagged_count: 11,
      held_count: 3,
      blocked_count: 0,
      dimension_trigger_counts: {
        financial: 0,
        operational: 2,
        temporal: 1,
        data_access: 5,
        communication: 6,
      },
      window_start: "2026-02-14T00:00:00Z",
      window_end: "2026-03-15T23:59:59Z",
      previous_pass_rate: 0.971,
    },
    report: {
      agent_id: "agent-content-writer",
      evaluation_period_days: 30,
      total_evaluations: 562,
      pass_rate: 0.9751,
      block_rate: 0.0,
      hold_rate: 0.0053,
      flag_rate: 0.0196,
      dimension_breakdown: {
        financial: 0.0,
        operational: 0.0036,
        temporal: 0.0018,
        data_access: 0.0089,
        communication: 0.0107,
      },
      upgrade_eligible: true,
      upgrade_blockers: [],
      recommendation:
        "Agent 'Content Writer' shows strong shadow enforcement results " +
        "(98% pass rate across 562 evaluations). Eligible for posture " +
        "upgrade consideration.",
    },
  },
  "agent-code-reviewer": {
    metrics: {
      agent_id: "agent-code-reviewer",
      total_evaluations: 43,
      auto_approved_count: 41,
      flagged_count: 1,
      held_count: 1,
      blocked_count: 0,
      dimension_trigger_counts: {
        financial: 0,
        operational: 1,
        temporal: 0,
        data_access: 1,
        communication: 0,
      },
      window_start: "2026-03-10T00:00:00Z",
      window_end: "2026-03-15T23:59:59Z",
      previous_pass_rate: 0.95,
    },
    report: {
      agent_id: "agent-code-reviewer",
      evaluation_period_days: 5,
      total_evaluations: 43,
      pass_rate: 0.9535,
      block_rate: 0.0,
      hold_rate: 0.0233,
      flag_rate: 0.0233,
      dimension_breakdown: {
        financial: 0.0,
        operational: 0.0233,
        temporal: 0.0,
        data_access: 0.0233,
        communication: 0.0,
      },
      upgrade_eligible: false,
      upgrade_blockers: ["Total evaluations 43 is below required 100"],
      recommendation:
        "Agent 'Code Reviewer' is not yet eligible for posture upgrade. " +
        "Blockers: Total evaluations 43 is below required 100",
    },
  },
};

/**
 * Get mock shadow dashboard data for an agent.
 *
 * TODO: Replace with API call to GET /api/v1/shadow/{agent_id}/report
 * once the endpoint is implemented in endpoints.py.
 */
export function getMockShadowData(agentId: string): ShadowDashboardData | null {
  return MOCK_DATA[agentId] ?? null;
}
