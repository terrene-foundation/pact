// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * Header -- top bar with breadcrumbs, page title, system status, and user menu.
 *
 * Displays:
 * - Breadcrumb navigation (configurable via props)
 * - Connection status indicator (connected/disconnected to WebSocket)
 * - Optional action buttons (right side)
 * - Authenticated user menu with sign-out
 */

"use client";

import { useState, useRef, useEffect } from "react";
import { useAuth, ROLE_LABELS } from "../../lib/auth-context";
import { NotificationBell } from "../notifications";

/** Single breadcrumb item. */
export interface Breadcrumb {
  /** Display label. */
  label: string;
  /** URL for the breadcrumb link. Omit for the current (last) item. */
  href?: string;
}

/** Connection status for the WebSocket indicator. */
export type ConnectionStatus = "connected" | "disconnected" | "connecting";

interface HeaderProps {
  /** Page title displayed prominently. */
  title: string;
  /** Breadcrumb trail. The last item is treated as the current page. */
  breadcrumbs?: Breadcrumb[];
  /** WebSocket connection status indicator. */
  connectionStatus?: ConnectionStatus;
  /** Optional content rendered on the right side (e.g., action buttons). */
  actions?: React.ReactNode;
  /** Callback when the mobile menu toggle is clicked. */
  onMenuToggle?: () => void;
}

/** Status indicator dot colors. */
const STATUS_COLORS: Record<ConnectionStatus, string> = {
  connected: "bg-green-500",
  disconnected: "bg-red-500",
  connecting: "bg-yellow-500",
};

const STATUS_LABELS: Record<ConnectionStatus, string> = {
  connected: "Connected",
  disconnected: "Disconnected",
  connecting: "Connecting...",
};

// ---------------------------------------------------------------------------
// User Menu
// ---------------------------------------------------------------------------

/** Dropdown menu showing operator name, role badge, and sign-out button. */
function UserMenu() {
  const { user, isAuthenticated, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    function handleClickOutside(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [open]);

  // Close on Escape key
  useEffect(() => {
    if (!open) return;
    function handleEscape(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("keydown", handleEscape);
    return () => document.removeEventListener("keydown", handleEscape);
  }, [open]);

  if (!isAuthenticated || !user) return null;

  const initials = user.name
    .split(/\s+/)
    .map((w) => w[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);

  return (
    <div className="relative" ref={menuRef}>
      <button
        onClick={() => setOpen((prev) => !prev)}
        className="flex items-center gap-2 rounded-lg px-2 py-1.5 text-sm text-gray-700 hover:bg-gray-100 transition-colors"
        aria-expanded={open}
        aria-haspopup="true"
        aria-label="User menu"
      >
        <div className="flex h-7 w-7 items-center justify-center rounded-full bg-care-primary text-xs font-semibold text-white">
          {initials}
        </div>
        <span className="hidden sm:inline font-medium">{user.name}</span>
        <svg
          className={`h-4 w-4 text-gray-400 transition-transform ${open ? "rotate-180" : ""}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
          aria-hidden="true"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M19 9l-7 7-7-7"
          />
        </svg>
      </button>

      {open && (
        <div className="absolute right-0 mt-1 w-56 rounded-lg border border-care-border bg-white py-1 shadow-lg z-50">
          {/* User info */}
          <div className="border-b border-care-border px-4 py-3">
            <p className="text-sm font-medium text-gray-900">{user.name}</p>
            <span className="mt-1 inline-flex items-center rounded-full bg-care-primary-light text-care-primary px-2 py-0.5 text-xs font-medium">
              {ROLE_LABELS[user.role]}
            </span>
          </div>

          {/* Sign out */}
          <div className="px-1 py-1">
            <button
              onClick={() => {
                setOpen(false);
                logout();
              }}
              className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm text-gray-700 hover:bg-gray-100 transition-colors"
            >
              <svg
                className="h-4 w-4 text-gray-400"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"
                />
              </svg>
              Sign Out
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Header
// ---------------------------------------------------------------------------

/** Dashboard header with breadcrumbs, status indicators, and user menu. */
export default function Header({
  title,
  breadcrumbs = [],
  connectionStatus,
  actions,
  onMenuToggle,
}: HeaderProps) {
  return (
    <header className="flex flex-col border-b border-gray-200 bg-white px-6 py-4">
      {/* Top row: breadcrumbs + status */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          {/* Mobile menu toggle */}
          {onMenuToggle && (
            <button
              onClick={onMenuToggle}
              className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600 lg:hidden"
              aria-label="Toggle navigation menu"
            >
              <svg
                className="h-6 w-6"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
                aria-hidden="true"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M4 6h16M4 12h16M4 18h16"
                />
              </svg>
            </button>
          )}

          {/* Breadcrumbs */}
          {breadcrumbs.length > 0 && (
            <nav aria-label="Breadcrumb">
              <ol className="flex items-center space-x-2 text-sm">
                {breadcrumbs.map((crumb, index) => {
                  const isLast = index === breadcrumbs.length - 1;
                  return (
                    <li
                      key={`${crumb.label}-${index}`}
                      className="flex items-center"
                    >
                      {index > 0 && (
                        <svg
                          className="mx-2 h-4 w-4 text-gray-400"
                          fill="none"
                          stroke="currentColor"
                          viewBox="0 0 24 24"
                          aria-hidden="true"
                          role="presentation"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M9 5l7 7-7 7"
                          />
                        </svg>
                      )}
                      {isLast || !crumb.href ? (
                        <span
                          className={
                            isLast
                              ? "font-medium text-gray-900"
                              : "text-gray-500"
                          }
                          {...(isLast
                            ? { "aria-current": "page" as const }
                            : {})}
                        >
                          {crumb.label}
                        </span>
                      ) : (
                        <a
                          href={crumb.href}
                          className="text-gray-500 hover:text-gray-700"
                        >
                          {crumb.label}
                        </a>
                      )}
                    </li>
                  );
                })}
              </ol>
            </nav>
          )}
        </div>

        <div className="flex items-center gap-4">
          {/* Connection status -- live region announces changes to screen readers */}
          {connectionStatus && (
            <div
              className="flex items-center gap-2 text-sm text-gray-600"
              role="status"
              aria-live="polite"
              aria-label={`Connection status: ${STATUS_LABELS[connectionStatus]}`}
            >
              <span
                className={`inline-block h-2.5 w-2.5 rounded-full ${STATUS_COLORS[connectionStatus]}`}
                aria-hidden="true"
              />
              <span>{STATUS_LABELS[connectionStatus]}</span>
            </div>
          )}

          {/* Notification bell */}
          <NotificationBell />

          {/* Action buttons */}
          {actions}

          {/* User menu */}
          <UserMenu />
        </div>
      </div>

      {/* Title */}
      <h1 className="mt-2 text-2xl font-bold text-gray-900">{title}</h1>
    </header>
  );
}
