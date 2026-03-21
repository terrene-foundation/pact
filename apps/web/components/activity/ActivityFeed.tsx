// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

"use client";

import { useState, useCallback } from "react";
import type { PlatformEvent, EventType } from "../../types/pact";
import { useWebSocket } from "../../lib/use-api";

/** Maximum events to keep in the feed (prevents unbounded memory). */
const MAX_EVENTS = 100;

/** Human-readable labels and icons for event types. */
const EVENT_CONFIG: Record<
  EventType,
  { label: string; icon: string; color: string }
> = {
  audit_anchor: {
    label: "Audit Anchor",
    icon: "\u{1F512}",
    color: "text-blue-600",
  },
  held_action: {
    label: "Action Held",
    icon: "\u{270B}",
    color: "text-gradient-held",
  },
  posture_change: {
    label: "Posture Change",
    icon: "\u{1F4CA}",
    color: "text-purple-600",
  },
  bridge_status: {
    label: "Bridge Update",
    icon: "\u{1F310}",
    color: "text-cyan-600",
  },
  verification_result: {
    label: "Verification",
    icon: "\u{2705}",
    color: "text-green-600",
  },
  workspace_transition: {
    label: "Workspace",
    icon: "\u{1F4C2}",
    color: "text-gray-600",
  },
};

/** Format a timestamp for display. */
function formatTime(timestamp: string): string {
  try {
    const date = new Date(timestamp);
    return date.toLocaleTimeString(undefined, {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return timestamp;
  }
}

/** Render the event description from its data payload. */
function describeEvent(event: PlatformEvent): string {
  const { event_type, data, source_agent_id } = event;

  switch (event_type) {
    case "audit_anchor":
      return `${source_agent_id} recorded audit anchor for "${data.action ?? "action"}"`;
    case "held_action":
      return `${source_agent_id}: "${data.action ?? "action"}" held — ${data.reason ?? "requires review"}`;
    case "posture_change":
      return `${source_agent_id} posture changed: ${data.from_posture ?? "?"} \u2192 ${data.to_posture ?? "?"}`;
    case "bridge_status":
      return `Bridge ${data.bridge_id ?? "?"} status: ${data.status ?? "updated"}`;
    case "verification_result":
      return `${source_agent_id}: "${data.action ?? "action"}" \u2192 ${data.level ?? "verified"}`;
    case "workspace_transition":
      return `Workspace ${data.workspace_id ?? "?"}: ${data.transition ?? "updated"}`;
    default:
      return `${source_agent_id}: ${event_type}`;
  }
}

/** Props for the ActivityFeed component. */
interface ActivityFeedProps {
  /** Maximum height of the feed container. Defaults to "400px". */
  maxHeight?: string;
  /** Filter to show only specific event types. */
  eventTypes?: EventType[];
  /** Compact mode for sidebar or small containers. */
  compact?: boolean;
}

/**
 * Real-time activity feed showing live platform events via WebSocket.
 *
 * Displays agent actions, verification results, held actions, posture changes,
 * and bridge updates as they happen. This is the primary visibility mechanism
 * for agents operating in the background.
 */
export default function ActivityFeed({
  maxHeight = "400px",
  eventTypes,
  compact = false,
}: ActivityFeedProps) {
  const [events, setEvents] = useState<PlatformEvent[]>([]);
  const [paused, setPaused] = useState(false);

  const handleEvent = useCallback(
    (event: PlatformEvent) => {
      if (paused) return;
      if (eventTypes && !eventTypes.includes(event.event_type)) return;

      setEvents((prev) => {
        const updated = [event, ...prev];
        return updated.slice(0, MAX_EVENTS);
      });
    },
    [paused, eventTypes],
  );

  const { connectionState } = useWebSocket(handleEvent);

  const connectionColor =
    connectionState === "connected"
      ? "bg-green-500"
      : connectionState === "connecting"
        ? "bg-yellow-500 animate-pulse-slow"
        : "bg-red-500";

  return (
    <div className="card p-0">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-care-border">
        <div className="flex items-center gap-2">
          <div
            className={`w-2 h-2 rounded-full ${connectionColor}`}
            aria-hidden="true"
          />
          <h3 className={compact ? "text-sm font-medium" : "font-semibold"}>
            Activity Feed
          </h3>
          {events.length > 0 && (
            <span className="text-xs text-care-muted">
              {events.length} events
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setPaused(!paused)}
            className="text-xs text-care-muted hover:text-gray-700 px-2 py-1 rounded hover:bg-gray-100"
          >
            {paused ? "Resume" : "Pause"}
          </button>
          {events.length > 0 && (
            <button
              onClick={() => setEvents([])}
              className="text-xs text-care-muted hover:text-gray-700 px-2 py-1 rounded hover:bg-gray-100"
            >
              Clear
            </button>
          )}
        </div>
      </div>

      {/* Feed -- live region announces new events to screen readers */}
      <div
        className="overflow-y-auto"
        style={{ maxHeight }}
        role="log"
        aria-live="polite"
        aria-label="Real-time activity feed"
      >
        {events.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-8 text-care-muted">
            <p className="text-sm">
              {connectionState === "connected"
                ? "Waiting for agent activity..."
                : "Connecting to platform..."}
            </p>
          </div>
        ) : (
          events.map((event) => {
            const config = EVENT_CONFIG[event.event_type];
            return (
              <div key={event.event_id} className="feed-item">
                <span className="text-lg flex-shrink-0" aria-hidden="true">
                  {config.icon}
                </span>
                <div className="flex-1 min-w-0">
                  <p
                    className={`${compact ? "text-xs" : "text-sm"} text-gray-800 truncate`}
                  >
                    {describeEvent(event)}
                  </p>
                  <div className="flex items-center gap-2 mt-0.5">
                    <span className={`text-xs ${config.color}`}>
                      {config.label}
                    </span>
                    <span className="text-xs text-care-muted">
                      {formatTime(event.timestamp)}
                    </span>
                    {event.source_team_id && (
                      <span className="text-xs text-care-muted">
                        {event.source_team_id}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
