// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * BridgeConnections -- visual bridge links between workspaces.
 *
 * Displays Cross-Functional Bridges as a list of connections between teams,
 * showing bridge type (Standing, Scoped, Ad-Hoc), status, and purpose.
 */

"use client";

import type { Bridge } from "../../types/pact";
import StatusBadge from "../ui/StatusBadge";

interface BridgeConnectionsProps {
  /** Bridge entries to display. */
  bridges: Bridge[];
}

/** Bridge type labels (canonical names from Terrene naming). */
const BRIDGE_TYPE_LABELS: Record<string, string> = {
  standing: "Standing",
  scoped: "Scoped",
  ad_hoc: "Ad-Hoc",
};

/** Bridge type badge colors. */
const BRIDGE_TYPE_COLORS: Record<string, string> = {
  standing: "bg-blue-100 text-blue-700 border-blue-200",
  scoped: "bg-purple-100 text-purple-700 border-purple-200",
  ad_hoc: "bg-gray-100 text-gray-700 border-gray-200",
};

/** Format an ISO timestamp to a short date. */
function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  } catch {
    return iso;
  }
}

/** Visual bridge connections display. */
export default function BridgeConnections({ bridges }: BridgeConnectionsProps) {
  if (bridges.length === 0) {
    return (
      <div className="rounded-lg border border-gray-200 bg-white p-6 text-center text-sm text-gray-500">
        No Cross-Functional Bridges established.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <h3 className="text-sm font-semibold text-gray-900">
        Cross-Functional Bridges
      </h3>
      <div className="space-y-2">
        {bridges.map((bridge) => (
          <div
            key={bridge.bridge_id}
            className="flex items-center gap-3 rounded-lg border border-gray-200 bg-white px-4 py-3"
          >
            {/* Source team */}
            <div className="flex items-center gap-2">
              <div className="flex h-7 w-7 items-center justify-center rounded-full bg-blue-100">
                <span className="text-xs font-bold text-blue-700">
                  {bridge.source_team_id.charAt(0).toUpperCase()}
                </span>
              </div>
              <span className="text-sm font-medium text-gray-900">
                {bridge.source_team_id}
              </span>
            </div>

            {/* Connection arrow */}
            <div className="flex flex-1 items-center gap-1">
              <div className="h-px flex-1 bg-gray-300" />
              <div className="flex flex-col items-center">
                <span
                  className={`rounded-full border px-2 py-0.5 text-xs font-medium ${
                    BRIDGE_TYPE_COLORS[bridge.bridge_type] ??
                    "bg-gray-100 text-gray-700 border-gray-200"
                  }`}
                >
                  {BRIDGE_TYPE_LABELS[bridge.bridge_type] ?? bridge.bridge_type}
                </span>
                <StatusBadge value={bridge.status} size="xs" />
              </div>
              <div className="h-px flex-1 bg-gray-300" />
            </div>

            {/* Target team */}
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-gray-900">
                {bridge.target_team_id}
              </span>
              <div className="flex h-7 w-7 items-center justify-center rounded-full bg-green-100">
                <span className="text-xs font-bold text-green-700">
                  {bridge.target_team_id.charAt(0).toUpperCase()}
                </span>
              </div>
            </div>

            {/* Purpose + date (hidden on small screens) */}
            <div className="hidden lg:block lg:min-w-[200px]">
              <p className="text-xs text-gray-600 truncate">{bridge.purpose}</p>
              <p className="text-xs text-gray-400">
                Created {formatDate(bridge.created_at)}
              </p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
