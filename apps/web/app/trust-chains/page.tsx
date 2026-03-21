// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * Trust Chains page -- displays all trust chains from the PACT API
 * as a visual tree grouped by team, showing genesis to delegation to agents.
 */

"use client";

import DashboardShell from "../../components/layout/DashboardShell";
import TrustChainGraph from "../../components/trust/TrustChainGraph";
import ErrorAlert from "../../components/ui/ErrorAlert";
import { TableSkeleton } from "../../components/ui/Skeleton";
import { useApi } from "../../lib/use-api";

export default function TrustChainsPage() {
  const { data, loading, error, refetch } = useApi(
    (client) => client.listTrustChains(),
    [],
  );

  return (
    <DashboardShell
      activePath="/trust-chains"
      title="Trust Chains"
      breadcrumbs={[
        { label: "Dashboard", href: "/" },
        { label: "Trust Chains" },
      ]}
    >
      <div className="space-y-6">
        {/* Description */}
        <p className="text-sm text-gray-600">
          EATP trust chain visualization showing genesis records, delegation
          chains, and current agent trust states. Each team has a genesis record
          from which agent delegations flow.
        </p>

        {/* Loading state */}
        {loading && <TableSkeleton rows={6} />}

        {/* Error state */}
        {error && <ErrorAlert message={error} onRetry={refetch} />}

        {/* Data display */}
        {data && <TrustChainGraph chains={data.trust_chains} />}
      </div>
    </DashboardShell>
  );
}
