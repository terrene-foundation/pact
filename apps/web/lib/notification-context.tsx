// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * NotificationProvider -- React context that converts real-time WebSocket
 * PlatformEvents into user-facing notifications with priority levels.
 *
 * Priority mapping:
 *   - held_action           -> HIGH ("Action held: {action} by {agent}")
 *   - verification_result   -> CRITICAL when BLOCKED, LOW otherwise
 *   - posture_change        -> MEDIUM
 *   - bridge_status         -> LOW
 *   - audit_anchor          -> LOW (informational)
 *   - workspace_transition  -> LOW (informational)
 *
 * Stores up to MAX_NOTIFICATIONS in FIFO order. Tracks unread count.
 * Provides addNotification, markAsRead, markAllAsRead, clearAll.
 */

"use client";

import {
  createContext,
  useContext,
  useState,
  useCallback,
  useRef,
  type ReactNode,
} from "react";
import type { PlatformEvent, EventType } from "../types/pact";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** Notification priority level. */
export type NotificationPriority = "critical" | "high" | "medium" | "low";

/** A user-facing notification derived from a PlatformEvent. */
export interface Notification {
  /** Unique identifier (matches event_id). */
  id: string;
  /** Short title summarizing the notification. */
  title: string;
  /** Longer description with context. */
  description: string;
  /** Priority determines visual treatment and toast behavior. */
  priority: NotificationPriority;
  /** Original event type for icon mapping. */
  eventType: EventType;
  /** ISO timestamp from the source event. */
  timestamp: string;
  /** Whether the user has seen this notification. */
  read: boolean;
  /** Navigation target when the notification is clicked. */
  href: string;
  /** Source agent ID from the event. */
  sourceAgentId: string;
  /** Source team ID from the event. */
  sourceTeamId: string;
}

