// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * PassRateGauge -- large circular gauge showing the shadow pass rate.
 *
 * Uses a CSS-only SVG ring to render the pass rate as a percentage
 * with color-coded feedback (green = high, orange = moderate, red = low).
 */

"use client";

interface PassRateGaugeProps {
  /** Pass rate as a decimal between 0 and 1. */
  passRate: number;
  /** Total evaluations for context text. */
  totalEvaluations: number;
  /** Evaluation period in days. */
  periodDays: number;
}

/**
 * Determine the gauge color based on the pass rate threshold.
 *
 * Thresholds follow CARE posture upgrade requirements:
 *   >= 0.90 = green (eligible for upgrade consideration)
 *   >= 0.75 = orange (improving but not eligible)
 *   < 0.75  = red (needs attention)
 */
function getGaugeColor(rate: number): {
  stroke: string;
  text: string;
  label: string;
} {
  if (rate >= 0.9) {
    return {
      stroke: "#16a34a",
      text: "text-green-700",
      label: "Strong",
    };
  }
  if (rate >= 0.75) {
    return {
      stroke: "#f97316",
      text: "text-orange-700",
      label: "Moderate",
    };
  }
  return {
    stroke: "#dc2626",
    text: "text-red-700",
    label: "Needs Attention",
  };
}

/** Large circular gauge displaying the shadow pass rate. */
export default function PassRateGauge({
  passRate,
  totalEvaluations,
  periodDays,
}: PassRateGaugeProps) {
  const percentage = Math.round(passRate * 1000) / 10;
  const color = getGaugeColor(passRate);

  // SVG circle geometry
  const size = 160;
  const strokeWidth = 12;
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const dashOffset = circumference - passRate * circumference;

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-6">
      <h3 className="mb-4 text-center text-sm font-semibold text-gray-900">
        Shadow Pass Rate
      </h3>

      <div className="flex flex-col items-center">
        {/* SVG ring gauge */}
        <div
          className="relative"
          style={{ width: size, height: size }}
          role="img"
          aria-label={`Shadow pass rate: ${percentage}% -- ${color.label}. Based on ${totalEvaluations.toLocaleString()} evaluations over ${periodDays} days.`}
        >
          <svg
            width={size}
            height={size}
            className="-rotate-90"
            aria-hidden="true"
          >
            {/* Background ring */}
            <circle
              cx={size / 2}
              cy={size / 2}
              r={radius}
              fill="none"
              stroke="#e5e7eb"
              strokeWidth={strokeWidth}
            />
            {/* Value ring */}
            <circle
              cx={size / 2}
              cy={size / 2}
              r={radius}
              fill="none"
              stroke={color.stroke}
              strokeWidth={strokeWidth}
              strokeLinecap="round"
              strokeDasharray={circumference}
              strokeDashoffset={dashOffset}
              className="transition-all duration-700 ease-out"
            />
          </svg>
          {/* Center text */}
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className={`text-3xl font-bold ${color.text}`}>
              {percentage}%
            </span>
            <span className={`text-xs font-medium ${color.text}`}>
              {color.label}
            </span>
          </div>
        </div>

        {/* Context text */}
        <div className="mt-4 text-center">
          <p className="text-xs text-gray-500">
            Based on {totalEvaluations.toLocaleString()} evaluations over{" "}
            {periodDays} day{periodDays !== 1 ? "s" : ""}
          </p>
          <p className="mt-1 text-xs text-gray-400">
            Upgrade threshold: 90% pass rate
          </p>
        </div>
      </div>
    </div>
  );
}
