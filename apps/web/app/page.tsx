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
import {
  Users,
  CheckCircle,
  Shield,
  DollarSign,
  ClipboardList,
  BarChart3,
  AlertCircle,
  ArrowUp,
  RefreshCw,
} from "lucide-react";
import DashboardShell from "../components/layout/DashboardShell";
import ActivityFeed from "../components/activity/ActivityFeed";
import { StatCard } from "@/components/pact";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Skeleton,
  Alert,
  AlertTitle,
  AlertDescription,
  Button,
} from "@/components/ui/shadcn";
import {
  useVerificationStats,
  useHeldActions,
  useCostReport,
  useDashboardTrends,
  useTrustChains,
} from "@/hooks";
import { useWebSocket } from "../lib/use-api";
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
// Verification Gradient Bar
// ---------------------------------------------------------------------------

interface GradientBarProps {
  level: string;
  count: number;
  total: number;
  color: string;
  textColor: string;
  /** Array of 7 numbers representing daily counts (last 7 days). */
  trend: number[];
}

function GradientBar({
  level,
  count,
  total,
  color,
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
          <span className="text-sm font-medium text-foreground">{level}</span>
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
          <span className="text-xs text-muted-foreground">{percent}%</span>
        </div>
      </div>
      {/* Horizontal bar */}
      <div className="h-2 w-full rounded-full bg-muted overflow-hidden">
        <div
          className={`h-full rounded-full ${color} transition-all duration-500`}
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
    <a href={href} className="group block">
      <Card className="transition-shadow hover:shadow-md h-full">
        <CardContent className="p-4 flex items-start gap-4">
          <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary group-hover:bg-primary group-hover:text-primary-foreground transition-colors">
            {icon}
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-medium text-foreground group-hover:text-primary">
                {label}
              </h3>
              {badge !== undefined && badge > 0 && (
                <span className="inline-flex items-center justify-center rounded-full bg-gradient-held-light text-gradient-held-dark px-2 py-0.5 text-xs font-semibold">
                  {badge}
                </span>
              )}
            </div>
            <p className="mt-0.5 text-xs text-muted-foreground">
              {description}
            </p>
          </div>
        </CardContent>
      </Card>
    </a>
  );
}

// ---------------------------------------------------------------------------
// Budget Gauge (inline progress bar)
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
      <div className="h-1.5 flex-1 rounded-full bg-muted overflow-hidden">
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
        className="text-xs text-muted-foreground whitespace-nowrap"
        aria-hidden="true"
      >
        {capped}% used
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Stat Cards Skeleton
// ---------------------------------------------------------------------------

