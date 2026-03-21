// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * Skeleton -- loading placeholder with shimmer animation.
 *
 * Used across all dashboard views to show loading states while
 * data is being fetched from the PACT API.
 */

"use client";

interface SkeletonProps {
  /** CSS class for width/height customization. */
  className?: string;
}

/** Animated loading skeleton placeholder. */
export default function Skeleton({ className = "h-4 w-full" }: SkeletonProps) {
  return (
    <div
      className={`animate-pulse rounded bg-gray-200 ${className}`}
      role="status"
      aria-label="Loading..."
    />
  );
}

/** Card-shaped skeleton for dashboard cards. */
export function CardSkeleton() {
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-6">
      <Skeleton className="mb-4 h-5 w-1/3" />
      <Skeleton className="mb-2 h-4 w-2/3" />
      <Skeleton className="mb-2 h-4 w-1/2" />
      <Skeleton className="h-4 w-3/4" />
    </div>
  );
}

/** Table-shaped skeleton for data tables. */
export function TableSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div className="w-full">
      <Skeleton className="mb-3 h-8 w-64" />
      <div className="overflow-hidden rounded-lg border border-gray-200">
        <div className="bg-gray-50 px-4 py-3">
          <div className="flex gap-8">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-4 w-32" />
            <Skeleton className="h-4 w-20" />
            <Skeleton className="h-4 w-28" />
          </div>
        </div>
        {Array.from({ length: rows }).map((_, i) => (
          <div key={i} className="border-t border-gray-200 px-4 py-3">
            <div className="flex gap-8">
              <Skeleton className="h-4 w-24" />
              <Skeleton className="h-4 w-32" />
              <Skeleton className="h-4 w-20" />
              <Skeleton className="h-4 w-28" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
