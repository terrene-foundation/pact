// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * PostureBadge -- trust posture badge using Shadcn Badge primitives.
 *
 * Wraps the existing posture color mapping from components/agents/PostureBadge
 * with Shadcn Badge for consistent styling. Uses the posture-* semantic colors
 * from tailwind.config.js.
 *
 * Color mapping:
 *   pseudo_agent       = gray   (posture-pseudo)
 *   supervised         = blue   (posture-supervised)
 *   shared_planning    = purple (posture-shared)
 *   continuous_insight = cyan   (posture-continuous)
 *   delegated          = green  (posture-delegated)
 */

"use client";

import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/shadcn/badge";
import type { TrustPosture } from "@/types/pact";

/** Posture configuration: colors, label, and description. */
const POSTURE_CONFIG: Record<
  TrustPosture,
  {
    bg: string;
    text: string;
    border: string;
    label: string;
    description: string;
  }
> = {
  pseudo_agent: {
    bg: "bg-posture-pseudo-light",
    text: "text-gray-700",
    border: "border-gray-300",
    label: "Pseudo Agent",
    description: "Minimal autonomy, maximum oversight",
  },
  supervised: {
    bg: "bg-posture-supervised-light",
    text: "text-blue-700",
    border: "border-blue-300",
    label: "Supervised",
    description: "Executes under close human supervision",
  },
  shared_planning: {
    bg: "bg-posture-shared-light",
    text: "text-purple-700",
    border: "border-purple-300",
    label: "Shared Planning",
    description: "Human and agent plan together, agent executes",
  },
  continuous_insight: {
    bg: "bg-posture-continuous-light",
    text: "text-cyan-700",
    border: "border-cyan-300",
    label: "Continuous Insight",
    description: "Agent operates autonomously, human monitors",
  },
  delegated: {
    bg: "bg-posture-delegated-light",
    text: "text-green-700",
    border: "border-green-300",
    label: "Delegated",
    description: "Full delegation within constraint envelope",
  },
};

/** Dot colors for the compact PostureDot variant. */
const DOT_COLORS: Record<TrustPosture, string> = {
  pseudo_agent: "bg-gray-400",
  supervised: "bg-blue-500",
  shared_planning: "bg-purple-500",
  continuous_insight: "bg-cyan-500",
  delegated: "bg-green-500",
};

interface PostureBadgeProps {
  /** Trust posture value. */
  posture: TrustPosture;
  /** Size variant. */
  size?: "sm" | "md" | "lg";
  /** Additional CSS classes. */
  className?: string;
}

const SIZE_MAP = {
  sm: "text-xs px-2 py-0.5",
  md: "text-sm px-2.5 py-1",
  lg: "text-sm px-3 py-1.5",
};

/**
 * Trust posture badge with semantic coloring.
 * Includes an accessible tooltip description via `title`.
 */
export function PostureBadge({
  posture,
  size = "sm",
  className,
}: PostureBadgeProps) {
  const config = POSTURE_CONFIG[posture];
  const sizeClass = SIZE_MAP[size];

  return (
    <Badge
      variant="outline"
      className={cn(
        "rounded-full font-medium",
        config.bg,
        config.text,
        config.border,
        sizeClass,
        className,
      )}
      title={config.description}
      data-posture={posture}
      role="status"
      aria-label={`Trust posture: ${config.label} -- ${config.description}`}
    >
      {config.label}
    </Badge>
  );
}

interface PostureDotProps {
  /** Trust posture value. */
  posture: TrustPosture;
  /** Additional CSS classes. */
  className?: string;
}

/** Compact posture dot indicator for use in dense layouts. */
export function PostureDot({ posture, className }: PostureDotProps) {
  const config = POSTURE_CONFIG[posture];

  return (
    <span
      className={cn(
        "inline-block h-2.5 w-2.5 rounded-full",
        DOT_COLORS[posture],
        className,
      )}
      title={config.label}
      role="img"
      aria-label={`Posture: ${config.label}`}
    />
  );
}
