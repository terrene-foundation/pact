// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * DimensionGauge -- individual constraint dimension gauge.
 *
 * Wraps ConstraintGauge with a labeled card layout showing the dimension
 * name, icon, and key metrics. Used in the envelope detail view to display
 * each of the five CARE constraint dimensions:
 *   Financial, Operational, Temporal, Data Access, Communication
 */

"use client";

import ConstraintGauge from "../ui/ConstraintGauge";

interface DimensionGaugeProps {
  /** Dimension name (e.g., "Financial"). */
  dimension: string;
  /** Current utilization value. */
  current: number;
  /** Maximum allowed value. */
  maximum: number;
  /** Unit label (e.g., "USD", "actions"). */
  unit?: string;
  /** Optional explicit utilization ratio (0-1), overrides current/maximum. */
  utilization?: number;
  /** SVG icon path for the dimension header. */
  iconPath: string;
  /** Key metrics to show beneath the gauge. */
  details: Array<{ label: string; value: string }>;
}

/** Constraint dimension gauge card with details. */
export default function DimensionGauge({
  dimension,
  current,
  maximum,
  unit,
  utilization,
  iconPath,
  details,
}: DimensionGaugeProps) {
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-5">
      {/* Dimension header */}
      <div className="mb-4 flex items-center gap-2">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-50">
          <svg
            className="h-4 w-4 text-blue-600"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d={iconPath}
            />
          </svg>
        </div>
        <h3 className="text-sm font-semibold text-gray-900">{dimension}</h3>
      </div>

      {/* Utilization gauge */}
      <div className="mb-4">
        <ConstraintGauge
          label="Utilization"
          current={current}
          maximum={maximum}
          unit={unit}
          utilization={utilization}
        />
      </div>

      {/* Detail metrics */}
      {details.length > 0 && (
        <div className="space-y-2 border-t border-gray-100 pt-3">
          {details.map((detail) => (
            <div
              key={detail.label}
              className="flex items-center justify-between text-xs"
            >
              <span className="text-gray-500">{detail.label}</span>
              <span className="font-medium text-gray-700">{detail.value}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
