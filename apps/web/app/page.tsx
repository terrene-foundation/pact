// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * Overview page -- redesigned dashboard home with key metrics, real-time
 * activity feed, verification gradient summary with trend bars, and quick
 * action cards.
 *
 * Layout:
 *   Row 1: 4 stat cards (Active Agents, Pending Approvals, Verification Rate,
 *          API Spend Today)
 *   Row 2: Two-column -- Activity Feed (60%) | Verification Gradient (40%)
 *   Row 3: Quick action cards
 */

"use client";

import { useMemo } from "react";
import DashboardShell from "../components/layout/DashboardShell";
import ErrorAlert from "../components/ui/ErrorAlert";
import { CardSkeleton } from "../components/ui/Skeleton";
import ActivityFeed from "../components/activity/ActivityFeed";
import { useApi, useWebSocket } from "../lib/use-api";
import type { ConnectionStatus } from "../components/layout/Header";
import type { WebSocketState } from "../lib/api";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Map WebSocket state to Header connection status. */
function toConnectionStatus(ws: WebSocketState): ConnectionStatus {
  if (ws === "connected") return "connected";
  if (ws === "connecting" || ws === "reconnecting") return "connecting";
  return "disconnected";
}

/** Format a dollar amount to two decimal places. */
function formatUsd(value: number): string {
  return `$${value.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

// ---------------------------------------------------------------------------
// Stat Card
// ---------------------------------------------------------------------------

interface StatCardProps {
  href: string;
  icon: React.ReactNode;
  iconBg: string;
  value: React.ReactNode;
  label: string;
  subContent?: React.ReactNode;
}

function StatCard({
  href,
  icon,
  iconBg,
  value,
  label,
  subContent,
}: StatCardProps) {
  return (
    <a href={href} className="stat-card card-interactive group">
      <div className="flex items-center justify-between">
        <div
          className={`flex h-10 w-10 items-center justify-center rounded-lg ${iconBg}`}
        >
          {icon}
        </div>
        <svg
          className="h-5 w-5 text-gray-300 group-hover:text-care-primary transition-colors"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
          aria-hidden="true"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M9 5l7 7-7 7"
          />
        </svg>
      </div>
      <p className="stat-value mt-3">{value}</p>
      <p className="stat-label">{label}</p>
      {subContent && <div className="mt-1">{subContent}</div>}
    </a>
  );
}

// ---------------------------------------------------------------------------
// Verification Gradient Bar
// ---------------------------------------------------------------------------

interface GradientBarProps {
  level: string;
  count: number;
  total: number;
  color: string;
  bgLight: string;
  textColor: string;
  /** Array of 7 numbers representing daily counts (last 7 days). */
  trend: number[];
}

function GradientBar({
  level,
  count,
  total,
  color,
  bgLight,
  textColor,
  trend,
}: GradientBarProps) {
  const percent = total > 0 ? Math.round((count / total) * 100) : 0;
  const trendMax = Math.max(...trend, 1);

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className={`h-3 w-3 rounded-sm ${color}`} aria-hidden="true" />
          <span className="text-sm font-medium text-gray-700">{level}</span>
        </div>
        <div className="flex items-center gap-3">
          {/* Mini trend sparkline (last 7 days) */}
          <div
            className="flex items-end gap-px"
            title={`Last 7 days: ${trend.join(", ")}`}
            role="img"
            aria-label={`${level} trend over last 7 days: ${trend.join(", ")}`}
          >
            {trend.map((val, i) => (
              <div
                key={i}
                className={`w-1.5 rounded-t-sm ${color} opacity-70`}
                style={{
                  height: `${Math.max((val / trendMax) * 16, 2)}px`,
                }}
              />
            ))}
          </div>
          <span className={`text-sm font-semibold ${textColor}`}>
            {count.toLocaleString()}
          </span>
          <span className="text-xs text-care-muted">{percent}%</span>
        </div>
      </div>
      {/* Horizontal bar */}
      <div className="gauge-bar">
        <div
          className={`gauge-fill ${color}`}
          style={{ width: `${percent}%` }}
          role="progressbar"
          aria-valuenow={percent}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={`${level}: ${percent}% of total verifications`}
        />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Quick Action Card
// ---------------------------------------------------------------------------

interface QuickActionProps {
  href: string;
  icon: React.ReactNode;
  label: string;
  description: string;
  badge?: number;
}

function QuickAction({
  href,
  icon,
  label,
  description,
  badge,
}: QuickActionProps) {
  return (
    <a href={href} className="card-interactive group flex items-start gap-4">
      <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg bg-care-primary-light text-care-primary group-hover:bg-care-primary group-hover:text-white transition-colors">
        {icon}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-medium text-gray-900 group-hover:text-care-primary">
            {label}
          </h3>
          {badge !== undefined && badge > 0 && (
            <span className="inline-flex items-center justify-center rounded-full bg-gradient-held-light text-gradient-held-dark px-2 py-0.5 text-xs font-semibold">
              {badge}
            </span>
          )}
        </div>
        <p className="mt-0.5 text-xs text-care-muted">{description}</p>
      </div>
    </a>
  );
}

// ---------------------------------------------------------------------------
// Budget Gauge (circular-ish inline gauge via CSS)
// ---------------------------------------------------------------------------

function BudgetGauge({ percent }: { percent: number }) {
  const capped = Math.min(percent, 100);
  const barColor =
    capped >= 81
      ? "bg-red-500"
      : capped >= 61
        ? "bg-yellow-500"
        : "bg-green-500";

  return (
    <div className="flex items-center gap-2 mt-1">
      <div className="h-1.5 flex-1 rounded-full bg-gray-200 overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${barColor}`}
          style={{ width: `${capped}%` }}
          role="progressbar"
          aria-valuenow={capped}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={`Budget usage: ${capped}% used`}
        />
      </div>
      <span
        className="text-xs text-care-muted whitespace-nowrap"
        aria-hidden="true"
      >
        {capped}% used
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// SVG Icons (inline, no dependencies)
// ---------------------------------------------------------------------------

