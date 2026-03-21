// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * NotificationItem -- single notification row inside the bell dropdown.
 *
 * Displays: priority-colored icon, title, description (truncated), relative
 * timestamp, and read/unread indicator. Clicking navigates to the relevant
 * page and marks the notification as read.
 */

"use client";

import type {
  Notification,
  NotificationPriority,
} from "../../../lib/notification-context";
import type { EventType } from "../../../types/pact";

// ---------------------------------------------------------------------------
// Visual Configuration
// ---------------------------------------------------------------------------

/** SVG path data for notification icons, keyed by event type. */
const EVENT_ICON_PATHS: Record<EventType, string> = {
  held_action:
    "M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z",
  verification_result:
    "M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z",
  posture_change: "M13 7h8m0 0v8m0-8l-8 8-4-4-6 6",
  bridge_status: "M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4",
  audit_anchor:
    "M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z",
  workspace_transition:
    "M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10",
};

/** Icon background color by priority level. */
const PRIORITY_ICON_COLORS: Record<NotificationPriority, string> = {
  critical: "bg-urgency-critical text-white",
  high: "bg-urgency-high text-white",
  medium: "bg-urgency-medium text-white",
  low: "bg-gray-200 text-gray-600",
};

/** Left border accent by priority level. */
const PRIORITY_BORDER_COLORS: Record<NotificationPriority, string> = {
  critical: "border-l-urgency-critical",
  high: "border-l-urgency-high",
  medium: "border-l-urgency-medium",
  low: "border-l-transparent",
};

// ---------------------------------------------------------------------------
// Relative Time
// ---------------------------------------------------------------------------

/** Format a timestamp as a relative time string (e.g., "2m ago", "1h ago"). */
function relativeTime(timestamp: string): string {
  try {
    const now = Date.now();
    const then = new Date(timestamp).getTime();
    const diffSeconds = Math.floor((now - then) / 1000);

    if (diffSeconds < 10) return "just now";
    if (diffSeconds < 60) return `${diffSeconds}s ago`;
    const diffMinutes = Math.floor(diffSeconds / 60);
    if (diffMinutes < 60) return `${diffMinutes}m ago`;
    const diffHours = Math.floor(diffMinutes / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    const diffDays = Math.floor(diffHours / 24);
    return `${diffDays}d ago`;
  } catch {
    return "";
  }
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface NotificationItemProps {
  notification: Notification;
  onRead: (id: string) => void;
}

export default function NotificationItem({
  notification,
  onRead,
}: NotificationItemProps) {
  const { id, title, description, priority, eventType, timestamp, read, href } =
    notification;

  const handleClick = () => {
    if (!read) onRead(id);
    window.location.href = href;
  };

  return (
    <button
      onClick={handleClick}
      className={`
        w-full text-left flex items-start gap-3 px-4 py-3
        border-l-2 ${PRIORITY_BORDER_COLORS[priority]}
        ${read ? "bg-white" : "bg-blue-50/50"}
        hover:bg-gray-50 transition-colors
        border-b border-care-border last:border-b-0
      `}
    >
      {/* Icon */}
      <div
        className={`flex-shrink-0 mt-0.5 flex h-7 w-7 items-center justify-center rounded-full ${PRIORITY_ICON_COLORS[priority]}`}
      >
        <svg
          className="h-3.5 w-3.5"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d={EVENT_ICON_PATHS[eventType]}
          />
        </svg>
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-start justify-between gap-2">
          <p
            className={`text-sm truncate ${read ? "text-gray-700" : "text-gray-900 font-medium"}`}
          >
            {title}
          </p>
          {!read && (
            <span className="flex-shrink-0 mt-1 h-2 w-2 rounded-full bg-care-primary" />
          )}
        </div>
        <p className="text-xs text-care-muted truncate mt-0.5">{description}</p>
        <p className="text-xs text-care-muted-light mt-1">
          {relativeTime(timestamp)}
        </p>
      </div>
    </button>
  );
}
