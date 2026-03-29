// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * Cost Report page -- displays API spend tracking, per-agent and per-model
 * breakdowns, daily spend trend chart, and budget alert history.
 *
 * Fetches data from GET /api/v1/cost/report via the shared API client.
 * Uses the CARE design system stat-card, card, and badge classes.
 */

"use client";

import { useState } from "react";
import DashboardShell from "../../components/layout/DashboardShell";
import { Skeleton } from "@/components/ui/shadcn/skeleton";
import { Alert, AlertDescription } from "@/components/ui/shadcn/alert";
import { Button } from "@/components/ui/shadcn/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/shadcn/select";
import { useCostReport } from "@/hooks";
import { AlertCircle, RefreshCw } from "lucide-react";

/** Number-of-days options for the period selector. */
const PERIOD_OPTIONS = [7, 14, 30, 60, 90] as const;

export default function CostReportPage() {
  const [days, setDays] = useState<number>(30);

  const {
    data,
    isLoading: loading,
    error: queryError,
    refetch,
  } = useCostReport({ days });
  const error = queryError?.message ?? null;

  return (
    <DashboardShell
      activePath="/cost-report"
      title="Cost Report"
      breadcrumbs={[
        { label: "Dashboard", href: "/" },
        { label: "Cost Report" },
      ]}
      actions={
        <div className="flex items-center gap-2">
          {/* Period selector */}
          <select
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
            className="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 focus:border-care-primary focus:outline-none focus:ring-1 focus:ring-care-primary"
            aria-label="Report period"
          >
            {PERIOD_OPTIONS.map((d) => (
              <option key={d} value={d}>
                Last {d} days
              </option>
            ))}
          </select>
          <button
            onClick={() => refetch()}
            disabled={loading}
            className="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 transition-colors"
          >
            Refresh
          </button>
        </div>
      }
    >
      <div className="space-y-8">
        <p className="text-sm text-gray-600">
          API cost tracking across all agents and models. Budget alerts trigger
          when agents approach or exceed their configured daily or monthly
          limits.
        </p>

        {/* Error */}
        {error && (
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {/* Summary stat cards */}
        {loading && (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-24 rounded-lg" />
            ))}
          </div>
        )}

        {!loading && data && <SummaryCards data={data} />}

        {/* By-agent breakdown */}
        {loading && <Skeleton className="h-48 rounded-lg" />}
        {!loading && data && <AgentBreakdown byAgent={data.by_agent} />}

        {/* By-model breakdown */}
        {loading && <Skeleton className="h-48 rounded-lg" />}
        {!loading && data && <ModelBreakdown byModel={data.by_model} />}

        {/* Daily spend trend chart */}
        {loading && (
          <div className="card">
            <Skeleton className="mb-4 h-5 w-40" />
            <Skeleton className="h-48 w-full" />
          </div>
        )}
        {!loading && data && (
          <DailySpendChart byDay={data.by_day} periodDays={data.period_days} />
        )}

        {/* Budget alerts */}
        {!loading && data && <AlertsSummary count={data.alerts_triggered} />}
      </div>
    </DashboardShell>
  );
}

// ---------------------------------------------------------------------------
// Summary Cards
// ---------------------------------------------------------------------------

interface CostData {
  total_cost: string;
  period_days: number;
  total_calls: number;
  by_agent: Record<string, string>;
  by_model: Record<string, string>;
  by_day: Record<string, string>;
  alerts_triggered: number;
}

