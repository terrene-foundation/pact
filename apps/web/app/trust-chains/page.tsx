// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * Trust Chains page -- displays all trust chains from the PACT API
 * as a visual tree grouped by team, showing genesis to delegation to agents.
 *
 * Uses React Query (useTrustChains) for data fetching and Shadcn UI
 * components for layout, loading, and error states.
 */

"use client";

import { RefreshCw } from "lucide-react";
import DashboardShell from "../../components/layout/DashboardShell";
import TrustChainGraph from "../../components/trust/TrustChainGraph";
import { useTrustChains } from "@/hooks";
import {
  Card,
  CardContent,
  Skeleton,
  Alert,
  AlertTitle,
  AlertDescription,
  Button,
} from "@/components/ui/shadcn";

/** Loading skeleton for the trust chains view. */
function TrustChainsSkeleton() {
  return (
    <div className="space-y-4">
      {Array.from({ length: 3 }).map((_, i) => (
        <Card key={i}>
          <CardContent className="p-5 space-y-3">
            <Skeleton className="h-5 w-48" />
            <div className="flex gap-3">
              {Array.from({ length: 4 }).map((_, j) => (
                <Skeleton key={j} className="h-10 w-28 rounded-md" />
              ))}
            </div>
            <Skeleton className="h-3 w-full" />
            <Skeleton className="h-3 w-2/3" />
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

export default function TrustChainsPage() {
  const { data, isLoading, error, refetch } = useTrustChains();

  return (
    <DashboardShell
      activePath="/trust-chains"
      title="Trust Chains"
      breadcrumbs={[
        { label: "Dashboard", href: "/" },
        { label: "Trust Chains" },
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
        {/* Description */}
        <p className="text-sm text-muted-foreground">
          EATP trust chain visualization showing genesis records, delegation
          chains, and current agent trust states. Each team has a genesis record
          from which agent delegations flow.
        </p>

        {/* Loading state */}
        {isLoading && <TrustChainsSkeleton />}

        {/* Error state */}
        {error && (
          <Alert variant="destructive">
            <AlertTitle>Failed to load trust chains</AlertTitle>
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

        {/* Data display */}
        {data && <TrustChainGraph chains={data.trust_chains} />}
      </div>
    </DashboardShell>
  );
}
