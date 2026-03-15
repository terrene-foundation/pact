// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * DimensionBreakdown -- bar chart showing which constraint dimensions
 * trigger most frequently during shadow evaluation.
 *
 * Displays all five CARE constraint dimensions:
 *   Financial, Operational, Temporal, Data Access, Communication.
 *
 * Uses CSS-only horizontal bars with CARE-themed colors.
 */

"use client";

interface DimensionBreakdownProps {
  /** Dimension trigger counts from ShadowMetrics. */
  dimensionTriggerCounts: Record<string, number>;
  /** Total evaluations for computing rates. */
  totalEvaluations: number;
}

/**
 * The five CARE constraint dimensions in canonical order.
 * Names must match the Python ConstraintEnvelope dimension keys.
 */
const DIMENSIONS = [
  {
    key: "financial",
    label: "Financial",
    barColor: "bg-blue-500",
    bgColor: "bg-blue-50",
    textColor: "text-blue-700",
  },
  {
    key: "operational",
    label: "Operational",
    barColor: "bg-purple-500",
    bgColor: "bg-purple-50",
    textColor: "text-purple-700",
  },
  {
    key: "temporal",
    label: "Temporal",
    barColor: "bg-cyan-500",
    bgColor: "bg-cyan-50",
    textColor: "text-cyan-700",
  },
  {
    key: "data_access",
    label: "Data Access",
    barColor: "bg-amber-500",
    bgColor: "bg-amber-50",
    textColor: "text-amber-700",
  },
  {
    key: "communication",
    label: "Communication",
    barColor: "bg-indigo-500",
    bgColor: "bg-indigo-50",
    textColor: "text-indigo-700",
  },
];

/** Horizontal bar chart showing dimension trigger frequency. */
export default function DimensionBreakdown({
  dimensionTriggerCounts,
  totalEvaluations,
}: DimensionBreakdownProps) {
  const maxCount = Math.max(
    ...DIMENSIONS.map((d) => dimensionTriggerCounts[d.key] ?? 0),
    1,
  );

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-6">
      <h3 className="mb-1 text-sm font-semibold text-gray-900">
        Constraint Dimension Triggers
      </h3>
      <p className="mb-4 text-xs text-gray-500">
        How often each constraint dimension triggers during shadow evaluation
      </p>

      <div className="space-y-3">
        {DIMENSIONS.map((dim) => {
          const count = dimensionTriggerCounts[dim.key] ?? 0;
          const rate =
            totalEvaluations > 0
              ? ((count / totalEvaluations) * 100).toFixed(1)
              : "0.0";
          const barWidth =
            maxCount > 0
              ? Math.max((count / maxCount) * 100, count > 0 ? 3 : 0)
              : 0;

          return (
            <div key={dim.key}>
              <div className="mb-1 flex items-center justify-between">
                <span className="text-sm font-medium text-gray-700">
                  {dim.label}
                </span>
                <div className="flex items-center gap-2">
                  <span className={`text-sm font-semibold ${dim.textColor}`}>
                    {count.toLocaleString()}
                  </span>
                  <span className="text-xs text-gray-400">
                    ({rate}% of evaluations)
                  </span>
                </div>
              </div>
              <div className="h-5 w-full rounded-full bg-gray-100">
                <div
                  className={`h-5 rounded-full transition-all duration-500 ${dim.barColor}`}
                  style={{ width: `${barWidth}%` }}
                  role="progressbar"
                  aria-valuenow={count}
                  aria-valuemin={0}
                  aria-valuemax={maxCount}
                  aria-label={`${dim.label}: ${count} triggers`}
                />
              </div>
            </div>
          );
        })}
      </div>

      {/* Summary note */}
      {totalEvaluations > 0 && (
        <p className="mt-4 text-xs text-gray-400">
          Dimensions with zero triggers are operating cleanly within
          constraints.
        </p>
      )}
    </div>
  );
}
