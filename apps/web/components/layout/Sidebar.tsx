// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * Sidebar -- navigation sidebar with links to all dashboard sections.
 *
 * Sections:
 *   - Overview (home)
 *   - Trust Chains
 *   - Constraint Envelopes
 *   - Workspaces
 *   - Agents
 *   - Bridges
 *   - Verification
 *   - Shadow (ShadowEnforcer)
 *   - Audit Trail
 *   - Approvals
 *   - Cost Report
 *
 * Responsive behavior:
 *   - Desktop (lg+): always visible, collapsible to icon-only mode
 *   - Mobile/tablet (<lg): hidden by default, shown as overlay when toggled
 */

"use client";

import { useNotificationsSafe } from "../../lib/notification-context";

/** Navigation item definition. */
export interface NavItem {
  /** Display label. */
  label: string;
  /** URL path for the link. */
  href: string;
  /** SVG path data for the icon (24x24 viewBox). */
  iconPath: string;
}

/** Default dashboard navigation items. */
export const DASHBOARD_NAV: NavItem[] = [
  {
    label: "Overview",
    href: "/",
    iconPath:
      "M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6",
  },
  {
    label: "Trust Chains",
    href: "/trust-chains",
    iconPath:
      "M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1",
  },
  {
    label: "Envelopes",
    href: "/envelopes",
    iconPath:
      "M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z",
  },
  {
    label: "Workspaces",
    href: "/workspaces",
    iconPath:
      "M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10",
  },
  {
    label: "Agents",
    href: "/agents",
    iconPath:
      "M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z",
  },
  {
    label: "DM Team",
    href: "/dm",
    iconPath:
      "M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z",
  },
  {
    label: "Bridges",
    href: "/bridges",
    iconPath: "M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4",
  },
  {
    label: "Verification",
    href: "/verification",
    iconPath:
      "M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4",
  },
  {
    label: "Shadow",
    href: "/shadow",
    iconPath:
      "M15 12a3 3 0 11-6 0 3 3 0 016 0z M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z",
  },
  {
    label: "Audit Trail",
    href: "/audit",
    iconPath:
      "M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z",
  },
  {
    label: "Approvals",
    href: "/approvals",
    iconPath: "M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z",
  },
  {
    label: "Cost Report",
    href: "/cost-report",
    iconPath:
      "M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z",
  },
];

interface SidebarProps {
  /** Currently active path for highlighting. */
  activePath?: string;
  /** Navigation items to display. Defaults to DASHBOARD_NAV. */
  items?: NavItem[];
  /** Whether the sidebar is collapsed. On mobile this controls overlay visibility. */
  collapsed?: boolean;
  /** Callback when collapse state changes. */
  onToggle?: () => void;
}

/** Navigation sidebar for the PACT dashboard. */
export default function Sidebar({
  activePath = "/",
  items = DASHBOARD_NAV,
  collapsed = false,
  onToggle,
}: SidebarProps) {
  // Pull pending approval count from notification context for badge display.
  // Uses the safe variant that returns defaults outside the provider.
  const { pendingApprovalCount, hasNewArrival } = useNotificationsSafe();
  return (
    <>
      {/* Mobile overlay backdrop */}
      {!collapsed && (
        <div
          className="fixed inset-0 z-30 bg-black/30 lg:hidden"
          onClick={onToggle}
          onKeyDown={(e) => {
            if (e.key === "Escape" && onToggle) onToggle();
          }}
          role="button"
          tabIndex={-1}
          aria-label="Close navigation menu"
        />
      )}

      <aside
        className={`
          flex flex-col border-r border-gray-200 bg-white transition-all duration-200
          fixed inset-y-0 left-0 z-40 lg:static lg:z-auto
          ${collapsed ? "-translate-x-full lg:translate-x-0 lg:w-16" : "translate-x-0 w-64"}
        `}
      >
        {/* Header */}
        <div className="flex h-16 items-center justify-between border-b border-gray-200 px-4">
          {(!collapsed || typeof window === "undefined") && (
            <div className="flex items-center gap-2">
              <div className="h-8 w-8 rounded-lg bg-blue-600 flex items-center justify-center">
                <span className="text-sm font-bold text-white">C</span>
              </div>
              <span className="text-lg font-semibold text-gray-900">PACT</span>
            </div>
          )}
          {onToggle && (
            <button
              onClick={onToggle}
              className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
              aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            >
              <svg
                className="h-5 w-5"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
                aria-hidden="true"
              >
                {collapsed ? (
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M13 5l7 7-7 7M5 5l7 7-7 7"
                  />
                ) : (
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M11 19l-7-7 7-7m8 14l-7-7 7-7"
                  />
                )}
              </svg>
            </button>
          )}
        </div>

        {/* Navigation */}
        <nav
          aria-label="Main navigation"
          className="flex-1 overflow-y-auto p-3"
        >
          <ul className="space-y-1">
            {items.map((item) => {
              const isActive = activePath === item.href;
              return (
                <li key={item.href}>
                  <a
                    href={item.href}
                    className={`relative flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                      isActive
                        ? "bg-blue-50 text-blue-700"
                        : "text-gray-700 hover:bg-gray-100 hover:text-gray-900"
                    }`}
                    title={collapsed ? item.label : undefined}
                    aria-label={collapsed ? item.label : undefined}
                    aria-current={isActive ? "page" : undefined}
                  >
                    <svg
                      className="h-5 w-5 flex-shrink-0"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                      aria-hidden="true"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d={item.iconPath}
                      />
                    </svg>
                    {!collapsed && <span className="flex-1">{item.label}</span>}
                    {/* Approvals badge -- shows pending held_action count */}
                    {!collapsed &&
                      item.href === "/approvals" &&
                      pendingApprovalCount > 0 && (
                        <span
                          className={`ml-auto inline-flex h-5 min-w-[1.25rem] items-center justify-center rounded-full bg-urgency-critical px-1.5 text-[10px] font-bold text-white ${
                            hasNewArrival ? "animate-pulse-slow" : ""
                          }`}
                          aria-label={`${pendingApprovalCount} pending approvals`}
                        >
                          {pendingApprovalCount > 99
                            ? "99+"
                            : pendingApprovalCount}
                        </span>
                      )}
                    {/* Collapsed mode: dot indicator for Approvals */}
                    {collapsed &&
                      item.href === "/approvals" &&
                      pendingApprovalCount > 0 && (
                        <span
                          className={`absolute top-1 right-1 h-2 w-2 rounded-full bg-urgency-critical ${
                            hasNewArrival ? "animate-pulse-slow" : ""
                          }`}
                          role="status"
                          aria-label={`${pendingApprovalCount} pending approvals`}
                        />
                      )}
                  </a>
                </li>
              );
            })}
          </ul>
        </nav>

        {/* Footer */}
        <div className="border-t border-gray-200 p-3">
          {!collapsed && <p className="text-xs text-gray-400">PACT v0.1.0</p>}
        </div>
      </aside>
    </>
  );
}
