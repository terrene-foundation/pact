// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * ShadowMetricsCards -- stat cards showing shadow evaluation counts.
 *
 * Displays: total evaluations, auto_approved, flagged, held, blocked,
 * pass rate, and block rate. Uses CARE gradient colors to match the
 * verification level semantics.
 */

"use client";

import type { ShadowMetrics } from "../../../types/pact";

interface ShadowMetricsCardsProps {
  metrics: ShadowMetrics;
}

/** Configuration for each metric card. */
const CARDS: Array<{
  label: string;
  getValue: (m: ShadowMetrics) => string;
  bgColor: string;
  textColor: string;
  borderColor: string;
}> = [
  {
    label: "Total Evaluations",
    getValue: (m) => m.total_evaluations.toLocaleString(),
    bgColor: "bg-white",
    textColor: "text-gray-900",
    borderColor: "border-gray-200",
  },
  {
    label: "Auto Approved",
    getValue: (m) => m.auto_approved_count.toLocaleString(),
    bgColor: "bg-green-50",
    textColor: "text-green-700",
    borderColor: "border-green-200",
  },
  {
    label: "Flagged",
    getValue: (m) => m.flagged_count.toLocaleString(),
    bgColor: "bg-yellow-50",
    textColor: "text-yellow-700",
    borderColor: "border-yellow-200",
  },
  {
    label: "Held",
    getValue: (m) => m.held_count.toLocaleString(),
    bgColor: "bg-orange-50",
    textColor: "text-orange-700",
    borderColor: "border-orange-200",
  },
  {
    label: "Blocked",
    getValue: (m) => m.blocked_count.toLocaleString(),
    bgColor: "bg-red-50",
    textColor: "text-red-700",
    borderColor: "border-red-200",
  },
  {
    label: "Pass Rate",
    getValue: (m) => {
      if (m.total_evaluations === 0) return "0%";
      return `${((m.auto_approved_count / m.total_evaluations) * 100).toFixed(1)}%`;
    },
    bgColor: "bg-blue-50",
    textColor: "text-blue-700",
    borderColor: "border-blue-200",
  },
  {
    label: "Block Rate",
    getValue: (m) => {
      if (m.total_evaluations === 0) return "0%";
      return `${((m.blocked_count / m.total_evaluations) * 100).toFixed(1)}%`;
    },
    bgColor: "bg-gray-50",
    textColor: "text-gray-700",
    borderColor: "border-gray-300",
  },
];

/** Shadow evaluation metric cards in a responsive grid. */
export default function ShadowMetricsCards({
  metrics,
}: ShadowMetricsCardsProps) {
  return (
    <div className="grid gap-4 grid-cols-2 sm:grid-cols-3 lg:grid-cols-7">
      {CARDS.map((card) => (
        <div
          key={card.label}
          className={`rounded-lg border p-4 ${card.bgColor} ${card.borderColor}`}
        >
          <p className="text-xs font-medium text-gray-500">{card.label}</p>
          <p className={`mt-1 text-xl font-bold ${card.textColor}`}>
            {card.getValue(metrics)}
          </p>
        </div>
      ))}
    </div>
  );
}
