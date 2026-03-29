// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * Verification page -- real-time verification gradient stats.
 *
 * Shows the distribution of agent actions across the four verification
 * gradient levels: AUTO_APPROVED, FLAGGED, HELD, BLOCKED.
 *
 * Uses React Query (useVerificationStats) for data fetching and Shadcn UI
 * components for layout, loading, and error states.
 */

"use client";

import { RefreshCw } from "lucide-react";
import DashboardShell from "../../components/layout/DashboardShell";
import GradientChart from "../../components/verification/GradientChart";
import { useVerificationStats } from "@/hooks";
import {
  Card,
  CardContent,
  Skeleton,
  Alert,
  AlertTitle,
  AlertDescription,
  Button,
} from "@/components/ui/shadcn";

/** Loading skeleton for the verification stats view. */
function VerificationSkeleton() {
  return (
    <div className="space-y-6">
      <Card>
        <CardContent className="p-5">
          <Skeleton className="h-48 w-full" />
        </CardContent>
      </Card>
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
        {Array.from({ length: 5 }).map((_, i) => (
          <Card key={i}>
            <CardContent className="p-4 space-y-2">
              <Skeleton className="h-3 w-20" />
              <Skeleton className="h-7 w-16" />
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}

export default function VerificationPage() {
  const { data, isLoading, error, refetch } = useVerificationStats();

  return (
    <DashboardShell
      activePath="/verification"
      title="Verification Gradient"
      breadcrumbs={[
        { label: "Dashboard", href: "/" },
        { label: "Verification" },
      ]}
      actions={
        <Button
          variant="outline"
          size="sm"
          onClick={() => void refetch()}
          disabled={isLoading}
        >
          <RefreshCw className={`h-4 w-4 ${isLoading ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      }
    >
      <div className="space-y-6">
        <p className="text-sm text-muted-foreground">
          Real-time monitoring of the CARE verification gradient. Every agent
          action is classified into one of four levels based on how it relates
          to the agent&apos;s constraint envelope boundaries.
        </p>

        {/* Loading */}
        {isLoading && <VerificationSkeleton />}

        {/* Error */}
        {error && (
          <Alert variant="destructive">
            <AlertTitle>Failed to load verification stats</AlertTitle>
            <AlertDescription className="flex items-center justify-between">
              <span>
                {error instanceof Error ? error.message : "Unknown error"}
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => void refetch()}
              >
                Retry
              </Button>
            </AlertDescription>
          </Alert>
        )}

        {/* Chart */}
        {data && <GradientChart stats={data} />}
      </div>
    </DashboardShell>
  );
}
