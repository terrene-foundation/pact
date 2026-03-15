// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * DashboardShell -- wrapper layout providing Sidebar + Header for all pages.
 *
 * Every dashboard page should wrap its content in this shell to get
 * consistent navigation, breadcrumbs, and responsive sidebar behavior.
 */

"use client";

import { useState, useEffect } from "react";
import Sidebar from "./Sidebar";
import Header, { type Breadcrumb, type ConnectionStatus } from "./Header";
import { useAuth } from "../../lib/auth-context";
import { NotificationListener, ToastContainer } from "../notifications";

interface DashboardShellProps {
  /** Current page path for sidebar highlighting. */
  activePath: string;
  /** Page title displayed in the header. */
  title: string;
  /** Breadcrumb trail for the header. */
  breadcrumbs?: Breadcrumb[];
  /** Optional action buttons for the header right side. */
  actions?: React.ReactNode;
  /** WebSocket connection status to display in the header. */
  connectionStatus?: ConnectionStatus;
  /** Page content. */
  children: React.ReactNode;
}

/** Dashboard layout shell with sidebar, header, and auth guard. */
export default function DashboardShell({
  activePath,
  title,
  breadcrumbs = [],
  actions,
  connectionStatus,
  children,
}: DashboardShellProps) {
  const { isAuthenticated, isLoaded } = useAuth();

  // Start collapsed on mobile (sidebar hidden), expanded on desktop
  const [sidebarCollapsed, setSidebarCollapsed] = useState(true);

  // Auth guard: redirect to /login if not authenticated
  useEffect(() => {
    if (isLoaded && !isAuthenticated) {
      window.location.href = "/login";
    }
  }, [isLoaded, isAuthenticated]);

  // Show loading spinner while auth state is being resolved
  if (!isLoaded) {
    return (
      <div className="flex h-screen items-center justify-center bg-gray-50">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-care-primary border-t-transparent" />
      </div>
    );
  }

  // Auth state loaded but not authenticated -- will redirect via useEffect
  if (!isAuthenticated) {
    return null;
  }

  return (
    <div className="flex h-screen overflow-hidden bg-gray-50">
      {/* WebSocket -> notification bridge (renders no UI) */}
      <NotificationListener />

      {/* Sidebar */}
      <Sidebar
        activePath={activePath}
        collapsed={sidebarCollapsed}
        onToggle={() => setSidebarCollapsed((prev) => !prev)}
      />

      {/* Main content area */}
      <div className="flex flex-1 flex-col overflow-hidden">
        <Header
          title={title}
          breadcrumbs={breadcrumbs}
          connectionStatus={connectionStatus}
          actions={actions}
          onMenuToggle={() => setSidebarCollapsed((prev) => !prev)}
        />
        <main id="main-content" className="flex-1 overflow-y-auto p-6">
          {children}
        </main>
      </div>

      {/* Toast popups for high-priority notifications */}
      <ToastContainer />
    </div>
  );
}