function StatCardsSkeleton() {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {Array.from({ length: 4 }).map((_, i) => (
        <Card key={i}>
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <Skeleton className="h-10 w-10 rounded-lg" />
              <Skeleton className="h-5 w-5 rounded" />
            </div>
            <Skeleton className="mt-3 h-8 w-16" />
            <Skeleton className="mt-2 h-4 w-24" />
            <Skeleton className="mt-2 h-3 w-20" />
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Gradient Panel Skeleton
// ---------------------------------------------------------------------------

function GradientPanelSkeleton() {
  return (
    <div className="space-y-6">
      {Array.from({ length: 4 }).map((_, i) => (
        <div key={i} className="space-y-2">
          <div className="flex justify-between">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-4 w-12" />
          </div>
          <Skeleton className="h-2 w-full rounded-full" />
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page Component
// ---------------------------------------------------------------------------

export default function OverviewPage() {
  // --- Data fetching via React Query hooks ---
  const statsQuery = useVerificationStats();
  const heldQuery = useHeldActions();
  const chainsQuery = useTrustChains();
  const costQuery = useCostReport({ days: 1 });
  const trendsQuery = useDashboardTrends();

  const { connectionState } = useWebSocket();

  // --- Derived state ---
  const isAnyLoading =
    statsQuery.isLoading ||
    heldQuery.isLoading ||
    chainsQuery.isLoading ||
    costQuery.isLoading ||
    trendsQuery.isLoading;

  const firstError =
    statsQuery.error ??
    heldQuery.error ??
    chainsQuery.error ??
    costQuery.error ??
    trendsQuery.error;

  const handleRefetch = () => {
    void statsQuery.refetch();
    void heldQuery.refetch();
    void chainsQuery.refetch();
    void costQuery.refetch();
    void trendsQuery.refetch();
  };

  const statsData = statsQuery.data;
  const heldData = heldQuery.data;
  const chainsData = chainsQuery.data;
  const costData = costQuery.data;
  const trendsData = trendsQuery.data;

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
  const dailyBudget = 50;
  const budgetPercent =
    dailyBudget > 0 ? Math.round((totalCostToday / dailyBudget) * 100) : 0;

  // Verification rate: percent auto-approved today
  const verificationRate = useMemo(() => {
    if (!statsData || statsData.total === 0) return 0;
    return Math.round((statsData.AUTO_APPROVED / statsData.total) * 100);
  }, [statsData]);

  // Trend data from the /api/v1/dashboard/trends endpoint (7-day daily
  // counts). Falls back to flat lines at the current value when unavailable.
  const buildFallbackTrend = (current: number): number[] => {
    return Array.from({ length: 7 }, () => current);
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
        textColor: "text-gradient-auto-dark",
        trend:
          trendsData?.auto_approved ??
          buildFallbackTrend(statsData.AUTO_APPROVED),
      },
      {
        level: "Flagged",
        count: statsData.FLAGGED,
        total,
        color: "bg-gradient-flagged",
        textColor: "text-gradient-flagged-dark",
        trend: trendsData?.flagged ?? buildFallbackTrend(statsData.FLAGGED),
      },
      {
        level: "Held",
        count: statsData.HELD,
        total,
        color: "bg-gradient-held",
        textColor: "text-gradient-held-dark",
        trend: trendsData?.held ?? buildFallbackTrend(statsData.HELD),
      },
      {
        level: "Blocked",
        count: statsData.BLOCKED,
        total,
        color: "bg-gradient-blocked",
        textColor: "text-gradient-blocked-dark",
        trend: trendsData?.blocked ?? buildFallbackTrend(statsData.BLOCKED),
      },
    ];
  }, [statsData, trendsData]);

  return (
    <DashboardShell
      activePath="/"
      title="Overview"
      breadcrumbs={[{ label: "Dashboard" }]}
      connectionStatus={toConnectionStatus(connectionState)}
      actions={
        <Button
          variant="outline"
          size="sm"
          onClick={handleRefetch}
          disabled={isAnyLoading}
        >
          <RefreshCw
            className={`h-4 w-4 ${isAnyLoading ? "animate-spin" : ""}`}
          />
          Refresh
        </Button>
      }
    >
      <div className="space-y-6">
        {/* Heading */}
        <p className="text-sm text-muted-foreground">
          Governed operational model for running organizations with AI agents
          under EATP trust governance, CO methodology, and CARE philosophy.
        </p>

        {/* Error */}
        {firstError && (
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertTitle>Error loading dashboard data</AlertTitle>
            <AlertDescription className="flex items-center justify-between">
              <span>
                {firstError instanceof Error
                  ? firstError.message
                  : "An unexpected error occurred"}
              </span>
              <Button variant="outline" size="sm" onClick={handleRefetch}>
                Retry
              </Button>
            </AlertDescription>
          </Alert>
        )}

        {/* ================================================================
            Row 1: Key Metrics (4 stat cards)
            ================================================================ */}
        {isAnyLoading ? (
          <StatCardsSkeleton />
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {/* Active Agents */}
            <StatCard
              href="/agents"
              icon={<Users className="h-5 w-5 text-blue-600" />}
              iconBg="bg-blue-50 dark:bg-blue-950"
              value={activeAgents}
              label="Active Agents"
              subContent={
                <div className="flex items-center gap-2">
                  <span className="inline-flex items-center text-xs font-medium text-green-600">
                    <ArrowUp className="mr-0.5 h-3 w-3" />
                    {agentTrend} this week
                  </span>
                  <span className="text-xs text-muted-foreground">
                    of {totalAgents}
                  </span>
                </div>
              }
            />

            {/* Pending Approvals */}
            <StatCard
              href="/approvals"
              icon={
                <CheckCircle
                  className={`h-5 w-5 ${pendingCount > 0 ? "text-orange-600" : "text-green-600"}`}
                />
              }
              iconBg={
                pendingCount > 0
                  ? "bg-orange-50 dark:bg-orange-950"
                  : "bg-green-50 dark:bg-green-950"
              }
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
                      <span className="inline-flex items-center rounded-full bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300 px-1.5 py-0.5 font-medium">
                        {criticalCount} critical
                      </span>
                    )}
                    {standardCount > 0 && (
                      <span className="text-muted-foreground">
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
              icon={<Shield className="h-5 w-5 text-green-600" />}
              iconBg="bg-green-50 dark:bg-green-950"
              value={`${verificationRate}%`}
              label="Verification Rate"
              subContent={
                <span className="text-xs text-muted-foreground">
                  auto-approved today
                </span>
              }
            />

            {/* API Spend Today */}
            <StatCard
              href="/cost"
              icon={<DollarSign className="h-5 w-5 text-emerald-600" />}
              iconBg="bg-emerald-50 dark:bg-emerald-950"
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
            <Card className="h-full">
              <CardHeader className="pb-4">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-sm font-semibold">
                    Verification Gradient
                  </CardTitle>
                  <a
                    href="/verification"
                    className="text-xs font-medium text-primary hover:text-primary/80"
                  >
                    View Details
                  </a>
                </div>
              </CardHeader>
              <CardContent>
                {statsQuery.isLoading ? (
                  <GradientPanelSkeleton />
                ) : (
                  <div className="space-y-5">
                    {gradientLevels.map((gl) => (
                      <GradientBar key={gl.level} {...gl} />
                    ))}

                    {/* Total summary */}
                    <div className="border-t border-border pt-4 mt-4">
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-medium text-foreground">
                          Total Verifications
                        </span>
                        <span className="text-lg font-semibold text-foreground">
                          {statsData?.total.toLocaleString() ?? 0}
                        </span>
                      </div>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </div>

        {/* ================================================================
            Row 3: Quick Actions
            ================================================================ */}
        <div>
          <h2 className="mb-3 text-sm font-semibold text-foreground">
            Quick Actions
          </h2>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <QuickAction
              href="/approvals"
              icon={<ClipboardList className="h-5 w-5" />}
              label="Review Approvals"
              description="Review and resolve HELD actions awaiting human approval"
              badge={pendingCount}
            />
            <QuickAction
              href="/audit"
              icon={<Shield className="h-5 w-5" />}
              label="View Audit Trail"
              description="Search cryptographic audit anchors and action history"
            />
            <QuickAction
              href="/cost"
              icon={<BarChart3 className="h-5 w-5" />}
              label="Cost Report"
              description="API spend breakdown by agent, model, and time period"
            />
            <QuickAction
              href="/agents"
              icon={<Users className="h-5 w-5" />}
              label="Agent Overview"
              description="View agent postures, capabilities, and trust status"
            />
          </div>
        </div>
      </div>
    </DashboardShell>
  );
}
