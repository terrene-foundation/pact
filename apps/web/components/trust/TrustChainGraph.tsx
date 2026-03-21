// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * TrustChainGraph -- visual tree showing genesis to delegations to agents.
 *
 * Renders trust chain entries as a hierarchical list grouped by team,
 * with color-coded status indicators:
 *   ACTIVE    = green
 *   SUSPENDED = yellow
 *   REVOKED   = red
 *   INACTIVE  = gray
 */

"use client";

import type { TrustChainSummary, AgentStatus } from "../../types/pact";
import StatusBadge from "../ui/StatusBadge";

interface TrustChainGraphProps {
  /** Trust chain entries to visualize. */
  chains: TrustChainSummary[];
}

/** Color map for the connection line indicators. */
const STATUS_LINE_COLORS: Record<AgentStatus, string> = {
  active: "border-green-400 bg-green-50",
  suspended: "border-yellow-400 bg-yellow-50",
  revoked: "border-red-400 bg-red-50",
  inactive: "border-gray-300 bg-gray-50",
};

/** Dot color for the tree node indicator. */
const STATUS_DOT_COLORS: Record<AgentStatus, string> = {
  active: "bg-green-500",
  suspended: "bg-yellow-500",
  revoked: "bg-red-500",
  inactive: "bg-gray-400",
};

/** Group chains by team_id for hierarchical display. */
function groupByTeam(
  chains: TrustChainSummary[],
): Map<string, TrustChainSummary[]> {
  const groups = new Map<string, TrustChainSummary[]>();
  for (const chain of chains) {
    const existing = groups.get(chain.team_id) ?? [];
    existing.push(chain);
    groups.set(chain.team_id, existing);
  }
  return groups;
}

/** Visual tree/list showing trust chain hierarchy. */
export default function TrustChainGraph({ chains }: TrustChainGraphProps) {
  if (chains.length === 0) {
    return (
      <div className="rounded-lg border border-gray-200 bg-white p-8 text-center text-gray-500">
        No trust chains found.
      </div>
    );
  }

  const grouped = groupByTeam(chains);

  return (
    <div className="space-y-6">
      {Array.from(grouped.entries()).map(([teamId, teamChains]) => (
        <div
          key={teamId}
          className="rounded-lg border border-gray-200 bg-white overflow-hidden"
        >
          {/* Team header (Genesis node) */}
          <div className="flex items-center gap-3 border-b border-gray-200 bg-gray-50 px-4 py-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-blue-100">
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
                  d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"
                />
              </svg>
            </div>
            <div>
              <p className="text-sm font-semibold text-gray-900">
                Genesis: Team {teamId}
              </p>
              <p className="text-xs text-gray-500">
                {teamChains.length} agent{teamChains.length !== 1 ? "s" : ""}{" "}
                delegated
              </p>
            </div>
          </div>

          {/* Agent delegation nodes */}
          <div className="divide-y divide-gray-100">
            {teamChains.map((chain) => (
              <div
                key={chain.agent_id}
                className={`flex items-center gap-4 border-l-4 px-4 py-3 ${STATUS_LINE_COLORS[chain.status]}`}
              >
                {/* Tree connector line + dot */}
                <div className="flex items-center gap-2" aria-hidden="true">
                  <div className="h-px w-4 bg-gray-300" />
                  <div
                    className={`h-3 w-3 rounded-full ${STATUS_DOT_COLORS[chain.status]}`}
                  />
                </div>

                {/* Agent info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <a
                      href={`/agents/${chain.agent_id}`}
                      className="text-sm font-medium text-gray-900 hover:text-blue-600 truncate"
                    >
                      {chain.name}
                    </a>
                    <StatusBadge value={chain.status} size="xs" />
                  </div>
                  <p className="text-xs text-gray-500 truncate">
                    ID: {chain.agent_id}
                  </p>
                </div>

                {/* Posture badge */}
                <div className="flex-shrink-0">
                  <StatusBadge value={chain.posture} size="xs" />
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
