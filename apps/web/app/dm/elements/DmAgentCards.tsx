// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * DmAgentCards -- grid of agent cards for the DM team.
 *
 * Each card shows agent name, role, posture badge, status badge,
 * actions today, and approval rate. Clicking a card links to the
 * agent detail page.
 */

"use client";

import PostureBadge from "../../../components/agents/PostureBadge";
import StatusBadge from "../../../components/ui/StatusBadge";
import type { DmAgentSummary } from "../../../types/pact";

interface DmAgentCardsProps {
  agents: DmAgentSummary[];
}

/** Grid of DM agent cards with quick stats. */
export default function DmAgentCards({ agents }: DmAgentCardsProps) {
  if (agents.length === 0) {
    return (
      <div className="rounded-lg border border-gray-200 bg-white p-8 text-center text-gray-500">
        No agents found in the DM team.
      </div>
    );
  }

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {agents.map((agent) => (
        <a
          key={agent.agent_id}
          href={`/agents/${agent.agent_id}`}
          className="group rounded-lg border border-gray-200 bg-white p-5 transition-shadow hover:shadow-md"
        >
          {/* Header: name + status */}
          <div className="mb-3 flex items-start justify-between">
            <div className="min-w-0 flex-1">
              <h3 className="truncate text-sm font-semibold text-gray-900 group-hover:text-blue-600">
                {agent.name}
              </h3>
              <p className="text-xs text-gray-500">{agent.role}</p>
            </div>
            <StatusBadge value={agent.status} size="xs" />
          </div>

          {/* Posture badge */}
          <div className="mb-3">
            <PostureBadge posture={agent.posture} size="sm" />
          </div>

          {/* Quick stats row */}
          <div className="flex items-center justify-between border-t border-gray-100 pt-3">
            <div className="text-center">
              <p className="text-lg font-semibold text-gray-900">
                {agent.tasks_submitted ?? 0}
              </p>
              <p className="text-xs text-gray-500">Tasks submitted</p>
            </div>
            <div className="text-center">
              <p className="text-lg font-semibold text-gray-900">
                {agent.tasks_completed ?? 0}
              </p>
              <p className="text-xs text-gray-500">Completed</p>
            </div>
            <div className="text-center">
              <p className="text-lg font-semibold text-gray-900">
                {agent.tasks_held ?? 0}
              </p>
              <p className="text-xs text-gray-500">Held</p>
            </div>
          </div>
        </a>
      ))}
    </div>
  );
}