function SummaryCards({ data }: { data: CostData }) {
  const totalCost = parseFloat(data.total_cost) || 0;

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {/* Total spend */}
      <div className="stat-card">
        <div className="flex items-center justify-between">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-50">
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
                d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
          </div>
        </div>
        <p className="stat-value text-gray-900">${totalCost.toFixed(2)}</p>
        <p className="stat-label">Total Spend</p>
      </div>

      {/* Period */}
      <div className="stat-card">
        <div className="flex items-center justify-between">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-purple-50">
            <svg
              className="h-5 w-5 text-purple-600"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"
              />
            </svg>
          </div>
        </div>
        <p className="stat-value text-gray-900">{data.period_days}</p>
        <p className="stat-label">Days in Period</p>
      </div>

      {/* Total API calls */}
      <div className="stat-card">
        <div className="flex items-center justify-between">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-green-50">
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
                d="M13 10V3L4 14h7v7l9-11h-7z"
              />
            </svg>
          </div>
        </div>
        <p className="stat-value text-gray-900">
          {data.total_calls.toLocaleString()}
        </p>
        <p className="stat-label">Total API Calls</p>
      </div>

      {/* Alerts triggered */}
      <div className="stat-card">
        <div className="flex items-center justify-between">
          <div
            className={`flex h-10 w-10 items-center justify-center rounded-lg ${
              data.alerts_triggered > 0 ? "bg-red-50" : "bg-green-50"
            }`}
          >
            <svg
              className={`h-5 w-5 ${
                data.alerts_triggered > 0 ? "text-red-600" : "text-green-600"
              }`}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"
              />
            </svg>
          </div>
        </div>
        <p
          className={`stat-value ${
            data.alerts_triggered > 0 ? "text-red-700" : "text-green-700"
          }`}
        >
          {data.alerts_triggered}
        </p>
        <p className="stat-label">
          {data.alerts_triggered > 0 ? "Alerts Triggered" : "No Alerts"}
        </p>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Agent Breakdown Table
// ---------------------------------------------------------------------------

function AgentBreakdown({ byAgent }: { byAgent: Record<string, string> }) {
  const entries = Object.entries(byAgent).sort(
    (a, b) => parseFloat(b[1]) - parseFloat(a[1]),
  );

  if (entries.length === 0) {
    return (
      <div className="card">
        <h2 className="mb-4 text-sm font-semibold text-gray-900">
          Cost by Agent
        </h2>
        <p className="text-sm text-gray-500">
          No agent cost data recorded in this period.
        </p>
      </div>
    );
  }

  const totalCost = entries.reduce(
    (sum, [, cost]) => sum + parseFloat(cost),
    0,
  );

  return (
    <div className="card p-0 overflow-hidden">
      <div className="px-6 pt-6 pb-3">
        <h2 className="text-sm font-semibold text-gray-900">Cost by Agent</h2>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-t border-care-border bg-gray-50">
              <th className="px-6 py-3 text-left font-medium text-gray-500">
                Agent ID
              </th>
              <th className="px-6 py-3 text-right font-medium text-gray-500">
                Total Cost
              </th>
              <th className="px-6 py-3 text-right font-medium text-gray-500">
                Share
              </th>
              <th className="px-6 py-3 text-left font-medium text-gray-500">
                Distribution
              </th>
            </tr>
          </thead>
          <tbody>
            {entries.map(([agentId, cost]) => {
              const costNum = parseFloat(cost);
              const share = totalCost > 0 ? (costNum / totalCost) * 100 : 0;

              return (
                <tr
                  key={agentId}
                  className="border-t border-care-border hover:bg-gray-50 transition-colors"
                >
                  <td className="px-6 py-3">
                    <span className="font-hash text-gray-900">{agentId}</span>
                  </td>
                  <td className="px-6 py-3 text-right font-medium text-gray-900">
                    ${costNum.toFixed(4)}
                  </td>
                  <td className="px-6 py-3 text-right text-gray-500">
                    {share.toFixed(1)}%
                  </td>
                  <td className="px-6 py-3">
                    <div className="gauge-bar w-full max-w-[120px]">
                      <div
                        className="gauge-fill bg-care-primary"
                        style={{ width: `${Math.max(share, 2)}%` }}
                        role="progressbar"
                        aria-valuenow={Math.round(share)}
                        aria-valuemin={0}
                        aria-valuemax={100}
                        aria-label={`${agentId}: ${share.toFixed(1)}% of total cost`}
                      />
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Model Breakdown Table
// ---------------------------------------------------------------------------

function ModelBreakdown({ byModel }: { byModel: Record<string, string> }) {
  const entries = Object.entries(byModel).sort(
    (a, b) => parseFloat(b[1]) - parseFloat(a[1]),
  );

  if (entries.length === 0) {
    return (
      <div className="card">
        <h2 className="mb-4 text-sm font-semibold text-gray-900">
          Cost by Model
        </h2>
        <p className="text-sm text-gray-500">
          No model cost data recorded in this period.
        </p>
      </div>
    );
  }

  const totalCost = entries.reduce(
    (sum, [, cost]) => sum + parseFloat(cost),
    0,
  );

  return (
    <div className="card p-0 overflow-hidden">
      <div className="px-6 pt-6 pb-3">
        <h2 className="text-sm font-semibold text-gray-900">Cost by Model</h2>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-t border-care-border bg-gray-50">
              <th className="px-6 py-3 text-left font-medium text-gray-500">
                Model
              </th>
              <th className="px-6 py-3 text-right font-medium text-gray-500">
                Total Cost
              </th>
              <th className="px-6 py-3 text-right font-medium text-gray-500">
                Share
              </th>
              <th className="px-6 py-3 text-left font-medium text-gray-500">
                Distribution
              </th>
            </tr>
          </thead>
          <tbody>
            {entries.map(([model, cost]) => {
              const costNum = parseFloat(cost);
              const share = totalCost > 0 ? (costNum / totalCost) * 100 : 0;

              return (
                <tr
                  key={model}
                  className="border-t border-care-border hover:bg-gray-50 transition-colors"
                >
                  <td className="px-6 py-3">
                    <span className="font-hash text-gray-900">{model}</span>
                  </td>
                  <td className="px-6 py-3 text-right font-medium text-gray-900">
                    ${costNum.toFixed(4)}
                  </td>
                  <td className="px-6 py-3 text-right text-gray-500">
                    {share.toFixed(1)}%
                  </td>
                  <td className="px-6 py-3">
                    <div className="gauge-bar w-full max-w-[120px]">
                      <div
                        className="gauge-fill bg-purple-500"
                        style={{ width: `${Math.max(share, 2)}%` }}
                        role="progressbar"
                        aria-valuenow={Math.round(share)}
                        aria-valuemin={0}
                        aria-valuemax={100}
                        aria-label={`${model}: ${share.toFixed(1)}% of total cost`}
                      />
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Daily Spend Trend Chart (CSS-only bar chart)
// ---------------------------------------------------------------------------

function DailySpendChart({
  byDay,
  periodDays,
}: {
  byDay: Record<string, string>;
  periodDays: number;
}) {
  // Build a sorted array of all days in the period, filling gaps with $0
  const today = new Date();
  const dayEntries: { date: string; cost: number }[] = [];

  for (let i = periodDays - 1; i >= 0; i--) {
    const d = new Date(today);
    d.setDate(d.getDate() - i);
    const key = d.toISOString().split("T")[0];
    dayEntries.push({
      date: key,
      cost: parseFloat(byDay[key] ?? "0"),
    });
  }

  const maxCost = Math.max(...dayEntries.map((e) => e.cost), 0.01);

  // For large periods, show fewer labels to avoid clutter
  const labelInterval = periodDays <= 14 ? 1 : periodDays <= 30 ? 3 : 7;

  if (dayEntries.every((e) => e.cost === 0)) {
    return (
      <div className="card">
        <h2 className="mb-4 text-sm font-semibold text-gray-900">
          Daily Spend Trend
        </h2>
        <p className="text-sm text-gray-500">
          No daily spend data recorded in this period.
        </p>
      </div>
    );
  }

  return (
    <div className="card">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-gray-900">
          Daily Spend Trend
        </h2>
        <p className="text-xs text-care-muted">
          Peak: ${maxCost.toFixed(2)}/day
        </p>
      </div>

      {/* Chart area */}
      <div
        className="flex items-end gap-px"
        style={{ height: "12rem" }}
        role="img"
        aria-label={`Daily spend trend chart showing ${dayEntries.length} days with peak spend of $${maxCost.toFixed(2)} per day`}
      >
        {dayEntries.map((entry, idx) => {
          const heightPct = maxCost > 0 ? (entry.cost / maxCost) * 100 : 0;

          return (
            <div
              key={entry.date}
              className="group relative flex flex-1 flex-col items-center justify-end"
              style={{ height: "100%" }}
            >
              {/* Tooltip */}
              <div className="pointer-events-none absolute -top-8 left-1/2 z-10 -translate-x-1/2 whitespace-nowrap rounded bg-gray-900 px-2 py-1 text-xs text-white opacity-0 transition-opacity group-hover:opacity-100">
                {entry.date}: ${entry.cost.toFixed(4)}
              </div>

              {/* Bar */}
              <div
                className="w-full rounded-t bg-care-primary transition-all duration-200 hover:bg-care-primary-dark"
                style={{
                  height: `${Math.max(heightPct, entry.cost > 0 ? 2 : 0)}%`,
                  minHeight: entry.cost > 0 ? "2px" : "0",
                }}
              />
            </div>
          );
        })}
      </div>

      {/* X-axis labels */}
      <div className="mt-2 flex">
        {dayEntries.map((entry, idx) => {
          const showLabel = idx % labelInterval === 0;
          return (
            <div key={entry.date} className="flex-1 text-center">
              {showLabel && (
                <span className="text-[10px] text-care-muted">
                  {formatShortDate(entry.date)}
                </span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

/** Format "2026-03-15" as "Mar 15". */
function formatShortDate(dateStr: string): string {
  const parts = dateStr.split("-");
  if (parts.length < 3) return dateStr;
  const monthNames = [
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
  ];
  const monthIdx = parseInt(parts[1], 10) - 1;
  const day = parseInt(parts[2], 10);
  return `${monthNames[monthIdx] ?? parts[1]} ${day}`;
}

// ---------------------------------------------------------------------------
// Budget Alerts Summary
// ---------------------------------------------------------------------------

function AlertsSummary({ count }: { count: number }) {
  if (count === 0) {
    return (
      <div className="card">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-green-50">
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
                d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
          </div>
          <div>
            <h2 className="text-sm font-semibold text-gray-900">
              Budget Alerts
            </h2>
            <p className="text-sm text-green-700">
              No budget alerts triggered in this period. All agents are within
              their configured spending limits.
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="card border-orange-200 bg-orange-50/50">
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-orange-100">
          <svg
            className="h-5 w-5 text-orange-600"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z"
            />
          </svg>
        </div>
        <div>
          <h2 className="text-sm font-semibold text-gray-900">Budget Alerts</h2>
          <p className="text-sm text-orange-700">
            {count} budget {count === 1 ? "alert" : "alerts"} triggered in this
            period. Review agent budget configurations in the constraint
            envelopes to adjust limits if needed.
          </p>
        </div>
      </div>
    </div>
  );
}