/** Shape of the notification context value. */
export interface NotificationContextValue {
  /** All stored notifications, newest first. */
  notifications: Notification[];
  /** Count of unread notifications. */
  unreadCount: number;
  /** Count of unread held_action notifications (for sidebar badge). */
  pendingApprovalCount: number;
  /** Add a notification (typically called by the WebSocket listener). */
  addNotification: (notification: Notification) => void;
  /** Mark a single notification as read by its ID. */
  markAsRead: (id: string) => void;
  /** Mark all notifications as read. */
  markAllAsRead: () => void;
  /** Remove all notifications. */
  clearAll: () => void;
  /** Whether a new notification just arrived (for pulse animation). */
  hasNewArrival: boolean;
  /** Reset the new-arrival flag (after animation completes). */
  clearNewArrival: () => void;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Maximum notifications to keep in state (FIFO). */
const MAX_NOTIFICATIONS = 50;

// ---------------------------------------------------------------------------
// Event-to-Notification Conversion
// ---------------------------------------------------------------------------

/**
 * Convert a PlatformEvent into a user-facing Notification.
 * Returns null for event types that should not generate notifications.
 */
export function eventToNotification(event: PlatformEvent): Notification | null {
  const {
    event_id,
    event_type,
    data,
    source_agent_id,
    source_team_id,
    timestamp,
  } = event;

  switch (event_type) {
    case "held_action": {
      const action = String(data.action ?? "Unknown action");
      const reason = String(data.reason ?? "Requires review");
      return {
        id: event_id,
        title: `Action held: ${action}`,
        description: `${source_agent_id} attempted "${action}" -- ${reason}`,
        priority: "high",
        eventType: event_type,
        timestamp,
        read: false,
        href: "/approvals",
        sourceAgentId: source_agent_id,
        sourceTeamId: source_team_id,
      };
    }

    case "verification_result": {
      const level = String(data.level ?? "UNKNOWN");
      const action = String(data.action ?? "Unknown action");
      if (level === "BLOCKED") {
        return {
          id: event_id,
          title: `Action BLOCKED: ${action}`,
          description: `${source_agent_id} was blocked from "${action}" -- violates hard constraint`,
          priority: "critical",
          eventType: event_type,
          timestamp,
          read: false,
          href: "/verification",
          sourceAgentId: source_agent_id,
          sourceTeamId: source_team_id,
        };
      }
      // Non-BLOCKED verification results are informational
      return {
        id: event_id,
        title: `Verification: ${action}`,
        description: `${source_agent_id}: "${action}" verified as ${level}`,
        priority: "low",
        eventType: event_type,
        timestamp,
        read: false,
        href: "/verification",
        sourceAgentId: source_agent_id,
        sourceTeamId: source_team_id,
      };
    }

    case "posture_change": {
      const from = String(data.from_posture ?? "unknown");
      const to = String(data.to_posture ?? "unknown");
      return {
        id: event_id,
        title: `Posture changed: ${from} to ${to}`,
        description: `${source_agent_id} posture updated from ${from} to ${to}`,
        priority: "medium",
        eventType: event_type,
        timestamp,
        read: false,
        href: "/agents",
        sourceAgentId: source_agent_id,
        sourceTeamId: source_team_id,
      };
    }

    case "bridge_status": {
      const bridgeId = String(data.bridge_id ?? "unknown");
      const status = String(data.status ?? "updated");
      return {
        id: event_id,
        title: `Bridge ${status}`,
        description: `Bridge ${bridgeId} status changed to ${status}`,
        priority: "low",
        eventType: event_type,
        timestamp,
        read: false,
        href: "/bridges",
        sourceAgentId: source_agent_id,
        sourceTeamId: source_team_id,
      };
    }

    case "audit_anchor": {
      const action = String(data.action ?? "action");
      return {
        id: event_id,
        title: `Audit anchor recorded`,
        description: `${source_agent_id} recorded audit anchor for "${action}"`,
        priority: "low",
        eventType: event_type,
        timestamp,
        read: false,
        href: "/audit",
        sourceAgentId: source_agent_id,
        sourceTeamId: source_team_id,
      };
    }

    case "workspace_transition": {
      const workspaceId = String(data.workspace_id ?? "unknown");
      const transition = String(data.transition ?? "updated");
      return {
        id: event_id,
        title: `Workspace ${transition}`,
        description: `Workspace ${workspaceId} transitioned to ${transition}`,
        priority: "low",
        eventType: event_type,
        timestamp,
        read: false,
        href: "/workspaces",
        sourceAgentId: source_agent_id,
        sourceTeamId: source_team_id,
      };
    }

    default:
      return null;
  }
}

// ---------------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------------

const NotificationContext = createContext<NotificationContextValue | null>(
  null,
);

/** Hook to access the notification context. Throws if used outside the provider. */
export function useNotifications(): NotificationContextValue {
  const ctx = useContext(NotificationContext);
  if (!ctx) {
    throw new Error(
      "useNotifications must be used within a <NotificationProvider>",
    );
  }
  return ctx;
}

/** Default no-op context value for components that may render outside the provider. */
const NOOP_CONTEXT: NotificationContextValue = {
  notifications: [],
  unreadCount: 0,
  pendingApprovalCount: 0,
  addNotification: () => {},
  markAsRead: () => {},
  markAllAsRead: () => {},
  clearAll: () => {},
  hasNewArrival: false,
  clearNewArrival: () => {},
};

/**
 * Safe version of useNotifications that returns default values
 * instead of throwing when rendered outside the provider.
 * Useful for components (e.g., Sidebar) that may be tested in isolation.
 */
export function useNotificationsSafe(): NotificationContextValue {
  const ctx = useContext(NotificationContext);
  return ctx ?? NOOP_CONTEXT;
}

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

interface NotificationProviderProps {
  children: ReactNode;
}

/**
 * Wraps the application to provide notification state. Does NOT subscribe
 * to WebSocket events itself -- that is done by NotificationListener,
 * which must be rendered as a child of both this provider and a WebSocket
 * connection context.
 */
export function NotificationProvider({ children }: NotificationProviderProps) {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [hasNewArrival, setHasNewArrival] = useState(false);
  const newArrivalTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const addNotification = useCallback((notification: Notification) => {
    setNotifications((prev) => {
      // Deduplicate by ID
      if (prev.some((n) => n.id === notification.id)) return prev;
      const updated = [notification, ...prev];
      return updated.slice(0, MAX_NOTIFICATIONS);
    });

    // Signal new arrival for pulse animation
    setHasNewArrival(true);
    if (newArrivalTimer.current) {
      clearTimeout(newArrivalTimer.current);
    }
    newArrivalTimer.current = setTimeout(() => {
      setHasNewArrival(false);
    }, 2000);
  }, []);

  const markAsRead = useCallback((id: string) => {
    setNotifications((prev) =>
      prev.map((n) => (n.id === id ? { ...n, read: true } : n)),
    );
  }, []);

  const markAllAsRead = useCallback(() => {
    setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
  }, []);

  const clearAll = useCallback(() => {
    setNotifications([]);
    setHasNewArrival(false);
  }, []);

  const clearNewArrival = useCallback(() => {
    setHasNewArrival(false);
  }, []);

  const unreadCount = notifications.filter((n) => !n.read).length;
  const pendingApprovalCount = notifications.filter(
    (n) => !n.read && n.eventType === "held_action",
  ).length;

  return (
    <NotificationContext.Provider
      value={{
        notifications,
        unreadCount,
        pendingApprovalCount,
        addNotification,
        markAsRead,
        markAllAsRead,
        clearAll,
        hasNewArrival,
        clearNewArrival,
      }}
    >
      {children}
    </NotificationContext.Provider>
  );
}
