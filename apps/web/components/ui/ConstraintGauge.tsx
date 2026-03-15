// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * ConstraintGauge -- visual gauge showing dimension utilization.
 *
 * Displays a horizontal bar showing how much of a constraint dimension's
 * capacity has been used. Color transitions from green (safe) through
 * yellow (warning) to red (critical) as utilization increases.
 *
 * Thresholds:
 *   0-60%  = green  (safe)
 *   61-80% = yellow (warning / approaching FLAGGED)
 *   81%+   = red    (critical / near BLOCKED)
 */

"use client";

interface ConstraintGaugeProps {
  /** Human-readable label for the constraint dimension. */
  label: string;
  /** Current utilization as a value (e.g., current spend amount). */
  current: number;
  /** Maximum allowed value (e.g., max_spend_usd). */
  maximum: number;
  /** Unit label to display after values (e.g., "USD", "actions", ""). */
  unit?: string;
  /** Optional explicit utilization ratio (0-1). When provided, overrides current/maximum calculation. */
  utilization?: number;
}

/** Determine the color class based on utilization percentage. */
function getBarColor(percent: number): string {
  if (percent >= 81) return "bg-red-500";
  if (percent >= 61) return "bg-yellow-500";
  return "bg-green-500";
}

/** Determine the text color for the percentage label. */
function getTextColor(percent: number): string {
  if (percent >= 81) return "text-red-700";
  if (percent >= 61) return "text-yellow-700";
  return "text-green-700";
}

/** Format a number for display, rounding to reasonable precision. */
function formatValue(value: number, unit: string): string {
  if (unit === "USD" || unit === "usd") {
    return `$${value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  }
  if (Number.isInteger(value)) {
    return value.toLocaleString();
  }
  return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

/** Visual gauge showing constraint dimension utilization. */
export default function ConstraintGauge({
  label,
  current,
  maximum,
  unit = "",
  utilization,
}: ConstraintGaugeProps) {
  const ratio = utilization ?? (maximum > 0 ? current / maximum : 0);
  const percent = Math.min(Math.round(ratio * 100), 100);
  const barColor = getBarColor(percent);
  const textColor = getTextColor(percent);

  return (
    <div className="w-full">
      <div className="mb-1 flex items-center justify-between">
        <span className="text-sm font-medium text-gray-700">{label}</span>
        <span className={`text-sm font-semibold ${textColor}`}>{percent}%</span>
      </div>
      <div className="h-2.5 w-full rounded-full bg-gray-200">
        <div
          className={`h-2.5 rounded-full transition-all duration-300 ${barColor}`}
          style={{ width: `${percent}%` }}
          role="progressbar"
          aria-valuenow={percent}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={`${label}: ${percent}% utilized`}
        />
      </div>
      <div className="mt-1 flex items-center justify-between text-xs text-gray-500">
        <span>
          {formatValue(current, unit)}
          {unit && unit !== "USD" && unit !== "usd" ? ` ${unit}` : ""}
        </span>
        <span>
          of {formatValue(maximum, unit)}
          {unit && unit !== "USD" && unit !== "usd" ? ` ${unit}` : ""}
        </span>
      </div>
    </div>
  );
}
