// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * ShadowEnforcer dashboard page.
 *
 * Shows what AI agents WOULD do vs what they actually do -- the key insight
 * for trust posture upgrade decisions. The ShadowEnforcer runs verification
 * gradient evaluation in parallel with normal operations, collecting metrics
 * that provide empirical evidence for posture upgrades.
 *
 * Page structure:
 *   1. Agent selector dropdown
 *   2. Shadow metric cards (total, auto_approved, flagged, held, blocked, rates)
 *   3. Pass rate gauge (circular SVG ring)
 *   4. Verification level distribution (stacked horizontal bar)
 *   5. Dimension trigger breakdown (horizontal bar chart)
 *   6. Upgrade eligibility card with blockers and recommendation
 *
 * TODO: Replace mock data with real API calls once the shadow endpoints
 * are added to endpoints.py:
 *   GET /api/v1/shadow/{agent_id}/metrics
 *   GET /api/v1/shadow/{agent_id}/report
 */

"use client";

import { useState } from "react";
import DashboardShell from "../../components/layout/DashboardShell";
import ShadowSkeleton from "./elements/ShadowSkeleton";
import ShadowMetricsCards from "./elements/ShadowMetricsCards";
import PassRateGauge from "./elements/PassRateGauge";
import VerificationDistribution from "./elements/VerificationDistribution";
import DimensionBreakdown from "./elements/DimensionBreakdown";
import UpgradeEligibility from "./elements/UpgradeEligibility";
import {
  MOCK_AGENTS,
  getMockShadowData,
  type ShadowAgentOption,
} from "./elements/mock-data";

export default function ShadowPage() {
  const [selectedAgentId, setSelectedAgentId] = useState<string>(
    MOCK_AGENTS[0]?.agent_id ?? "",
  );

  // TODO: Replace with useApi() call once shadow endpoints exist.
  // For now, mock data loads synchronously so loading is always false.
  const loading = false;
  const shadowData = getMockShadowData(selectedAgentId);

  const selectedAgent = MOCK_AGENTS.find((a) => a.agent_id === selectedAgentId);

  return (
    <DashboardShell
      activePath="/shadow"
      title="ShadowEnforcer"
      breadcrumbs={[
        { label: "Dashboard", href: "/" },
        { label: "ShadowEnforcer" },
      ]}
    >
      <div className="space-y-6">
        {/* Page description */}
        <p className="text-sm text-gray-600">
          The ShadowEnforcer runs trust evaluation in parallel with normal agent
          operations. It records what WOULD happen under the current constraint
          configuration without blocking or modifying any actions. These metrics
          provide empirical evidence for trust posture upgrade decisions.
        </p>

        {/* Agent selector */}
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-4">
          <label
            htmlFor="agent-selector"
            className="text-sm font-medium text-gray-700"
          >
            Select Agent
          </label>
          <select
            id="agent-selector"
            value={selectedAgentId}
            onChange={(e) => setSelectedAgentId(e.target.value)}
            className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 sm:w-80"
          >
            {MOCK_AGENTS.map((agent: ShadowAgentOption) => (
              <option key={agent.agent_id} value={agent.agent_id}>
                {agent.name} ({agent.team_id} / {agent.posture})
              </option>
            ))}
          </select>
          {selectedAgent && (
            <span className="text-xs text-gray-400">
              Current posture:{" "}
              <span className="font-medium text-gray-600">
                {selectedAgent.posture.replace(/_/g, " ")}
              </span>
            </span>
          )}
        </div>

        {/* Loading state */}
        {loading && <ShadowSkeleton />}

        {/* No data state */}
        {!loading && !shadowData && (
          <div className="rounded-lg border border-gray-200 bg-white p-8 text-center text-gray-500">
            No shadow evaluation data available for this agent. The
            ShadowEnforcer may not have recorded any evaluations yet.
          </div>
        )}

        {/* Dashboard content */}
        {!loading && shadowData && (
          <>
            {/* Metrics cards */}
            <ShadowMetricsCards metrics={shadowData.metrics} />

            {/* Pass rate gauge + Verification distribution */}
            <div className="grid gap-6 lg:grid-cols-2">
              <PassRateGauge
                passRate={shadowData.report.pass_rate}
                totalEvaluations={shadowData.report.total_evaluations}
                periodDays={shadowData.report.evaluation_period_days}
              />
              <VerificationDistribution metrics={shadowData.metrics} />
            </div>

            {/* Dimension trigger breakdown */}
            <DimensionBreakdown
              dimensionTriggerCounts={
                shadowData.metrics.dimension_trigger_counts
              }
              totalEvaluations={shadowData.metrics.total_evaluations}
            />

            {/* Upgrade eligibility */}
            <UpgradeEligibility report={shadowData.report} />
          </>
        )}
      </div>
    </DashboardShell>
  );
}
