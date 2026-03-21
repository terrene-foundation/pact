// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * StatusBadge -- color-coded badge for verification levels and trust postures.
 *
 * Verification levels:
 *   AUTO_APPROVED = green
 *   FLAGGED       = yellow
 *   HELD          = orange
 *   BLOCKED       = red
 *
 * Trust postures:
 *   pseudo_agent       = gray
 *   supervised         = blue
 *   shared_planning    = indigo
 *   continuous_insight = purple
 *   delegated          = emerald
 *
 * Bridge/workspace status uses contextual coloring.
 */

"use client";

import type {
  VerificationLevel,
  TrustPosture,
  BridgeStatus,
  WorkspaceState,
} from "../../types/pact";

type BadgeVariant =
  | VerificationLevel
  | TrustPosture
  | BridgeStatus
  | WorkspaceState
  | string;

interface StatusBadgeProps {
  /** The status value to display. */
  value: BadgeVariant;
  /** Optional override label text. When omitted, value is displayed. */
  label?: string;
  /** Size variant. Defaults to "sm". */
  size?: "xs" | "sm" | "md";
}

/** Map of known status values to Tailwind color classes. */
const COLOR_MAP: Record<string, string> = {
  // Verification levels
  AUTO_APPROVED: "bg-green-100 text-green-800 border-green-300",
  FLAGGED: "bg-yellow-100 text-yellow-800 border-yellow-300",
  HELD: "bg-orange-100 text-orange-800 border-orange-300",
  BLOCKED: "bg-red-100 text-red-800 border-red-300",

  // Trust postures
  pseudo_agent: "bg-gray-100 text-gray-800 border-gray-300",
  supervised: "bg-blue-100 text-blue-800 border-blue-300",
  shared_planning: "bg-indigo-100 text-indigo-800 border-indigo-300",
  continuous_insight: "bg-purple-100 text-purple-800 border-purple-300",
  delegated: "bg-emerald-100 text-emerald-800 border-emerald-300",

  // Bridge status
  pending: "bg-yellow-100 text-yellow-800 border-yellow-300",
  negotiating: "bg-amber-100 text-amber-800 border-amber-300",
  active: "bg-green-100 text-green-800 border-green-300",
  suspended: "bg-orange-100 text-orange-800 border-orange-300",
  expired: "bg-gray-100 text-gray-600 border-gray-300",
  closed: "bg-gray-100 text-gray-600 border-gray-300",
  revoked: "bg-red-100 text-red-800 border-red-300",

  // Workspace state
  provisioning: "bg-blue-100 text-blue-800 border-blue-300",
  archived: "bg-gray-100 text-gray-600 border-gray-300",
  decommissioned: "bg-gray-200 text-gray-500 border-gray-300",

  // Agent status
  inactive: "bg-gray-100 text-gray-600 border-gray-300",
};

/** Default color for unknown status values. */
const DEFAULT_COLOR = "bg-gray-100 text-gray-700 border-gray-300";

const SIZE_MAP: Record<string, string> = {
  xs: "text-xs px-1.5 py-0.5",
  sm: "text-xs px-2 py-0.5",
  md: "text-sm px-2.5 py-1",
};

/**
 * Format a status value for display.
 * Replaces underscores with spaces and capitalizes each word.
 */
function formatLabel(value: string): string {
  return value.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

/** Color-coded status badge for verification levels, postures, and statuses. */
export default function StatusBadge({
  value,
  label,
  size = "sm",
}: StatusBadgeProps) {
  const colorClass = COLOR_MAP[value] ?? DEFAULT_COLOR;
  const sizeClass = SIZE_MAP[size] ?? SIZE_MAP.sm;
  const displayText = label ?? formatLabel(value);

  return (
    <span
      className={`inline-flex items-center rounded-full border font-medium ${colorClass} ${sizeClass}`}
      data-status={value}
      role="status"
      aria-label={`Status: ${displayText}`}
    >
      {displayText}
    </span>
  );
}
