// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * Verification page -- real-time verification gradient stats.
 *
 * Shows the distribution of agent actions across the four verification
 * gradient levels: AUTO_APPROVED, FLAGGED, HELD, BLOCKED.
 */

"use client";

import DashboardShell from "../../components/layout/DashboardShell";
import GradientChart from "../../components/verification/GradientChart";
import ErrorAlert from "../../components/ui/ErrorAlert";
import { CardSkeleton } from "../../components/ui/Skeleton";
import { useApi } from "../../lib/use-api";

export default function VerificationPage() {
  const { data, loading, error, refetch } = useApi(
    (client) => client.verificationStats(),
    []
  );

  return (
    <DashboardShell
      activePath="/verification"
      title="Verification Gradient"
      breadcrumbs={[
        { label: "Dashboard", href: "/" },
        { label: "Verification" },
      ]}
      actions={
        <button
          onClick={refetch}
          disabled={loading}
          className="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 transition-colors"
        >
          Refresh
        </button>
      }
    >
      <div className="space-y-6">
        <p className="text-sm text-gray-600">
          Real-time monitoring of the CARE verification gradient. Every agent
          action is classified into one of four levels based on how it relates to
          the agent&apos;s constraint envelope boundaries.
        </p>

        {/* Loading */}
        {loading && (
          <div className="space-y-6">
            <CardSkeleton />
            <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
              {Array.from({ length: 5 }).map((_, i) => (
                <CardSkeleton key={i} />
              ))}
            </div>
          </div>
        )}

        {/* Error */}
        {error && <ErrorAlert message={error} onRetry={refetch} />}

        {/* Chart */}
        {data && <GradientChart stats={data} />}
      </div>
    </DashboardShell>
  );
}
