// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * ToastContainer -- renders toast popups for HIGH and CRITICAL notifications.
 *
 * Toasts appear in the bottom-right corner and auto-dismiss after 5 seconds.
 * CRITICAL toasts have a red left border; HIGH toasts have orange.
 * Clicking a toast navigates to the relevant page.
 * Stacks up to 3 toasts, newest on top.
 */

"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import type { Notification } from "../../lib/notification-context";
import { useNotifications } from "../../lib/notification-context";
import type { EventType } from "../../types/pact";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Maximum toasts displayed simultaneously. */
const MAX_TOASTS = 3;

/** Auto-dismiss duration in milliseconds. */
const AUTO_DISMISS_MS = 5000;

// ---------------------------------------------------------------------------
// Visual Configuration
// ---------------------------------------------------------------------------

const TOAST_BORDER_COLORS: Record<string, string> = {
  critical: "border-l-urgency-critical",
  high: "border-l-urgency-high",
};

const TOAST_ICON_COLORS: Record<string, string> = {
  critical: "text-urgency-critical",
  high: "text-urgency-high",
};

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

// ---------------------------------------------------------------------------
// Internal Toast Item
// ---------------------------------------------------------------------------

interface ToastEntry {
  notification: Notification;
  /** Timer ID for auto-dismiss. */
  timerId: ReturnType<typeof setTimeout>;
}

interface ToastItemProps {
  notification: Notification;
  onDismiss: (id: string) => void;
}

function ToastItem({ notification, onDismiss }: ToastItemProps) {
  const { id, title, description, priority, eventType, href } = notification;

  const borderColor = TOAST_BORDER_COLORS[priority] ?? "border-l-urgency-high";
  const iconColor = TOAST_ICON_COLORS[priority] ?? "text-urgency-high";

  const handleClick = () => {
    onDismiss(id);
    window.location.href = href;
  };

  return (
    <div
      role="alert"
      className={`
        flex items-start gap-3 rounded-lg border border-care-border bg-white
        p-4 shadow-lg border-l-4 ${borderColor}
        animate-slide-in cursor-pointer
        hover:shadow-xl transition-shadow
        w-80 max-w-[calc(100vw-2rem)]
      `}
      onClick={handleClick}
    >
      {/* Icon */}
      <svg
        className={`h-5 w-5 flex-shrink-0 mt-0.5 ${iconColor}`}
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

      {/* Content */}
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-gray-900 truncate">{title}</p>
        <p className="text-xs text-care-muted mt-0.5 truncate">{description}</p>
      </div>

      {/* Close button */}
      <button
        onClick={(e) => {
          e.stopPropagation();
          onDismiss(id);
        }}
        className="flex-shrink-0 rounded p-0.5 text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
        aria-label="Dismiss notification"
      >
        <svg
          className="h-4 w-4"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M6 18L18 6M6 6l12 12"
          />
        </svg>
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// ToastContainer
// ---------------------------------------------------------------------------

/**
 * Listens to the notification context and shows toast popups for high-priority
 * notifications. Must be rendered inside NotificationProvider.
 */
export default function ToastContainer() {
  const { notifications } = useNotifications();
  const [toasts, setToasts] = useState<ToastEntry[]>([]);
  const seenIds = useRef<Set<string>>(new Set());

  const dismissToast = useCallback((id: string) => {
    setToasts((prev) => {
      const entry = prev.find((t) => t.notification.id === id);
      if (entry) clearTimeout(entry.timerId);
      return prev.filter((t) => t.notification.id !== id);
    });
  }, []);

  // Watch for new high/critical notifications
  useEffect(() => {
    if (notifications.length === 0) return;

    const newest = notifications[0];
    if (!newest) return;

    // Only show toast for critical and high priority, and only once per ID
    if (seenIds.current.has(newest.id)) return;
    if (newest.priority !== "critical" && newest.priority !== "high") {
      seenIds.current.add(newest.id);
      return;
    }

    seenIds.current.add(newest.id);

    const timerId = setTimeout(() => {
      dismissToast(newest.id);
    }, AUTO_DISMISS_MS);

    setToasts((prev) => {
      const updated = [{ notification: newest, timerId }, ...prev];
      // If we exceed max, dismiss the oldest
      if (updated.length > MAX_TOASTS) {
        const removed = updated.slice(MAX_TOASTS);
        removed.forEach((entry) => clearTimeout(entry.timerId));
        return updated.slice(0, MAX_TOASTS);
      }
      return updated;
    });
  }, [notifications, dismissToast]);

  // Cleanup timers on unmount
  useEffect(() => {
    return () => {
      toasts.forEach((entry) => clearTimeout(entry.timerId));
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (toasts.length === 0) return null;

  return (
    <div
      className="fixed bottom-4 right-4 z-50 flex flex-col gap-2"
      aria-live="polite"
      aria-label="Notifications"
    >
      {toasts.map((entry) => (
        <ToastItem
          key={entry.notification.id}
          notification={entry.notification}
          onDismiss={dismissToast}
        />
      ))}
    </div>
  );
}
