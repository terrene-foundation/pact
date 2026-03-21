// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * GradientChart -- bar chart showing verification gradient distribution.
 *
 * Displays the count of actions at each verification level:
 *   AUTO_APPROVED = green
 *   FLAGGED       = yellow
 *   HELD          = orange
 *   BLOCKED       = red
 *
 * Renders a responsive horizontal bar chart using pure CSS/Tailwind.
 */

"use client";

import type { VerificationStats } from "../../types/pact";

interface GradientChartProps {
  /** Verification stats from the API. */
  stats: VerificationStats;
}

/** Configuration for each verification level bar. */
const LEVEL_CONFIG = [
  {
    key: "AUTO_APPROVED" as const,
    label: "Auto Approved",
    barColor: "bg-green-500",
    bgColor: "bg-green-50",
    textColor: "text-green-700",
    borderColor: "border-green-200",
    description: "Actions within all constraint boundaries",
  },
  {
    key: "FLAGGED" as const,
    label: "Flagged",
    barColor: "bg-yellow-500",
    bgColor: "bg-yellow-50",
    textColor: "text-yellow-700",
    borderColor: "border-yellow-200",
    description: "Actions near a constraint boundary",
  },
  {
    key: "HELD" as const,
    label: "Held",
    barColor: "bg-orange-500",
    bgColor: "bg-orange-50",
    textColor: "text-orange-700",
    borderColor: "border-orange-200",
    description: "Actions queued for human approval",
  },
  {
    key: "BLOCKED" as const,
    label: "Blocked",
    barColor: "bg-red-500",
    bgColor: "bg-red-50",
    textColor: "text-red-700",
    borderColor: "border-red-200",
    description: "Actions that violated a hard constraint",
  },
];

/** Verification gradient bar chart. */
export default function GradientChart({ stats }: GradientChartProps) {
  const maxCount = Math.max(
    stats.AUTO_APPROVED,
    stats.FLAGGED,
    stats.HELD,
    stats.BLOCKED,
    1,
  );

  return (
    <div className="space-y-6">
      {/* Bar chart */}
      <div className="rounded-lg border border-gray-200 bg-white p-6">
        <h3 className="mb-6 text-sm font-semibold text-gray-900">
          Verification Level Distribution
        </h3>
        <div className="space-y-4">
          {LEVEL_CONFIG.map((level) => {
            const count = stats[level.key];
            const percentage =
              stats.total > 0 ? Math.round((count / stats.total) * 100) : 0;
            const barWidth =
              maxCount > 0
                ? Math.max((count / maxCount) * 100, count > 0 ? 2 : 0)
                : 0;

            return (
              <div key={level.key}>
                <div className="mb-1 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-gray-700">
                      {level.label}
                    </span>
                    <span className="text-xs text-gray-400">
                      {level.description}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span
                      className={`text-sm font-semibold ${level.textColor}`}
                    >
                      {count.toLocaleString()}
                    </span>
                    <span className="text-xs text-gray-400">
                      ({percentage}%)
                    </span>
                  </div>
                </div>
                <div className="h-6 w-full rounded-full bg-gray-100">
                  <div
                    className={`h-6 rounded-full transition-all duration-500 ${level.barColor}`}
                    style={{ width: `${barWidth}%` }}
                    role="progressbar"
                    aria-valuenow={count}
                    aria-valuemin={0}
                    aria-valuemax={maxCount}
                    aria-label={`${level.label}: ${count} actions`}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
        {LEVEL_CONFIG.map((level) => {
          const count = stats[level.key];
          const percentage =
            stats.total > 0 ? Math.round((count / stats.total) * 100) : 0;

          return (
            <div
              key={level.key}
              className={`rounded-lg border p-4 text-center ${level.bgColor} ${level.borderColor}`}
            >
              <p className={`text-2xl font-bold ${level.textColor}`}>
                {count.toLocaleString()}
              </p>
              <p className={`text-xs font-medium ${level.textColor}`}>
                {level.label}
              </p>
              <p className="text-xs text-gray-500">{percentage}%</p>
            </div>
          );
        })}
        {/* Total */}
        <div className="rounded-lg border border-gray-200 bg-white p-4 text-center">
          <p className="text-2xl font-bold text-gray-900">
            {stats.total.toLocaleString()}
          </p>
          <p className="text-xs font-medium text-gray-600">Total</p>
          <p className="text-xs text-gray-500">100%</p>
        </div>
      </div>
    </div>
  );
}
