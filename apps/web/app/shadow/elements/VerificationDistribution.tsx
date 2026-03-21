// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * VerificationDistribution -- horizontal stacked bar showing the proportion
 * of AUTO_APPROVED / FLAGGED / HELD / BLOCKED from shadow evaluations.
 *
 * Uses CARE gradient colors (green/yellow/orange/red) in a single stacked
 * bar with a legend below. Pure CSS, no charting libraries.
 */

"use client";

import type { ShadowMetrics } from "../../../types/pact";

interface VerificationDistributionProps {
  metrics: ShadowMetrics;
}

/** Verification level display configuration. */
const LEVELS = [
  {
    key: "auto_approved_count" as const,
    label: "Auto Approved",
    color: "bg-green-500",
    dotColor: "bg-green-500",
    textColor: "text-green-700",
  },
  {
    key: "flagged_count" as const,
    label: "Flagged",
    color: "bg-yellow-500",
    dotColor: "bg-yellow-500",
    textColor: "text-yellow-700",
  },
  {
    key: "held_count" as const,
    label: "Held",
    color: "bg-orange-500",
    dotColor: "bg-orange-500",
    textColor: "text-orange-700",
  },
  {
    key: "blocked_count" as const,
    label: "Blocked",
    color: "bg-red-500",
    dotColor: "bg-red-500",
    textColor: "text-red-700",
  },
];

/** Stacked horizontal bar showing verification level distribution. */
export default function VerificationDistribution({
  metrics,
}: VerificationDistributionProps) {
  const total = metrics.total_evaluations;

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-6">
      <h3 className="mb-4 text-sm font-semibold text-gray-900">
        Verification Level Distribution
      </h3>

      {total === 0 ? (
        <p className="text-sm text-gray-500">No evaluations recorded yet.</p>
      ) : (
        <>
          {/* Stacked bar */}
          <div
            className="flex h-10 w-full overflow-hidden rounded-full"
            role="img"
            aria-label={`Verification distribution: ${LEVELS.map(
              (l) =>
                `${l.label} ${Math.round((metrics[l.key] / total) * 100)}%`,
            ).join(", ")}`}
          >
            {LEVELS.map((level) => {
              const count = metrics[level.key];
              const pct = (count / total) * 100;
              if (pct === 0) return null;
              return (
                <div
                  key={level.key}
                  className={`${level.color} transition-all duration-500`}
                  style={{ width: `${pct}%` }}
                  title={`${level.label}: ${count.toLocaleString()} (${pct.toFixed(1)}%)`}
                />
              );
            })}
          </div>

          {/* Legend */}
          <div className="mt-4 flex flex-wrap gap-x-6 gap-y-2">
            {LEVELS.map((level) => {
              const count = metrics[level.key];
              const pct = total > 0 ? (count / total) * 100 : 0;
              return (
                <div key={level.key} className="flex items-center gap-2">
                  <span
                    className={`inline-block h-3 w-3 rounded-full ${level.dotColor}`}
                    aria-hidden="true"
                  />
                  <span className="text-xs text-gray-600">{level.label}</span>
                  <span className={`text-xs font-semibold ${level.textColor}`}>
                    {count.toLocaleString()} ({pct.toFixed(1)}%)
                  </span>
                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
