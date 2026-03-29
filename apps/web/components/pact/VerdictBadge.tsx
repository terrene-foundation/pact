// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * VerdictBadge -- verification gradient badge with semantic coloring.
 *
 * Extracted from app/requests/page.tsx inline VerdictBadge pattern.
 * Maps verification gradient levels (AUTO_APPROVED, FLAGGED, HELD, BLOCKED)
 * to the PACT semantic color system defined in tailwind.config.js.
 */

"use client";

import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/shadcn/badge";

/**
 * Color mapping for each verification gradient level.
 *
 * Uses the `gradient-*` semantic colors from tailwind.config.js:
 *   gradient-auto    = green  (#16a34a)
 *   gradient-flagged = yellow (#eab308)
 *   gradient-held    = orange (#f97316)
 *   gradient-blocked = red    (#dc2626)
 */
const VERDICT_STYLES: Record<string, string> = {
  auto_approved:
    "bg-gradient-auto-light text-gradient-auto-dark border-gradient-auto/30",
  flagged:
    "bg-gradient-flagged-light text-gradient-flagged-dark border-gradient-flagged/30",
  held: "bg-gradient-held-light text-gradient-held-dark border-gradient-held/30",
  blocked:
    "bg-gradient-blocked-light text-gradient-blocked-dark border-gradient-blocked/30",
};

/** Human-readable labels for each verdict level. */
const VERDICT_LABELS: Record<string, string> = {
  auto_approved: "Auto Approved",
  flagged: "Flagged",
  held: "Held",
  blocked: "Blocked",
};

interface VerdictBadgeProps {
  /** Verification gradient level string (case-insensitive, underscores or spaces). */
  level: string | null;
  /** Additional CSS classes. */
  className?: string;
}

/**
 * Renders a colored badge for a verification gradient verdict.
 * Returns a muted "No verdict" label when the level is null/undefined.
 */
export function VerdictBadge({ level, className }: VerdictBadgeProps) {
  if (!level) {
    return (
      <span className="text-xs text-muted-foreground italic">No verdict</span>
    );
  }

  const normalized = level.toLowerCase().replace(/\s+/g, "_");
  const style =
    VERDICT_STYLES[normalized] ?? "bg-gray-100 text-gray-700 border-gray-300";
  const label =
    VERDICT_LABELS[normalized] ??
    level.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

  return (
    <Badge
      variant="outline"
      className={cn("rounded-full font-medium", style, className)}
    >
      {label}
    </Badge>
  );
}
