// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * PriorityIndicator -- visual priority level indicator with colored bars.
 *
 * Extracted from app/requests/page.tsx inline PriorityIndicator pattern.
 * Displays 4 bars where filled count represents the priority level:
 *   critical = 4 bars (red)
 *   high     = 3 bars (orange)
 *   medium   = 2 bars (blue)
 *   low      = 1 bar  (gray)
 */

"use client";

import { cn } from "@/lib/utils";

/** Priority level type. */
type PriorityLevel = "critical" | "high" | "medium" | "low";

/** Bar count and color for each priority level. */
const PRIORITY_CONFIG: Record<
  PriorityLevel,
  { bars: number; color: string; textColor: string }
> = {
  critical: {
    bars: 4,
    color: "bg-urgency-critical",
    textColor: "text-urgency-critical",
  },
  high: { bars: 3, color: "bg-urgency-high", textColor: "text-urgency-high" },
  medium: { bars: 2, color: "bg-blue-500", textColor: "text-blue-500" },
  low: { bars: 1, color: "bg-urgency-low", textColor: "text-urgency-low" },
};

interface PriorityIndicatorProps {
  /** Priority level string. */
  priority: string;
  /** Whether to show the text label alongside the bars. */
  showLabel?: boolean;
  /** Additional CSS classes. */
  className?: string;
}

/**
 * Visual priority indicator with colored vertical bars and optional label.
 * Defaults to showing the label.
 */
export function PriorityIndicator({
  priority,
  showLabel = true,
  className,
}: PriorityIndicatorProps) {
  const normalized = priority.toLowerCase() as PriorityLevel;
  const config = PRIORITY_CONFIG[normalized] ?? PRIORITY_CONFIG.low;

  return (
    <div
      className={cn("flex items-center gap-1", className)}
      title={priority}
      role="img"
      aria-label={`Priority: ${priority}`}
    >
      {Array.from({ length: 4 }).map((_, i) => (
        <div
          key={i}
          className={cn(
            "h-3 w-1 rounded-sm",
            i < config.bars ? config.color : "bg-gray-200",
          )}
        />
      ))}
      {showLabel && (
        <span className={cn("ml-1 text-xs font-medium", config.textColor)}>
          {priority.charAt(0).toUpperCase() + priority.slice(1)}
        </span>
      )}
    </div>
  );
}
