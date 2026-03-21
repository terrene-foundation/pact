// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * PostureBadge -- posture-specific badge with distinct colors.
 *
 * Color mapping:
 *   PSEUDO_AGENT       = gray
 *   SUPERVISED         = blue
 *   SHARED_PLANNING    = purple
 *   CONTINUOUS_INSIGHT = green
 *   DELEGATED          = gold
 */

"use client";

import type { TrustPosture } from "../../types/pact";

interface PostureBadgeProps {
  /** Trust posture value. */
  posture: TrustPosture;
  /** Size variant. */
  size?: "sm" | "md" | "lg";
}

/** Posture to color/label mapping. */
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
    bg: "bg-gray-100",
    text: "text-gray-800",
    border: "border-gray-300",
    label: "Pseudo Agent",
    description: "Minimal autonomy, maximum oversight",
  },
  supervised: {
    bg: "bg-blue-100",
    text: "text-blue-800",
    border: "border-blue-300",
    label: "Supervised",
    description: "Executes under close human supervision",
  },
  shared_planning: {
    bg: "bg-purple-100",
    text: "text-purple-800",
    border: "border-purple-300",
    label: "Shared Planning",
    description: "Human and agent plan together, agent executes",
  },
  continuous_insight: {
    bg: "bg-green-100",
    text: "text-green-800",
    border: "border-green-300",
    label: "Continuous Insight",
    description: "Agent operates autonomously, human monitors",
  },
  delegated: {
    bg: "bg-amber-100",
    text: "text-amber-800",
    border: "border-amber-300",
    label: "Delegated",
    description: "Full delegation within constraint envelope",
  },
};

const SIZE_MAP = {
  sm: "text-xs px-2 py-0.5",
  md: "text-sm px-2.5 py-1",
  lg: "text-sm px-3 py-1.5",
};

/** Posture-specific badge with color coding and optional tooltip. */
export default function PostureBadge({
  posture,
  size = "sm",
}: PostureBadgeProps) {
  const config = POSTURE_CONFIG[posture];
  const sizeClass = SIZE_MAP[size];

  return (
    <span
      className={`inline-flex items-center rounded-full border font-medium ${config.bg} ${config.text} ${config.border} ${sizeClass}`}
      title={config.description}
      data-posture={posture}
      role="status"
      aria-label={`Trust posture: ${config.label} -- ${config.description}`}
    >
      {config.label}
    </span>
  );
}

/** Posture indicator dot (small circle) for compact displays. */
export function PostureDot({ posture }: { posture: TrustPosture }) {
  const dotColors: Record<TrustPosture, string> = {
    pseudo_agent: "bg-gray-400",
    supervised: "bg-blue-500",
    shared_planning: "bg-purple-500",
    continuous_insight: "bg-green-500",
    delegated: "bg-amber-500",
  };

  const config = POSTURE_CONFIG[posture];

  return (
    <span
      className={`inline-block h-2.5 w-2.5 rounded-full ${dotColors[posture]}`}
      title={config.label}
      role="img"
      aria-label={`Posture: ${config.label}`}
    />
  );
}