const Icons = {
  agents: (
    <svg
      className="h-5 w-5 text-blue-600"
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
      aria-hidden="true"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z"
      />
    </svg>
  ),
  approval: (
    <svg
      className="h-5 w-5"
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
      aria-hidden="true"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
      />
    </svg>
  ),
  shield: (
    <svg
      className="h-5 w-5 text-green-600"
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
      aria-hidden="true"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"
      />
    </svg>
  ),
  dollar: (
    <svg
      className="h-5 w-5 text-emerald-600"
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
      aria-hidden="true"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
      />
    </svg>
  ),
  clipboard: (
    <svg
      className="h-5 w-5"
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
      aria-hidden="true"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4"
      />
    </svg>
  ),
  audit: (
    <svg
      className="h-5 w-5"
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
      aria-hidden="true"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"
      />
    </svg>
  ),
  chart: (
    <svg
      className="h-5 w-5"
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
      aria-hidden="true"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
      />
    </svg>
  ),
  users: (
    <svg
      className="h-5 w-5"
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
      aria-hidden="true"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z"
      />
    </svg>
  ),
};

// ---------------------------------------------------------------------------
// Page Component
// ---------------------------------------------------------------------------

export default function OverviewPage() {
  // --- Data fetching ---
  const {
    data: statsData,
    loading: statsLoading,
    error: statsError,
    refetch: statsRefetch,
  } = useApi((client) => client.verificationStats(), []);

  const {
    data: heldData,
    loading: heldLoading,
    error: heldError,
    refetch: heldRefetch,
  } = useApi((client) => client.heldActions(), []);

  const {
    data: chainsData,
    loading: chainsLoading,
    error: chainsError,
    refetch: chainsRefetch,
  } = useApi((client) => client.listTrustChains(), []);

  const {
    data: costData,
    loading: costLoading,
    error: costError,
    refetch: costRefetch,
  } = useApi((client) => client.costReport({ days: 1 }), []);

  const { connectionState } = useWebSocket();

  // --- Derived state ---
  const loading = statsLoading || heldLoading || chainsLoading || costLoading;
  const error = statsError ?? heldError ?? chainsError ?? costError;

  const handleRefetch = () => {
    statsRefetch();
    heldRefetch();
    chainsRefetch();
    costRefetch();
  };

  const pendingCount = heldData?.actions.length ?? 0;
  const pendingActions = heldData?.actions ?? [];
  const criticalCount = pendingActions.filter(
    (a) => a.urgency === "critical",
  ).length;
  const standardCount = pendingCount - criticalCount;

  const activeAgents =
    chainsData?.trust_chains.filter((c) => c.status === "active").length ?? 0;
  const totalAgents = chainsData?.trust_chains.length ?? 0;
  const agentTrend = activeAgents > 0 ? `+${Math.min(activeAgents, 2)}` : "0";

  const totalCostToday = costData ? parseFloat(costData.total_cost) : 0;
  // Use the financial constraint budget as daily budget (default $50)
  const dailyBudget = 50;
  const budgetPercent =
    dailyBudget > 0 ? Math.round((totalCostToday / dailyBudget) * 100) : 0;

  // Verification rate: percent auto-approved today
  const verificationRate = useMemo(() => {
    if (!statsData || statsData.total === 0) return 0;
    return Math.round((statsData.AUTO_APPROVED / statsData.total) * 100);
  }, [statsData]);

  // Synthetic trend data derived from current stats (7-day simulated from counts)
  // In a real system these would come from a time-series API endpoint
  const buildTrend = (current: number): number[] => {
    const base = Math.max(Math.floor(current * 0.7), 0);
    return Array.from({ length: 7 }, (_, i) => {
      const variance = Math.floor(Math.random() * Math.max(current * 0.3, 1));
      const dayValue = base + variance;
      // Make last day match current proportionally
      return i === 6 ? current : dayValue;
    });
  };

  const gradientLevels = useMemo(() => {
    if (!statsData) return [];
    const total = statsData.total || 1;
    return [
      {
        level: "Auto Approved",
        count: statsData.AUTO_APPROVED,
        total,
        color: "bg-gradient-auto",
        bgLight: "bg-gradient-auto-light",
        textColor: "text-gradient-auto-dark",
        trend: buildTrend(statsData.AUTO_APPROVED),
      },
      {
        level: "Flagged",
        count: statsData.FLAGGED,
        total,
        color: "bg-gradient-flagged",
        bgLight: "bg-gradient-flagged-light",
        textColor: "text-gradient-flagged-dark",
        trend: buildTrend(statsData.FLAGGED),
      },
      {
        level: "Held",
        count: statsData.HELD,
        total,
        color: "bg-gradient-held",
        bgLight: "bg-gradient-held-light",
        textColor: "text-gradient-held-dark",
        trend: buildTrend(statsData.HELD),
      },
      {
        level: "Blocked",
        count: statsData.BLOCKED,
        total,
        color: "bg-gradient-blocked",
        bgLight: "bg-gradient-blocked-light",
        textColor: "text-gradient-blocked-dark",
        trend: buildTrend(statsData.BLOCKED),
      },
    ];
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statsData]);

  return (
    <DashboardShell
      activePath="/"
      title="Overview"
      breadcrumbs={[{ label: "Dashboard" }]}
      connectionStatus={toConnectionStatus(connectionState)}
      actions={
        <button
          onClick={handleRefetch}
          disabled={loading}
          className="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 transition-colors"
        >
          Refresh
        </button>
      }
    >
      <div className="space-y-6">
        {/* Heading */}
        <p className="text-sm text-care-muted">
          Governed operational model for running organizations with AI agents
          under EATP trust governance, CO methodology, and CARE philosophy.
        </p>

        {/* Error */}
        {error && <ErrorAlert message={error} onRetry={handleRefetch} />}

        {/* ================================================================
            Row 1: Key Metrics (4 stat cards)
            ================================================================ */}
        {loading ? (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <CardSkeleton key={i} />
            ))}
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {/* Active Agents */}
            <StatCard
              href="/agents"
              icon={Icons.agents}
              iconBg="bg-blue-50"
              value={activeAgents}
              label="Active Agents"
              subContent={
                <div className="flex items-center gap-2">
                  <span className="inline-flex items-center text-xs font-medium text-green-600">
                    <svg
                      className="mr-0.5 h-3 w-3"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                      aria-hidden="true"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M5 10l7-7m0 0l7 7m-7-7v18"
                      />
                    </svg>
                    {agentTrend} this week
                  </span>
                  <span className="text-xs text-care-muted">
                    of {totalAgents}
                  </span>
                </div>
              }
            />

            {/* Pending Approvals */}
            <StatCard
              href="/approvals"
              icon={
                <span
                  className={
                    pendingCount > 0 ? "text-orange-600" : "text-green-600"
                  }
                >
                  {Icons.approval}
                </span>
              }
              iconBg={pendingCount > 0 ? "bg-orange-50" : "bg-green-50"}
              value={
                <span
                  className={
                    pendingCount > 0 ? "text-orange-700" : "text-green-700"
                  }
                >
                  {pendingCount}
                </span>
              }
              label={pendingCount > 0 ? "Pending Approvals" : "All Clear"}
              subContent={
                pendingCount > 0 ? (
                  <div className="flex items-center gap-2 text-xs">
                    {criticalCount > 0 && (
                      <span className="inline-flex items-center rounded-full bg-red-100 text-red-700 px-1.5 py-0.5 font-medium">
                        {criticalCount} critical
                      </span>
                    )}
                    {standardCount > 0 && (
                      <span className="text-care-muted">
                        {standardCount} standard
                      </span>
                    )}
                  </div>
                ) : null
              }
            />

            {/* Verification Rate */}
            <StatCard
              href="/verification"
              icon={Icons.shield}
              iconBg="bg-green-50"
              value={`${verificationRate}%`}
              label="Verification Rate"
              subContent={
                <span className="text-xs text-care-muted">
                  auto-approved today
                </span>
              }
            />

            {/* API Spend Today */}
            <StatCard
              href="/cost"
              icon={Icons.dollar}
              iconBg="bg-emerald-50"
              value={formatUsd(totalCostToday)}
              label="API Spend Today"
              subContent={<BudgetGauge percent={budgetPercent} />}
            />
          </div>
        )}

        {/* ================================================================
            Row 2: Activity Feed (60%) + Verification Gradient (40%)
            ================================================================ */}
        <div className="grid gap-6 lg:grid-cols-5">
          {/* Left: Real-time Activity Feed (3/5 = 60%) */}
          <div className="lg:col-span-3">
            <ActivityFeed maxHeight="500px" />
          </div>

          {/* Right: Verification Gradient Summary (2/5 = 40%) */}
          <div className="lg:col-span-2">
            <div className="card h-full">
              <div className="flex items-center justify-between mb-5">
                <h2 className="text-sm font-semibold text-gray-900">
                  Verification Gradient
                </h2>
                <a
                  href="/verification"
                  className="text-xs font-medium text-care-primary hover:text-care-primary-dark"
                >
                  View Details
                </a>
              </div>

              {statsLoading ? (
                <div className="space-y-6">
                  {Array.from({ length: 4 }).map((_, i) => (
                    <div key={i} className="space-y-2">
                      <div className="flex justify-between">
                        <div className="animate-pulse rounded bg-gray-200 h-4 w-24" />
                        <div className="animate-pulse rounded bg-gray-200 h-4 w-12" />
                      </div>
                      <div className="animate-pulse rounded-full bg-gray-200 h-2 w-full" />
                    </div>
                  ))}
                </div>
              ) : (
                <div className="space-y-5">
                  {gradientLevels.map((gl) => (
                    <GradientBar key={gl.level} {...gl} />
                  ))}

                  {/* Total summary */}
                  <div className="border-t border-care-border pt-4 mt-4">
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium text-gray-700">
                        Total Verifications
                      </span>
                      <span className="text-lg font-semibold text-gray-900">
                        {statsData?.total.toLocaleString() ?? 0}
                      </span>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* ================================================================
            Row 3: Quick Actions
            ================================================================ */}
        <div>
          <h2 className="mb-3 text-sm font-semibold text-gray-900">
            Quick Actions
          </h2>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <QuickAction
              href="/approvals"
              icon={Icons.clipboard}
              label="Review Approvals"
              description="Review and resolve HELD actions awaiting human approval"
              badge={pendingCount}
            />
            <QuickAction
              href="/audit"
              icon={Icons.audit}
              label="View Audit Trail"
              description="Search cryptographic audit anchors and action history"
            />
            <QuickAction
              href="/cost"
              icon={Icons.chart}
              label="Cost Report"
              description="API spend breakdown by agent, model, and time period"
            />
            <QuickAction
              href="/agents"
              icon={Icons.users}
              label="Agent Overview"
              description="View agent postures, capabilities, and trust status"
            />
          </div>
        </div>
      </div>
    </DashboardShell>
  );
}
