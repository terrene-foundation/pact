// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * NotificationListener -- invisible component that subscribes to WebSocket
 * events and feeds them into the NotificationProvider.
 *
 * This component must be rendered inside both the NotificationProvider and
 * any component tree where the useWebSocket hook can function. It does not
 * render any visible UI.
 */

"use client";

import { useCallback } from "react";
import { useWebSocket } from "../../lib/use-api";
import {
  useNotifications,
  eventToNotification,
} from "../../lib/notification-context";
import type { PlatformEvent } from "../../types/pact";

export default function NotificationListener() {
  const { addNotification } = useNotifications();

  const handleEvent = useCallback(
    (event: PlatformEvent) => {
      const notification = eventToNotification(event);
      if (notification) {
        addNotification(notification);
      }
    },
    [addNotification],
  );

  // Subscribe to WebSocket events; no UI rendered
  useWebSocket(handleEvent);

  return null;
}
