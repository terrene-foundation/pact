// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * WorkspaceCard -- card showing workspace state, CO phase, and metadata.
 *
 * Displays workspace identity, current lifecycle state, and CO methodology
 * phase with visual indicators.
 */

"use client";

import type { Workspace, WorkspacePhase } from "../../types/pact";
import StatusBadge from "../ui/StatusBadge";

interface WorkspaceCardProps {
  /** Workspace data. */
  workspace: Workspace;
}

/** CO phase labels and colors. */
const PHASE_CONFIG: Record<
  WorkspacePhase,
  { label: string; color: string; step: number }
> = {
  analyze: { label: "Analyze", color: "bg-blue-500", step: 1 },
  plan: { label: "Plan", color: "bg-indigo-500", step: 2 },
  implement: { label: "Implement", color: "bg-purple-500", step: 3 },
  validate: { label: "Validate", color: "bg-amber-500", step: 4 },
  codify: { label: "Codify", color: "bg-green-500", step: 5 },
};

const TOTAL_PHASES = 5;

/** Workspace card for the workspace status grid. */
export default function WorkspaceCard({ workspace }: WorkspaceCardProps) {
  const phaseConfig = PHASE_CONFIG[workspace.phase];

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-5 transition-shadow hover:shadow-md">
      {/* Header: name + state badge */}
      <div className="mb-3 flex items-start justify-between">
        <div className="min-w-0 flex-1">
          <h3 className="text-sm font-semibold text-gray-900 truncate">
            {workspace.path.split("/").pop() ?? workspace.id}
          </h3>
          <p className="text-xs text-gray-500 truncate">
            {workspace.description}
          </p>
        </div>
        <StatusBadge value={workspace.state} size="xs" />
      </div>

      {/* CO Phase indicator */}
      <div className="mb-3">
        <div className="mb-1 flex items-center justify-between">
          <span className="text-xs font-medium text-gray-600">CO Phase</span>
          <span className="text-xs font-semibold text-gray-900">
            {phaseConfig.label}
          </span>
        </div>
        {/* Phase progress dots */}
        <div
          className="flex gap-1.5"
          role="img"
          aria-label={`CO phase: ${phaseConfig.label}, step ${phaseConfig.step} of ${TOTAL_PHASES}`}
        >
          {Object.values(PHASE_CONFIG).map((phase) => (
            <div
              key={phase.label}
              className={`h-1.5 flex-1 rounded-full transition-colors ${
                phase.step <= phaseConfig.step
                  ? phaseConfig.color
                  : "bg-gray-200"
              }`}
              aria-hidden="true"
            />
          ))}
        </div>
      </div>

      {/* Metadata */}
      <div className="flex items-center justify-between text-xs text-gray-400">
        <span>Team: {workspace.team_id}</span>
        <span>ID: {workspace.id.slice(0, 8)}</span>
      </div>
    </div>
  );
}
