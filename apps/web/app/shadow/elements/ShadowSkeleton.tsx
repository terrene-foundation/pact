// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * ShadowSkeleton -- loading placeholder for the ShadowEnforcer dashboard.
 *
 * Mimics the layout of the full dashboard: metric cards, gauge, charts,
 * and upgrade eligibility card.
 */

"use client";

import Skeleton from "../../../components/ui/Skeleton";

/** Full-page skeleton for the ShadowEnforcer dashboard. */
export default function ShadowSkeleton() {
  return (
    <div className="space-y-6">
      {/* Agent selector skeleton */}
      <Skeleton className="h-10 w-64" />

      {/* Metrics cards row */}
      <div className="grid gap-4 grid-cols-2 sm:grid-cols-3 lg:grid-cols-7">
        {Array.from({ length: 7 }).map((_, i) => (
          <div
            key={i}
            className="rounded-lg border border-gray-200 bg-white p-4"
          >
            <Skeleton className="mb-2 h-3 w-16" />
            <Skeleton className="h-7 w-12" />
          </div>
        ))}
      </div>

      {/* Pass rate gauge + distribution row */}
      <div className="grid gap-6 lg:grid-cols-2">
        <div className="rounded-lg border border-gray-200 bg-white p-6">
          <Skeleton className="mx-auto mb-4 h-4 w-24" />
          <Skeleton className="mx-auto h-40 w-40 rounded-full" />
        </div>
        <div className="rounded-lg border border-gray-200 bg-white p-6">
          <Skeleton className="mb-4 h-4 w-48" />
          <Skeleton className="mb-4 h-8 w-full rounded-full" />
          <div className="flex gap-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-3 w-20" />
            ))}
          </div>
        </div>
      </div>

      {/* Dimension breakdown */}
      <div className="rounded-lg border border-gray-200 bg-white p-6">
        <Skeleton className="mb-4 h-4 w-48" />
        <div className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i}>
              <Skeleton className="mb-1 h-3 w-24" />
              <Skeleton className="h-5 w-full rounded-full" />
            </div>
          ))}
        </div>
      </div>

      {/* Upgrade eligibility */}
      <div className="rounded-lg border border-gray-200 bg-white p-6">
        <Skeleton className="mb-3 h-4 w-32" />
        <Skeleton className="mb-2 h-3 w-full" />
        <Skeleton className="h-3 w-3/4" />
      </div>
    </div>
  );
}
